"""Run a small local glyph-chip cycle against a durable SQLite ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runtime import FIELD_ACTOR_ID, FIELD_WORLD_ID, bootstrap_field


def run(database: str | Path, *, world_id: str = FIELD_WORLD_ID) -> dict:
    field = bootstrap_field(database, world_id=world_id, qubits=3)
    # Replaying the deterministic keys recovers completed steps and completes a
    # partially interrupted cycle without duplicating already committed capsules.
    # The chip YAML supplies topology, not an executable schedule. H then CNOT is
    # the minimal mathematically valid GHZ-family realization.
    field.execute("reference", idempotency_key="cycle-0-reference")
    field.execute("hadamard", parameters={"qubit": 0}, idempotency_key="cycle-0-superpose")
    field.execute("cnot", parameters={"control": 0, "target": 1}, idempotency_key="cycle-0-entangle-1")
    field.execute("cnot", parameters={"control": 0, "target": 2}, idempotency_key="cycle-0-entangle-2")
    field.execute("phase", parameters={"angle": 3.141592653589793}, idempotency_key="cycle-0-relative-phase")
    event = field.execute("witness", parameters={"basis": "x", "seed": 417}, idempotency_key="cycle-0-witness")
    field.execute("close", idempotency_key="cycle-0-close")
    return {
        "world_id": world_id,
        "state": field.state(),
        "last_receipt": field.receipt(event),
        "event_count": len(field.kernel.events(world_id)),
        "integrity": field.kernel.verify(world_id),
        "execution_class": "local exact sparse state-vector model; not physical quantum hardware",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=".xi/glyph-field.sqlite3", help="local SQLite field ledger")
    parser.add_argument("--world", default=FIELD_WORLD_ID)
    args = parser.parse_args()
    print(json.dumps(run(Path(args.db), world_id=args.world), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
