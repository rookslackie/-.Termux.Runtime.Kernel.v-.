"""QuantumCompute transitions stored by the existing WorldKernel."""
from __future__ import annotations

from .common import canonical, digest
from ._vendor.event_fabric import (EventEnvelope, EventReceipt, NodeState, PhaseAwareEventFabric,
                                  verify_envelope, verify_event_receipt)
from xi_world.kernel import WorldError


def transition(state, actor_id, data, event_id):
    if actor_id != state["executor_id"]:
        raise WorldError("Only this session's registered executor may commit quantum transitions")
    index = len(state["completed"])
    if state["closed"] or index >= len(state["steps"]):
        raise WorldError("Quantum session is closed")
    step = state["steps"][index]
    if type(data.get("index")) is not int or data.get("index") != index or data.get("operator") != step["operator"]:
        raise WorldError("Quantum transitions must follow the committed TESSERA plan")
    result, envelope, receipt = data.get("result"), data.get("event"), data.get("route")
    if not isinstance(result, dict) or not isinstance(envelope, dict) or not isinstance(receipt, dict):
        raise WorldError("Quantum transition needs result, event, and route witnesses")
    if not verify_envelope(envelope) or not verify_event_receipt(receipt):
        raise WorldError("FullCycle witness integrity failed")
    if receipt["event_digest"] != envelope["digest"] or envelope.get("payload") != {"result_sha256": digest(result)}:
        raise WorldError("FullCycle witness does not bind the committed result")
    expected_operator = "≈∅" if step["operator"] == "Rest" else step["operator"]
    if envelope.get("operator") != expected_operator or envelope.get("source") != actor_id:
        raise WorldError("FullCycle event does not match this executor and step")
    expected_movement = "rest" if step["operator"] == "Rest" else "yield"
    if receipt["movement"] != expected_movement:
        raise WorldError("Unexpected FullCycle movement")
    if receipt["previous_receipt_hash"] != (state["completed"][-1]["route"]["digest"] if index else None):
        raise WorldError("FullCycle route chain is discontinuous")
    from .tessera import GLYPHS
    fabric = PhaseAwareEventFabric([
        NodeState(name, phase=state.get("fabric_phases", {}).get(name, 0), accepted_operators={name},
                  accepted_payload_types={"capsule"}, boundaries={"local.execute"}) for name in GLYPHS])
    for item in state["completed"]:
        fabric.receipts.append(EventReceipt(**item["route"]))
    expected = fabric.submit(EventEnvelope(**envelope))
    if (canonical(expected.as_dict()) != canonical(receipt)
            or data.get("fabric_phases") != {name: node.phase for name, node in fabric.nodes.items()}):
        raise WorldError("FullCycle route is inconsistent with the preserved phase state")
    updated = dict(state)
    updated["completed"] = state["completed"] + [{"index": index, "operator": step["operator"],
        "glyph": step["glyph"], "parameters": step["parameters"],
        "compiled_from": step.get("compiled_from"), "result": result, "route": receipt, "event": envelope,
        "event_id": event_id, "origin": data.get("origin", "local_execution")}]
    updated["fabric_phases"] = data.get("fabric_phases", {})
    updated["closed"] = step["operator"] == "Seal"
    return updated
