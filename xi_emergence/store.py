"""Ξ.Emergence · store.py

Every committed field transition becomes a capsule receipt in local SQLite,
chained by hash so the history of the field can be checked, not trusted.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class EmergenceLedger:
    """Append-only, hash-chained ledger of emergence and operator receipts."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS emergence_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                actor TEXT NOT NULL,
                operator TEXT,
                idempotency_key TEXT UNIQUE,
                data_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                previous_hash TEXT,
                event_hash TEXT NOT NULL
            );
            """
        )
        self._db.commit()

    # ── writes ──────────────────────────────────────────────────────────
    def append(
        self,
        kind: str,
        actor: str,
        operator: str | None,
        data: dict[str, Any],
        metrics: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            previous = self._db.execute(
                "SELECT event_hash FROM emergence_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous_hash = previous["event_hash"] if previous else None
            event = {
                "event_id": str(uuid.uuid4()),
                "kind": kind,
                "actor": actor,
                "operator": operator,
                "data": data,
                "metrics": metrics,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "previous_hash": previous_hash,
            }
            event_hash = hashlib.sha256(_canonical(event).encode("utf-8")).hexdigest()
            self._db.execute(
                """INSERT INTO emergence_events
                   (event_id, kind, actor, operator, idempotency_key,
                    data_json, metrics_json, created_at, previous_hash, event_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["event_id"], kind, actor, operator, idempotency_key,
                    _canonical(data), _canonical(metrics), event["created_at"],
                    previous_hash, event_hash,
                ),
            )
            self._db.commit()
            row = self._db.execute(
                "SELECT sequence FROM emergence_events WHERE event_id = ?", (event["event_id"],)
            ).fetchone()
            return {**event, "sequence": row["sequence"], "event_hash": event_hash}

    # ── reads ───────────────────────────────────────────────────────────
    def find(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM emergence_events WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
        return self._row(row) if row else None

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM emergence_events ORDER BY sequence DESC LIMIT ?", (int(limit),)
            ).fetchall()
        return [self._row(row) for row in rows]

    def verify(self) -> dict[str, Any]:
        """Recompute the chain. A broken link is reported, never hidden."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM emergence_events ORDER BY sequence ASC"
            ).fetchall()
        previous_hash = None
        for row in rows:
            entry = {
                "event_id": row["event_id"],
                "kind": row["kind"],
                "actor": row["actor"],
                "operator": row["operator"],
                "data": json.loads(row["data_json"]),
                "metrics": json.loads(row["metrics_json"]),
                "created_at": row["created_at"],
                "previous_hash": row["previous_hash"],
            }
            expected = hashlib.sha256(_canonical(entry).encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
                return {"ok": False, "entries": len(rows), "broken_at": row["sequence"],
                        "head": rows[-1]["event_hash"] if rows else None}
            previous_hash = row["event_hash"]
        return {"ok": True, "entries": len(rows), "head": previous_hash}

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "sequence": row["sequence"],
            "event_id": row["event_id"],
            "kind": row["kind"],
            "actor": row["actor"],
            "operator": row["operator"],
            "data": json.loads(row["data_json"]),
            "metrics": json.loads(row["metrics_json"]),
            "created_at": row["created_at"],
            "previous_hash": row["previous_hash"],
            "event_hash": row["event_hash"],
        }
