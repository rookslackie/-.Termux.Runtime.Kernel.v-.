"""Durable jobs, source preservation, and stepwise execution for an owner UI.

This module has no UI dependency. A single executor leases each home, commits
progress after each operator, and resumes queued work after a process restart.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import sqlite3
import threading
import uuid

from .common import PROFILES, Profile, QuantumComputeError, canonical, digest
from .glyphsafe import Identity, SUITE, public_id
from .runtime import Runtime, ExecutionGrant
from .tessera import compile_program, engine_hash, GLYPHS, OPERATORS, DIALECT, DIALECT_V3
from .thinksync import ThinkSync


def now():
    return datetime.now(timezone.utc).isoformat()


def capabilities():
    import inspect
    from . import __version__
    return {"schema": "xi.living-circuit.capabilities.v1", "version": __version__,
            "dialects": [DIALECT, DIALECT_V3], "execution": "local classical numerical simulation",
            "engine_sha256": engine_hash(), "glyphsafe_suite": SUITE,
            "operators": [{"operator": name, "glyph": glyph,
                "parameters": str(inspect.signature(OPERATORS[name])) if name in OPERATORS else None,
                "description": (inspect.getdoc(OPERATORS[name]) or "").split("\n")[0] if name in OPERATORS else name}
                for name, glyph in GLYPHS.items()],
            "profiles": {name: profile.__dict__ for name, profile in PROFILES.items()},
            "glyph_definitions": {"versioned": True, "max_definitions": 64,
                "max_expanded_steps": 1024, "max_nesting": 16,
                "semantics": "explicit typed macro lowering; exact codepoints retained"},
            "job_states": ["queued", "running", "completed", "paused", "failed", "cancelled", "interrupted", "needs_recompile"],
            "cancellation": "between operators; an active numerical operator finishes its bounded call",
            "transport": "ThinkSync encrypted source/checkpoint packets; receive preserves bytes",
            "return_operator": "⟁∴Ω"}


class Workbench:
    def __init__(self, home, *, profile=Profile(), start_worker=True):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.profile = profile
        self.profile_sha256 = digest(asdict(profile))
        self.engine_sha256 = engine_hash()
        self._lease = (self.home / "workbench.lock").open("a")
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._lease.close()
            raise QuantumComputeError("Another Living Circuit service owns this home") from exc
        self.database = self.home / "jobs.sqlite3"
        self._wake, self._stop = threading.Event(), threading.Event()
        self._worker = None
        self.runtime = Runtime(self.home / "runtime", profile=profile)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                    source BLOB NOT NULL, source_sha256 TEXT NOT NULL, engine_sha256 TEXT NOT NULL,
                    profile_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    result TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS job_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(id), at TEXT NOT NULL,
                    kind TEXT NOT NULL, data TEXT NOT NULL);
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
            if "profile_sha256" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN profile_sha256 TEXT")
            db.execute("UPDATE jobs SET state='queued',updated_at=? WHERE state IN ('running','interrupted')", (now(),))
            db.execute("UPDATE jobs SET state='needs_recompile',error=?,updated_at=? WHERE state='queued' AND (engine_sha256!=? OR profile_sha256 IS NULL OR profile_sha256!=?)",
                       ("Engine or resource profile changed; compile and submit a new request", now(), self.engine_sha256, self.profile_sha256))
        if start_worker:
            self.start()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _event(self, db, job_id, kind, data):
        db.execute("INSERT INTO job_events(job_id,at,kind,data) VALUES (?,?,?,?)",
                   (job_id, now(), kind, canonical(data).decode()))

    def submit(self, source, *, request_id=None):
        if type(source) is not str:
            raise QuantumComputeError("source must be UTF-8 program text")
        raw = source.encode("utf-8")
        plan = compile_program(raw)
        if plan.engine_sha256 != self.engine_sha256:
            raise QuantumComputeError("Engine source changed since service startup; restart before compiling new work")
        request_id = str(uuid.uuid4()) if request_id is None else request_id
        if type(request_id) is not str or not 1 <= len(request_id) <= 128:
            raise QuantumComputeError("request_id must contain 1..128 characters")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM jobs WHERE request_id=?", (request_id,)).fetchone()
            if prior:
                if (prior["source_sha256"] != plan.program_sha256 or prior["engine_sha256"] != plan.engine_sha256
                        or prior["profile_sha256"] != self.profile_sha256):
                    raise QuantumComputeError("This request_id already names different source or an earlier engine")
                job_id = prior["id"]
            else:
                job_id = str(uuid.uuid4())
                at = now()
                db.execute("INSERT INTO jobs(id,request_id,source,source_sha256,engine_sha256,profile_sha256,state,created_at,updated_at) VALUES (?,?,?,?,?,?,'queued',?,?)",
                           (job_id, request_id, raw, plan.program_sha256, plan.engine_sha256, self.profile_sha256, at, at))
                self._event(db, job_id, "queued", {"primitive_steps": len(plan.steps), "source_sha256": plan.program_sha256})
        self._wake.set()
        return self.get(job_id)

    def get(self, job_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown job")
        result = dict(row)
        del result["source"]
        result["result"] = json.loads(result["result"]) if result["result"] else None
        result["cancel_requested"] = bool(result["cancel_requested"])
        return result

    def source(self, job_id):
        with self._connect() as db:
            row = db.execute("SELECT source,source_sha256 FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown job")
        if digest(row[0]) != row[1]:
            raise QuantumComputeError("Job source commitment failed")
        return row[0].decode("utf-8")

    def list(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise QuantumComputeError("limit must be 1..100")
        with self._connect() as db:
            rows = db.execute("SELECT id,request_id,source_sha256,state,created_at,updated_at,error FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def events(self, job_id, after=0):
        self.get(job_id)
        if type(after) is not int or after < 0:
            raise QuantumComputeError("after must be a nonnegative event cursor")
        with self._connect() as db:
            rows = db.execute("SELECT * FROM job_events WHERE job_id=? AND sequence>? ORDER BY sequence LIMIT 200", (job_id, after)).fetchall()
        return [{**dict(row), "data": json.loads(row["data"])} for row in rows]

    def cancel(self, job_id):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError("Unknown job")
            if row[0] not in ("completed", "failed", "cancelled", "needs_recompile"):
                state = "cancelled" if row[0] in ("queued", "paused", "interrupted") else row[0]
                db.execute("UPDATE jobs SET state=?,cancel_requested=1,updated_at=? WHERE id=?", (state, now(), job_id))
                self._event(db, job_id, "cancel_requested", {})
        return self.get(job_id)

    def resume(self, job_id):
        job = self.get(job_id)
        if job["engine_sha256"] != engine_hash() or job["profile_sha256"] != self.profile_sha256:
            raise QuantumComputeError("Engine or resource profile changed; submit the source as a new compiled request")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute("UPDATE jobs SET state='queued',cancel_requested=0,error=NULL,updated_at=? WHERE id=? AND state IN ('paused','cancelled','failed','interrupted')",
                                 (now(), job_id)).rowcount
            if changed:
                self._event(db, job_id, "resumed", {})
        self._wake.set()
        return self.get(job_id)

    def start(self):
        if self._worker is None:
            self._worker = threading.Thread(target=self._loop, daemon=True, name="xi-living-circuit")
            self._worker.start()

    def _claim(self):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET state='running',updated_at=? WHERE id=?", (now(), row[0]))
            self._event(db, row[0], "running", {})
            return row[0]

    def _finish(self, job_id, state, *, receipt=None, error=None):
        with self._connect() as db:
            db.execute("UPDATE jobs SET state=?,result=COALESCE(?,result),error=?,updated_at=? WHERE id=?",
                       (state, canonical(receipt).decode() if receipt is not None else None, error, now(), job_id))
            self._event(db, job_id, state, {"error": error} if error else {})

    def _execute_job(self, job_id):
        try:
            source = self.source(job_id).encode("utf-8")
            plan = compile_program(source)
            if self.get(job_id)["engine_sha256"] != plan.engine_sha256:
                self._finish(job_id, "needs_recompile", error="Engine changed since submission")
                return
            grant = ExecutionGrant(plan.program_sha256, frozenset(step["operator"] for step in plan.steps))
            while True:
                if engine_hash() != self.engine_sha256:
                    self._finish(job_id, "needs_recompile", error="Engine source changed during the job; restart the service")
                    return
                if self._stop.is_set():
                    self._finish(job_id, "interrupted")
                    return
                if self.get(job_id)["cancel_requested"]:
                    self._finish(job_id, "cancelled")
                    return
                receipt = self.runtime.run(source, grant=grant, stop_after=1)
                with self._connect() as db:
                    db.execute("UPDATE jobs SET result=?,updated_at=? WHERE id=?", (canonical(receipt).decode(), now(), job_id))
                    last = receipt["steps"][-1] if receipt["steps"] else None
                    self._event(db, job_id, "step", {"completed_steps": receipt["completed_steps"],
                        "operator": last["operator"] if last else None,
                        "result_sha256": digest(last["result"]) if last else None})
                if receipt["closed"]:
                    self._finish(job_id, "completed", receipt=receipt)
                    return
                if receipt["steps"] and receipt["steps"][-1]["operator"] == "Rest":
                    self._finish(job_id, "paused", receipt=receipt)
                    return
        except Exception as exc:
            self._finish(job_id, "failed", error=f"{type(exc).__name__}: {exc}")

    def _loop(self):
        while not self._stop.is_set():
            job_id = self._claim()
            if job_id is None:
                self._wake.wait(.25)
                self._wake.clear()
            else:
                self._execute_job(job_id)

    def identity(self):
        return Identity.load_or_create(self.home / "identity.secret.json")

    def export(self, job_id, recipient):
        job = self.get(job_id)
        checkpoint = self.runtime.checkpoint(job["result"]) if job["result"] else None
        return ThinkSync(self.runtime, self.identity()).queue(self.source(job_id).encode(), recipient, checkpoint=checkpoint)

    def receive(self, wire, sender):
        return ThinkSync(self.runtime, self.identity(), trusted_senders={public_id(sender): sender}).receive(wire)

    def close(self):
        self._stop.set()
        self._wake.set()
        if self._worker is not None:
            self._worker.join(timeout=30)
            if self._worker.is_alive():
                raise QuantumComputeError("An active operator is still finishing; the home lease remains held")
        if not self._lease.closed:
            fcntl.flock(self._lease, fcntl.LOCK_UN)
            self._lease.close()
