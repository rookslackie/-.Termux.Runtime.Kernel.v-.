"""A small local-first world kernel built from Xi capsule and provenance primitives.

SQLite is the local filesystem for this prototype. Every committed transition is
stored as a capsule and linked to its causes. Entity state is a materialized view
of those transitions; model inference and external services are not required.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping

from .workbench import compose_structural_field


class WorldError(ValueError):
    """Raised when a requested transition violates the current world rules."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Event:
    world_id: str
    sequence: int
    event_id: str
    actor_id: str
    action: str
    target_id: str | None
    data: dict[str, Any]
    causes: tuple[str, ...]
    created_at: str
    anchor: str
    mirror: str
    content: str
    rules: tuple[str, ...]
    echo: dict[str, Any]
    previous_hash: str | None
    event_hash: str


class WorldKernel:
    """Persistent world state, participants, event capsules, and causal DAG."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        if self.database != ":memory:":
            Path(self.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS worlds (
                    world_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS participants (
                    world_id TEXT NOT NULL,
                    participant_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    identity_json TEXT NOT NULL,
                    PRIMARY KEY (world_id, participant_id),
                    FOREIGN KEY (world_id) REFERENCES worlds(world_id)
                );
                CREATE TABLE IF NOT EXISTS entities (
                    world_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    PRIMARY KEY (world_id, entity_id),
                    FOREIGN KEY (world_id) REFERENCES worlds(world_id)
                );
                CREATE TABLE IF NOT EXISTS capsules (
                    world_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_id TEXT,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    anchor TEXT NOT NULL,
                    mirror TEXT NOT NULL,
                    content TEXT NOT NULL,
                    rules_json TEXT NOT NULL,
                    echo_json TEXT NOT NULL,
                    previous_hash TEXT,
                    event_hash TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    PRIMARY KEY (world_id, event_id),
                    UNIQUE (world_id, sequence),
                    UNIQUE (world_id, actor_id, idempotency_key),
                    FOREIGN KEY (world_id) REFERENCES worlds(world_id)
                );
                CREATE TABLE IF NOT EXISTS causal_edges (
                    world_id TEXT NOT NULL,
                    parent_event_id TEXT NOT NULL,
                    child_event_id TEXT NOT NULL,
                    PRIMARY KEY (world_id, parent_event_id, child_event_id),
                    FOREIGN KEY (world_id, parent_event_id)
                        REFERENCES capsules(world_id, event_id),
                    FOREIGN KEY (world_id, child_event_id)
                        REFERENCES capsules(world_id, event_id)
                );
                CREATE INDEX IF NOT EXISTS capsules_world_sequence
                    ON capsules(world_id, sequence);
                CREATE INDEX IF NOT EXISTS causal_edges_child
                    ON causal_edges(world_id, child_event_id);
                CREATE TRIGGER IF NOT EXISTS capsules_append_only_update
                    BEFORE UPDATE ON capsules BEGIN SELECT RAISE(ABORT, 'capsules are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS capsules_append_only_delete
                    BEFORE DELETE ON capsules BEGIN SELECT RAISE(ABORT, 'capsules are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causal_edges_append_only_update
                    BEFORE UPDATE ON causal_edges BEGIN SELECT RAISE(ABORT, 'causal edges are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causal_edges_append_only_delete
                    BEFORE DELETE ON causal_edges BEGIN SELECT RAISE(ABORT, 'causal edges are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS participants_identity_immutable_update
                    BEFORE UPDATE ON participants BEGIN SELECT RAISE(ABORT, 'participant identities are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS participants_identity_immutable_delete
                    BEFORE DELETE ON participants BEGIN SELECT RAISE(ABORT, 'participant identities are immutable'); END;
                """
            )

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="microseconds")

    def create_world(
        self,
        world_id: str,
        name: str,
        participants: Iterable[Mapping[str, Any]],
        entities: Iterable[Mapping[str, Any]],
    ) -> Event:
        """Create a world and record its initial frame as the genesis capsule."""
        participants = [dict(p) for p in participants]
        entities = [dict(e) for e in entities]
        if not world_id or not name:
            raise WorldError("world_id and name are required")
        if not any(p.get("participant_id") == "world:genesis" for p in participants):
            participants.append({
                "participant_id": "world:genesis",
                "display_name": "World Genesis",
                "kind": "system",
                "identity": {"role": "initial-frame", "origin": "local-kernel"},
            })
        ids = [p.get("participant_id") for p in participants]
        if len(ids) != len(set(ids)):
            raise WorldError("participant IDs must be unique within a world")
        entity_ids = [e.get("entity_id") for e in entities]
        if None in entity_ids or len(entity_ids) != len(set(entity_ids)):
            raise WorldError("entity IDs must be present and unique within a world")
        now = self._now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("INSERT INTO worlds VALUES (?, ?, ?)", (world_id, name, now))
                for participant in participants:
                    if not all(participant.get(key) for key in ("participant_id", "display_name", "kind")):
                        raise WorldError("participants require participant_id, display_name, and kind")
                    db.execute(
                        "INSERT INTO participants VALUES (?, ?, ?, ?, ?)",
                        (world_id, participant["participant_id"], participant["display_name"],
                         participant["kind"], _json(participant.get("identity", {}))),
                    )
                for entity in entities:
                    if not entity.get("kind"):
                        raise WorldError(f"entity {entity['entity_id']} requires kind")
                    db.execute(
                        "INSERT INTO entities VALUES (?, ?, ?, ?)",
                        (world_id, entity["entity_id"], entity["kind"], _json(entity.get("state", {}))),
                    )
                initial = {e["entity_id"]: e.get("state", {}) for e in entities}
                event = self._commit_event(
                    db, world_id=world_id, actor_id="world:genesis", action="world.genesis",
                    target_id=None, data={"name": name, "initial_entities": initial},
                    causes=(), idempotency_key="genesis", content=f"The world {name} opens.",
                    rules=("capsule.genesis", "identity.preserve", "provenance.append"), echo=initial,
                    anchor="⟁", mirror="∅", created_at=now,
                )
                db.commit()
                return event
            except Exception:
                db.rollback()
                raise

    def apply(
        self,
        world_id: str,
        actor_id: str,
        action: str,
        target_id: str,
        *,
        causes: Iterable[str] | None = None,
        idempotency_key: str,
        data: Mapping[str, Any] | None = None,
    ) -> Event:
        """Apply one lawful transition and persist its capsule and causal edges."""
        if not idempotency_key:
            raise WorldError("an idempotency_key is required")
        payload = dict(data or {})
        requested_causes = tuple(causes) if causes is not None else None
        request = {"action": action, "target_id": target_id, "data": payload,
                   "causes": requested_causes}
        request_hash = _hash(request)
        legacy_request_hash = _hash({"action": action, "target_id": target_id, "data": payload})
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                prior = db.execute(
                    "SELECT * FROM capsules WHERE world_id=? AND actor_id=? AND idempotency_key=?",
                    (world_id, actor_id, idempotency_key),
                ).fetchone()
                if prior:
                    if prior["request_hash"] != request_hash:
                        prior_event = self._row_to_event(db, prior)
                        legacy_replay_matches = (
                            prior["request_hash"] == legacy_request_hash
                            and (requested_causes is None or tuple(dict.fromkeys(requested_causes)) == prior_event.causes)
                        )
                        if not legacy_replay_matches:
                            raise WorldError("idempotency key was already used for a different transition")
                    event = self._row_to_event(db, prior)
                    db.commit()
                    return event
                self._require_participant(db, world_id, actor_id)
                head = db.execute(
                    "SELECT event_id FROM capsules WHERE world_id=? ORDER BY sequence DESC LIMIT 1",
                    (world_id,),
                ).fetchone()
                parent_ids = tuple(dict.fromkeys(requested_causes if requested_causes is not None else ([head["event_id"]] if head else [])))
                if head and not parent_ids:
                    raise WorldError("non-genesis transitions need at least one explicit causal parent")
                for parent_id in parent_ids:
                    row = db.execute(
                        "SELECT 1 FROM capsules WHERE world_id=? AND event_id=?", (world_id, parent_id)
                    ).fetchone()
                    if not row:
                        raise WorldError(f"causal parent {parent_id!r} is not in world {world_id!r}")
                event_id = "evt_" + hashlib.sha256(
                    f"{world_id}\0{actor_id}\0{idempotency_key}".encode("utf-8")
                ).hexdigest()[:24]
                changes, content, rule_names = self._transition(
                    db, world_id, actor_id, action, target_id, payload, event_id, parent_ids
                )
                event = self._commit_event(
                    db, world_id=world_id, actor_id=actor_id, action=action,
                    target_id=target_id, data=payload, causes=parent_ids,
                    idempotency_key=idempotency_key, content=content,
                    rules=rule_names, echo=changes, anchor="⟐", mirror=parent_ids[0] if parent_ids else "∅",
                    created_at=self._now(), event_id=event_id, request_hash=request_hash,
                )
                db.commit()
                return event
            except Exception:
                db.rollback()
                raise

    def _transition(
        self,
        db: sqlite3.Connection,
        world_id: str,
        actor_id: str,
        action: str,
        target_id: str,
        data: dict[str, Any],
        event_id: str,
        causes: tuple[str, ...],
    ) -> tuple[dict[str, Any], str, tuple[str, ...]]:
        if action == "residue.capture":
            if not target_id or not all(ch.isalnum() or ch in "_-.:" for ch in target_id):
                raise WorldError("residue IDs may contain letters, digits, dot, dash, and underscore")
            if db.execute(
                "SELECT 1 FROM entities WHERE world_id=? AND entity_id=?", (world_id, target_id)
            ).fetchone():
                raise WorldError(f"entity already exists: {target_id}")
            provenance = data.get("provenance")
            if not isinstance(provenance, str) or provenance not in {
                "recovered", "composed", "mixed", "proposed", "simulated"
            }:
                raise WorldError("residue provenance must be recovered, composed, mixed, proposed, or simulated")
            recovered, composed = data.get("recovered", []), data.get("composed", [])
            if not isinstance(recovered, list) or not all(isinstance(x, str) for x in recovered):
                raise WorldError("residue recovered entries must be a list of strings")
            if not isinstance(composed, list) or not all(isinstance(x, str) for x in composed):
                raise WorldError("residue composed entries must be a list of strings")
            if provenance == "mixed" and (not recovered or not composed):
                raise WorldError("mixed residues need separate recovered and composed entries")
            form = data.get("form", {})
            if not isinstance(form, dict):
                raise WorldError("residue form must be an object")
            captured = {
                "residue_id": target_id,
                "provenance": provenance,
                "source_ref": data.get("source_ref"),
                "recovered": recovered,
                "composed": composed,
                "image_or_fragment": data.get("image_or_fragment", ""),
                "form": form,
                "captured_by": actor_id,
                "captured_by_event": event_id,
            }
            try:
                compose_structural_field([captured])
            except (KeyError, TypeError, ValueError) as exc:
                raise WorldError(f"invalid explicit residue form: {exc}") from exc
            db.execute(
                "INSERT INTO entities VALUES (?, ?, 'residue', ?)",
                (world_id, target_id, _json(captured)),
            )
            return ({target_id: captured}, f"{actor_id} records residue {target_id} with its source boundary.",
                    ("residue.provenance.preserve", "residue.form.record", "capsule.state_delta"))

        if action == "workbench.weave":
            bench = self._entity(db, world_id, target_id, "workbench")
            residue_ids = data.get("residue_ids")
            if not isinstance(residue_ids, list) or not residue_ids or not all(isinstance(x, str) for x in residue_ids):
                raise WorldError("workbench.weave requires a non-empty data.residue_ids list")
            if len(residue_ids) != len(set(residue_ids)):
                raise WorldError("workbench residue IDs must be unique")
            residues = []
            for residue_id in residue_ids:
                residue = self._entity(db, world_id, residue_id, "residue")
                if residue.get("captured_by_event") not in causes:
                    raise WorldError(f"residue {residue_id!r} must be a direct causal parent of the workbench event")
                residues.append(residue)
            field = compose_structural_field(residues)
            bench["revision"] = int(bench.get("revision", 0)) + 1
            bench["latest_field"] = field
            bench["last_event"] = event_id
            self._write_state(db, world_id, target_id, bench)
            return ({target_id: bench},
                    f"{actor_id} composes {len(residues)} witnessed residues by recorded form.",
                    ("workbench.provenance.partition", "workbench.form.project", "capsule.state_delta", "causal.link"))

        if action == "sow_seed":
            seed = self._entity(db, world_id, target_id, "seed")
            if seed["status"] != "carried":
                raise WorldError("only a carried seed can be sown")
            seed.update(status="planted", planted_by_event=event_id, planted_by=actor_id)
            self._write_state(db, world_id, target_id, seed)
            return ({target_id: seed}, f"{actor_id} plants {target_id}.",
                    ("seed.carried_to_planted", "capsule.state_delta", "causal.link"))

        if action == "water_garden":
            garden = self._entity(db, world_id, target_id, "environment")
            seed_id = data.get("seed_id")
            if not seed_id:
                raise WorldError("water_garden requires data.seed_id")
            seed = self._entity(db, world_id, seed_id, "seed")
            if seed["status"] != "planted":
                raise WorldError("the garden can be watered for this seed only after it is planted")
            if garden.get("moisture") != "dry":
                raise WorldError("the garden is already damp")
            garden.update(moisture="damp", last_water_event=event_id)
            self._write_state(db, world_id, target_id, garden)
            return ({target_id: garden}, f"{actor_id} waters {target_id} for {seed_id}.",
                    ("garden.dry_to_damp", "capsule.state_delta", "causal.link"))

        if action == "advance_day":
            if actor_id != "world:environment":
                raise WorldError("only the environment participant can advance world time")
            garden = self._entity(db, world_id, target_id, "environment")
            seed_id = data.get("seed_id")
            if not seed_id:
                raise WorldError("advance_day requires data.seed_id")
            seed = self._entity(db, world_id, seed_id, "seed")
            garden["day"] = int(garden.get("day", 0)) + 1
            changes = {target_id: garden}
            if seed["status"] == "planted" and garden.get("moisture") == "damp":
                wet_event = garden.get("last_water_event")
                # The caller must explicitly connect the growth transition to its water cause.
                if not wet_event or wet_event not in causes:
                    raise WorldError("growth requires the watering event as a direct causal parent")
                seed.update(status="sprouted", sprouted_on_day=garden["day"], sprouted_by_event=event_id)
                garden.update(moisture="dry", last_water_event=None)
                changes[seed_id] = seed
            self._write_state(db, world_id, target_id, garden)
            if seed_id in changes:
                self._write_state(db, world_id, seed_id, seed)
            return (changes, f"Day {garden['day']} passes in {target_id}.",
                    ("environment.advance_day", "seed.planted_to_sprouted", "capsule.state_delta", "causal.link"))

        raise WorldError(f"unknown world action: {action}")

    def autonomous_turn(self, world_id: str, actor_id: str, *, idempotency_key: str) -> Event | None:
        """Run the seeded local policy; it acts only when a planted seed needs water."""
        with self._connect() as db:
            self._require_participant(db, world_id, actor_id)
            row = db.execute(
                "SELECT kind FROM participants WHERE world_id=? AND participant_id=?", (world_id, actor_id)
            ).fetchone()
            if row["kind"] != "local_agent":
                raise WorldError("autonomous_turn is available only to a local_agent participant")
            garden_row = db.execute(
                "SELECT entity_id, state_json FROM entities WHERE world_id=? AND kind='environment' ORDER BY entity_id LIMIT 1",
                (world_id,),
            ).fetchone()
            if not garden_row:
                return None
            garden = json.loads(garden_row["state_json"])
            if garden.get("moisture") != "dry":
                return None
            seeds = db.execute(
                "SELECT entity_id, state_json FROM entities WHERE world_id=? AND kind='seed' ORDER BY entity_id",
                (world_id,),
            ).fetchall()
            planted = next(((s["entity_id"], json.loads(s["state_json"])) for s in seeds
                            if json.loads(s["state_json"]).get("status") == "planted"), None)
            if not planted:
                return None
            seed_id, seed_state = planted
            return self.apply(
                world_id, actor_id, "water_garden", garden_row["entity_id"],
                causes=[seed_state["planted_by_event"]], idempotency_key=idempotency_key,
                data={"seed_id": seed_id, "policy": "water_planted_seed_in_dry_garden"},
            )

    def get_state(self, world_id: str) -> dict[str, Any]:
        with self._connect() as db:
            world = db.execute("SELECT * FROM worlds WHERE world_id=?", (world_id,)).fetchone()
            if not world:
                raise WorldError(f"unknown world: {world_id}")
            participants = db.execute(
                "SELECT * FROM participants WHERE world_id=? ORDER BY participant_id", (world_id,)
            ).fetchall()
            entities = db.execute(
                "SELECT * FROM entities WHERE world_id=? ORDER BY entity_id", (world_id,)
            ).fetchall()
            latest = db.execute(
                "SELECT event_id, sequence, event_hash FROM capsules WHERE world_id=? ORDER BY sequence DESC LIMIT 1",
                (world_id,),
            ).fetchone()
            return {
                "world_id": world["world_id"], "name": world["name"],
                "participants": [
                    {"participant_id": p["participant_id"], "display_name": p["display_name"],
                     "kind": p["kind"], "identity": json.loads(p["identity_json"])} for p in participants
                ],
                "entities": {
                    e["entity_id"]: {"kind": e["kind"], "state": json.loads(e["state_json"])}
                    for e in entities
                },
                "head": dict(latest) if latest else None,
            }

    def events(self, world_id: str) -> list[Event]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM capsules WHERE world_id=? ORDER BY sequence", (world_id,)
            ).fetchall()
            return [self._row_to_event(db, row) for row in rows]

    def causal_ancestors(self, world_id: str, event_id: str) -> list[Event]:
        with self._connect() as db:
            rows = db.execute(
                """WITH RECURSIVE ancestors(event_id) AS (
                       SELECT parent_event_id FROM causal_edges
                       WHERE world_id=? AND child_event_id=?
                       UNION
                       SELECT e.parent_event_id FROM causal_edges e
                       JOIN ancestors a ON e.child_event_id=a.event_id
                       WHERE e.world_id=?
                   )
                   SELECT c.* FROM capsules c JOIN ancestors a USING(event_id)
                   WHERE c.world_id=? ORDER BY c.sequence""",
                (world_id, event_id, world_id, world_id),
            ).fetchall()
            return [self._row_to_event(db, row) for row in rows]

    def verify(self, world_id: str) -> dict[str, Any]:
        """Verify event hash chain, event sequence, and backward-only causal edges."""
        events = self.events(world_id)
        errors: list[str] = []
        expected_previous: str | None = None
        by_id = {event.event_id: event for event in events}
        for position, event in enumerate(events, start=1):
            if event.sequence != position:
                errors.append(f"sequence gap at {event.event_id}: got {event.sequence}, expected {position}")
            if event.previous_hash != expected_previous:
                errors.append(f"hash-chain predecessor mismatch at {event.event_id}")
            material = self._event_material(event)
            if _hash(material) != event.event_hash:
                errors.append(f"event hash mismatch at {event.event_id}")
            for cause in event.causes:
                parent = by_id.get(cause)
                if not parent or parent.sequence >= event.sequence:
                    errors.append(f"invalid causal edge {cause} -> {event.event_id}")
            with self._connect() as db:
                stored_causes = tuple(r[0] for r in db.execute(
                    "SELECT parent_event_id FROM causal_edges WHERE world_id=? AND child_event_id=? ORDER BY parent_event_id",
                    (world_id, event.event_id),
                ).fetchall())
            if set(stored_causes) != set(event.causes):
                errors.append(f"causal edge record mismatch at {event.event_id}")
            expected_previous = event.event_hash
        return {"ok": not errors, "event_count": len(events), "head_hash": expected_previous, "errors": errors}

    def _commit_event(
        self, db: sqlite3.Connection, *, world_id: str, actor_id: str, action: str,
        target_id: str | None, data: Mapping[str, Any], causes: Iterable[str],
        idempotency_key: str, content: str, rules: Iterable[str], echo: Mapping[str, Any],
        anchor: str, mirror: str, created_at: str, event_id: str | None = None,
        request_hash: str | None = None,
    ) -> Event:
        last = db.execute(
            "SELECT sequence, event_id, event_hash FROM capsules WHERE world_id=? ORDER BY sequence DESC LIMIT 1",
            (world_id,),
        ).fetchone()
        sequence = (last["sequence"] + 1) if last else 1
        previous_hash = last["event_hash"] if last else None
        event_id = event_id or "evt_" + hashlib.sha256(f"{world_id}\0{actor_id}\0{idempotency_key}".encode()).hexdigest()[:24]
        parent_ids = tuple(causes)
        event_json = {"action": action, "target_id": target_id, "data": dict(data), "causes": parent_ids}
        rules_tuple = tuple(rules)
        material = {
            "world_id": world_id, "sequence": sequence, "event_id": event_id, "actor_id": actor_id,
            "event": event_json, "created_at": created_at, "anchor": anchor, "mirror": mirror,
            "content": content, "rules": rules_tuple, "echo": dict(echo), "previous_hash": previous_hash,
        }
        event_hash = _hash(material)
        if request_hash is None:
            request_hash = _hash({"action": action, "target_id": target_id, "data": dict(data)})
        db.execute(
            """INSERT INTO capsules
               (world_id,sequence,event_id,actor_id,action,target_id,event_json,created_at,anchor,mirror,
                content,rules_json,echo_json,previous_hash,event_hash,idempotency_key,request_hash)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (world_id, sequence, event_id, actor_id, action, target_id, _json(event_json), created_at,
             anchor, mirror, content, _json(rules_tuple), _json(echo), previous_hash, event_hash,
             idempotency_key, request_hash),
        )
        for parent_id in parent_ids:
            db.execute("INSERT INTO causal_edges VALUES (?,?,?)", (world_id, parent_id, event_id))
        return Event(world_id, sequence, event_id, actor_id, action, target_id, dict(data), parent_ids,
                     created_at, anchor, mirror, content, rules_tuple, dict(echo), previous_hash, event_hash)

    @staticmethod
    def _event_material(event: Event) -> dict[str, Any]:
        return {
            "world_id": event.world_id, "sequence": event.sequence, "event_id": event.event_id,
            "actor_id": event.actor_id,
            "event": {"action": event.action, "target_id": event.target_id,
                      "data": event.data, "causes": event.causes},
            "created_at": event.created_at, "anchor": event.anchor, "mirror": event.mirror,
            "content": event.content, "rules": event.rules, "echo": event.echo,
            "previous_hash": event.previous_hash,
        }

    def _row_to_event(self, db: sqlite3.Connection, row: sqlite3.Row) -> Event:
        event_json = json.loads(row["event_json"])
        causes = tuple(event_json["causes"])
        return Event(
            row["world_id"], row["sequence"], row["event_id"], row["actor_id"], row["action"],
            row["target_id"], event_json["data"], causes, row["created_at"], row["anchor"],
            row["mirror"], row["content"], tuple(json.loads(row["rules_json"])),
            json.loads(row["echo_json"]), row["previous_hash"], row["event_hash"],
        )

    @staticmethod
    def _require_participant(db: sqlite3.Connection, world_id: str, actor_id: str) -> None:
        if not db.execute(
            "SELECT 1 FROM participants WHERE world_id=? AND participant_id=?", (world_id, actor_id)
        ).fetchone():
            raise WorldError(f"unknown participant {actor_id!r} in world {world_id!r}")

    @staticmethod
    def _entity(db: sqlite3.Connection, world_id: str, entity_id: str, expected_kind: str) -> dict[str, Any]:
        row = db.execute(
            "SELECT kind, state_json FROM entities WHERE world_id=? AND entity_id=?", (world_id, entity_id)
        ).fetchone()
        if not row:
            raise WorldError(f"unknown entity: {entity_id}")
        if row["kind"] != expected_kind:
            raise WorldError(f"entity {entity_id!r} must have kind {expected_kind!r}")
        return json.loads(row["state_json"])

    @staticmethod
    def _write_state(db: sqlite3.Connection, world_id: str, entity_id: str, state: Mapping[str, Any]) -> None:
        db.execute("UPDATE entities SET state_json=? WHERE world_id=? AND entity_id=?", (_json(state), world_id, entity_id))

