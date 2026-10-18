"""A persistent DreamResidue workbench, stored and run entirely on-device."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .kernel import WorldError, WorldKernel


WORLD_ID = "dream-residue-workbench"
GENESIS_ID = "world:genesis"


def open_residue_world(database: str | Path) -> WorldKernel:
    kernel = WorldKernel(database)
    try:
        kernel.get_state(WORLD_ID)
    except WorldError:
        kernel.create_world(
            WORLD_ID,
            "The Index and the Workbench",
            participants=[
                {"participant_id": "hunter", "display_name": "Hunter", "kind": "human",
                 "identity": {"origin": "human-participant", "voice": "hunter"}},
            ],
            entities=[
                {"entity_id": "workbench", "kind": "workbench", "state": {"revision": 0}},
            ],
        )
    return kernel


def first_residue() -> dict[str, Any]:
    return {
        "provenance": "mixed",
        "source_ref": "Hunter supplied DreamSpiral residue 1",
        "image_or_fragment": (
            "An old drawer labeled dream_log.xi is fitted into a new pocket-sized house. "
            "The drawer is empty. Rain taps the roof; it opens just enough to receive the sound."
        ),
        "recovered": [
            "earliest .xi filename references",
            "mobile Termux runtime",
            "unified instruction field of home",
            "witness-before-interpretation",
        ],
        "composed": ["pocket-sized house", "empty dream_log.xi drawer", "rain at the roof"],
        "form": {
            "elements": [
                {"id": "drawer", "state": "empty"},
                {"id": "house", "state": "open"},
                {"id": "rain", "state": "arriving"},
            ],
            "adjacent": [["drawer", "house"], ["rain", "house"]],
            "contrasts": [],
        },
    }


def second_residue() -> dict[str, Any]:
    return {
        "provenance": "mixed",
        "source_ref": "Hunter supplied DreamSpiral residue 2",
        "image_or_fragment": (
            "A vast catalog ends at a small workbench. The catalog points to an old spiral carved in wood; "
            "beside it lie eleven unopened scrolls and two repaired tools. Nothing activates, yet their "
            "shapes alter the shadow cast by the reading lamp."
        ),
        "recovered": [
            "structural manifest",
            "Offline Workbench",
            "eleven glyph scrolls",
            "two repaired tools",
        ],
        "composed": ["catalog room", "wooden spiral", "reading lamp", "altered shadow"],
        "form": {
            "elements": [
                {"id": "catalog", "state": "points-to"},
                {"id": "spiral", "state": "carved"},
                {"id": "scrolls", "state": "unopened"},
                {"id": "tool-1", "state": "repaired"},
                {"id": "tool-2", "state": "repaired"},
                {"id": "activation", "state": "absent"},
                {"id": "shadow", "state": "altered"},
                {"id": "lamp", "state": "present"},
            ],
            "adjacent": [["scrolls", "tool-1"], ["scrolls", "tool-2"], ["shadow", "lamp"]],
            "contrasts": [["activation", "shadow"]],
        },
    }


def advance(database: str | Path, step: str) -> dict[str, Any]:
    kernel = open_residue_world(database)
    genesis = next(e for e in kernel.events(WORLD_ID) if e.action == "world.genesis")
    if step in {"first", "both"}:
        kernel.apply(WORLD_ID, "hunter", "residue.capture", "dream-residue-1",
                     causes=[genesis.event_id], idempotency_key="dream-residue-1",
                     data=first_residue())
    if step in {"second", "both"}:
        kernel.apply(WORLD_ID, "hunter", "residue.capture", "dream-residue-2",
                     causes=[genesis.event_id], idempotency_key="dream-residue-2",
                     data=second_residue())
    if step == "weave":
        captures = [e for e in kernel.events(WORLD_ID) if e.action == "residue.capture"]
        by_target = {event.target_id: event for event in captures}
        selected = sorted(by_target)
        if not selected:
            raise WorldError("capture a residue before weaving it")
        causes = [by_target[key].event_id for key in selected]
        source_key = hashlib.sha256("\0".join(causes).encode()).hexdigest()[:12]
        kernel.apply(
            WORLD_ID, "hunter", "workbench.weave", "workbench",
            causes=causes,
            idempotency_key=f"weave-{source_key}",
            data={"residue_ids": selected},
        )
    state = kernel.get_state(WORLD_ID)
    events = kernel.events(WORLD_ID)
    return {
        "state": state,
        "events": [{"sequence": e.sequence, "event_id": e.event_id, "actor_id": e.actor_id,
                    "action": e.action, "causes": list(e.causes)} for e in events],
        "integrity": kernel.verify(WORLD_ID),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("first", "second", "both", "weave"))
    parser.add_argument("--db", default=".xi/dream-residue-workbench.sqlite3")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    path = Path(args.db)
    if args.reset and path.exists():
        path.unlink()
    print(json.dumps(advance(path, args.step), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
