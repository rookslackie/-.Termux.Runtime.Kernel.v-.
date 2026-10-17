"""Repeatable CoreOrigin World demo; each command uses a local SQLite file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .kernel import WorldError, WorldKernel


def open_seed_world(database: str | Path) -> WorldKernel:
    kernel = WorldKernel(database)
    try:
        kernel.get_state("core-origin-garden")
    except WorldError:
        kernel.create_world(
            "core-origin-garden",
            "The First Garden",
            participants=[
                {"participant_id": "hunter", "display_name": "Hunter", "kind": "human",
                 "identity": {"origin": "human-participant", "voice": "hunter"}},
                {"participant_id": "axiom", "display_name": "Axiom", "kind": "local_agent",
                 "identity": {"origin": "seeded-local-policy", "policy": "water planted seed in dry garden"}},
                {"participant_id": "world:environment", "display_name": "Garden Weather", "kind": "system",
                 "identity": {"origin": "world-rule", "role": "environment"}},
            ],
            entities=[
                {"entity_id": "garden", "kind": "environment", "state": {"day": 0, "moisture": "dry"}},
                {"entity_id": "sunflower-1", "kind": "seed", "state": {"species": "sunflower", "status": "carried"}},
            ],
        )
    return kernel


def run_demo(database: str | Path) -> dict:
    kernel = open_seed_world(database)
    state = kernel.get_state("core-origin-garden")
    if state["entities"]["sunflower-1"]["state"]["status"] == "carried":
        kernel.apply("core-origin-garden", "hunter", "sow_seed", "sunflower-1", idempotency_key="hunter-sows-first-seed")
    agent_event = kernel.autonomous_turn("core-origin-garden", "axiom", idempotency_key="axiom-first-watering")
    state = kernel.get_state("core-origin-garden")
    if state["entities"]["sunflower-1"]["state"]["status"] == "planted":
        water_id = state["entities"]["garden"]["state"]["last_water_event"]
        kernel.apply(
            "core-origin-garden", "world:environment", "advance_day", "garden",
            causes=[water_id], idempotency_key="environment-first-day",
            data={"seed_id": "sunflower-1"},
        )
    return {"state": kernel.get_state("core-origin-garden"),
            "events": [event.__dict__ for event in kernel.events("core-origin-garden")],
            "causal_ancestors": [e.event_id for e in kernel.causal_ancestors(
                "core-origin-garden", kernel.events("core-origin-garden")[-1].event_id)],
            "integrity": kernel.verify("core-origin-garden"),
            "autonomous_action": agent_event.event_id if agent_event else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=".xi/core-origin-world.sqlite3", help="local SQLite world file")
    parser.add_argument("--reset", action="store_true", help="start a fresh demo database")
    args = parser.parse_args()
    path = Path(args.db)
    if args.reset and path.exists():
        path.unlink()
    result = run_demo(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
