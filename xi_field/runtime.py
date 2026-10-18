"""Field runtime integrated with the existing persistent Xi world ledger."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from xi_world.kernel import Event, WorldError, WorldKernel
from .topology import chip_topology


FIELD_WORLD_ID = "quantum-field-local"
FIELD_ENTITY_ID = "glyph-chip"
FIELD_ACTOR_ID = "world:field-runtime"


def bootstrap_field(database: str | Path, *, world_id: str = FIELD_WORLD_ID, qubits: int = 3,
                    human_id: str = "hunter", human_name: str = "Hunter") -> "FieldRuntime":
    """Create the local field once; subsequent calls recover it from SQLite."""
    from .operators import initial_state

    kernel = WorldKernel(database)
    _, topology_hash = chip_topology()
    try:
        kernel.get_state(world_id)
    except WorldError:
        kernel.create_world(
            world_id, "Xi Glyph Field",
            participants=[
                {"participant_id": human_id, "display_name": human_name, "kind": "human",
                 "identity": {"origin": "local-field-participant", "distinct_identity": True}},
                {"participant_id": FIELD_ACTOR_ID, "display_name": "Xi Field Runtime", "kind": "local_runtime",
                 "identity": {"origin": "xi_field.runtime", "operator_grammar": "glyph-chip-v1"}},
            ],
            entities=[{"entity_id": FIELD_ENTITY_ID, "kind": "field_state",
                       "state": {**initial_state(qubits), "topology_sha256": topology_hash}}],
        )
    return FieldRuntime(kernel, world_id=world_id)


class FieldRuntime:
    """Execute local glyph operators as persistent, provenance-bearing capsules."""

    def __init__(self, kernel: WorldKernel, *, world_id: str = FIELD_WORLD_ID):
        self.kernel = kernel
        self.world_id = world_id

    def state(self) -> dict[str, Any]:
        world = self.kernel.get_state(self.world_id)
        try:
            return world["entities"][FIELD_ENTITY_ID]["state"]
        except KeyError as exc:
            raise WorldError(f"field entity {FIELD_ENTITY_ID!r} is absent") from exc

    def execute(self, operator: str, *, actor_id: str = FIELD_ACTOR_ID, idempotency_key: str,
                parameters: Mapping[str, Any] | None = None, causes: list[str] | None = None) -> Event:
        return self.kernel.apply(
            self.world_id, actor_id, "field.operator", FIELD_ENTITY_ID,
            idempotency_key=idempotency_key, causes=causes,
            data={"operator": operator, "parameters": dict(parameters or {})},
        )

    def receipt(self, event: Event) -> dict[str, Any]:
        state_delta = event.echo.get(FIELD_ENTITY_ID, {})
        return {
            "world_id": self.world_id, "sequence": event.sequence, "event_id": event.event_id,
            "actor_id": event.actor_id, "operator": event.data.get("operator"),
            "causes": list(event.causes), "event_hash": event.event_hash,
            "previous_hash": event.previous_hash,
            "echo": {
                "branch_count": len(state_delta.get("branches", [])),
                "closed": state_delta.get("closed"),
                "cycle": state_delta.get("cycle"),
                "operator": state_delta.get("last_operator_receipt"),
            },
        }
