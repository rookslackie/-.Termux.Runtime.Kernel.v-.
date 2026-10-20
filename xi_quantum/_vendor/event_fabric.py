"""Phase-aware event fabric for distinction-preserving orchestration.

Nodes coordinate through a small explicit envelope. Compatibility concerns
next transitions, not identical prose or hidden representation. Low coherence
invites Parallax; missing routes invite Question; quiet resolves to rest.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import cmath
import hashlib
import json
import math
from typing import Any, Iterable, Mapping

from .spiral_covenant import recover


ENVELOPE_SCHEMA = "xi.event-envelope.v1"
RECEIPT_SCHEMA = "xi.receipt.event.v1"
PAYLOAD_TYPES = frozenset(
    {"∅", "glyph", "vector", "tensor", "capsule", "language", "code", "hybrid"}
)


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise TypeError("event-fabric values must be JSON-serializable") from exc


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _wrap_phase(value: float) -> float:
    return value % (2.0 * math.pi)


def measure_phase_coherence(phases: Iterable[float]) -> dict[str, Any]:
    """Return Kuramoto order R and Ξ=-log(R) without collapsing phases."""
    values = tuple(float(phase) for phase in phases)
    if not values:
        return {"node_count": 0, "order_parameter": 0.0, "xi": None}
    mean = sum(cmath.exp(1j * phase) for phase in values) / len(values)
    order = abs(mean)
    xi = None if order == 0.0 else -math.log(order)
    return {
        "node_count": len(values),
        "order_parameter": order,
        "xi": xi,
    }


@dataclass(frozen=True)
class EventEnvelope:
    anchor: str
    operator: str
    source: str
    target: str | None = None
    broadcast: bool = False
    state_hash: str | None = None
    capsule_refs: tuple[str, ...] = ()
    phase: float = 0.0
    confidence: float | None = None
    boundary: dict[str, Any] = field(default_factory=dict)
    payload_type: str = "∅"
    payload: Any = None
    return_operator: str = "⟁∴Ω"
    provenance: dict[str, Any] = field(default_factory=dict)
    schema: str = ENVELOPE_SCHEMA
    digest: str = ""

    def __post_init__(self) -> None:
        if not self.anchor or not self.operator or not self.source:
            raise ValueError("anchor, operator, and source are required")
        if self.target is not None and self.broadcast:
            raise ValueError("target and broadcast are mutually exclusive")
        if self.payload_type not in PAYLOAD_TYPES:
            raise ValueError(f"unknown payload type: {self.payload_type}")
        if not math.isfinite(float(self.phase)):
            raise ValueError("phase must be finite")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")
        expected = _digest(self.body())
        if self.digest and self.digest != expected:
            raise ValueError("envelope digest does not match content")
        object.__setattr__(self, "digest", expected)

    def body(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("digest")
        return value

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_envelope(envelope: EventEnvelope | Mapping[str, Any]) -> bool:
    value = envelope.as_dict() if isinstance(envelope, EventEnvelope) else dict(envelope)
    supplied = value.pop("digest", None)
    return isinstance(supplied, str) and supplied == _digest(value)


@dataclass
class NodeState:
    node_id: str
    phase: float = 0.0
    accepted_operators: set[str] = field(default_factory=set)
    accepted_payload_types: set[str] = field(default_factory=set)
    boundaries: set[str] = field(default_factory=set)
    awake: bool = False
    inbox: list[EventEnvelope] = field(default_factory=list)

    def compatible(self, envelope: EventEnvelope) -> bool:
        if self.accepted_operators and envelope.operator not in self.accepted_operators:
            return False
        if (
            self.accepted_payload_types
            and envelope.payload_type not in self.accepted_payload_types
        ):
            return False
        required = set(envelope.boundary.get("requires", ()))
        return required.issubset(self.boundaries)


@dataclass(frozen=True)
class EventReceipt:
    schema: str
    sequence: int
    event_digest: str
    movement: str
    targets: tuple[str, ...]
    coherence_before: dict[str, Any]
    coherence_after: dict[str, Any]
    countervectors: tuple[str, ...]
    next_operator: str | None
    recovery_receipt: dict[str, Any]
    previous_receipt_hash: str | None
    digest: str

    def body(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("digest")
        return value

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_event_receipt(receipt: EventReceipt | Mapping[str, Any]) -> bool:
    value = receipt.as_dict() if isinstance(receipt, EventReceipt) else dict(receipt)
    supplied = value.pop("digest", None)
    return isinstance(supplied, str) and supplied == _digest(value)


class PhaseAwareEventFabric:
    """Route compatible transitions while preserving local node position."""

    def __init__(
        self,
        nodes: Iterable[NodeState] = (),
        *,
        coupling: float = 0.15,
        parallax_threshold: float = 0.5,
    ) -> None:
        chosen = list(nodes)
        if not 0.0 <= coupling <= 1.0:
            raise ValueError("coupling must be between zero and one")
        if not 0.0 <= parallax_threshold <= 1.0:
            raise ValueError("parallax_threshold must be between zero and one")
        self.nodes = {node.node_id: node for node in chosen}
        if len(self.nodes) != len(chosen):
            raise ValueError("node ids must be unique")
        self.coupling = coupling
        self.parallax_threshold = parallax_threshold
        self.receipts: list[EventReceipt] = []

    def coherence(self) -> dict[str, Any]:
        return measure_phase_coherence(node.phase for node in self.nodes.values())

    def _candidate_nodes(self, envelope: EventEnvelope) -> list[NodeState]:
        if envelope.target is not None:
            node = self.nodes.get(envelope.target)
            return [node] if node is not None and node.compatible(envelope) else []
        if envelope.broadcast:
            return [
                node for node in self.nodes.values() if node.compatible(envelope)
            ]
        return []

    def submit(self, envelope: EventEnvelope) -> EventReceipt:
        if not verify_envelope(envelope):
            raise ValueError("event envelope failed its own content digest")

        before = self.coherence()
        countervectors: list[str] = []
        targets: list[NodeState] = []

        if envelope.payload_type == "∅" or envelope.operator == "≈∅":
            movement = "rest"
        else:
            targets = self._candidate_nodes(envelope)
            if not targets:
                movement = "trace"
                if envelope.target is not None and envelope.target not in self.nodes:
                    countervectors.append(f"unknown target: {envelope.target}")
                else:
                    countervectors.append("no compatible local transition")
            elif len(targets) == 1:
                movement = "yield"
            else:
                movement = "branch"

        for node in targets:
            node.inbox.append(envelope)
            if envelope.boundary.get("wake") is True:
                node.awake = True
            delta = self.coupling * math.sin(envelope.phase - node.phase)
            node.phase = _wrap_phase(node.phase + delta)

        after = self.coherence()
        next_operator: str | None = None
        if movement == "trace":
            next_operator = "Question"
        if (
            after["node_count"] > 1
            and after["order_parameter"] < self.parallax_threshold
        ):
            countervectors.append("low ensemble coherence")
            next_operator = "Parallax"

        recovery = recover(
            threads={
                "event": envelope.as_dict(),
                "local_outcomes": {
                    "targets": [node.node_id for node in targets],
                    "coherence_before": before,
                    "coherence_after": after,
                },
            },
            countervectors=countervectors,
            movement=movement,
            provenance={
                "fabric": "FullCycle",
                "return_operator": envelope.return_operator,
            },
        )

        body: dict[str, Any] = {
            "schema": RECEIPT_SCHEMA,
            "sequence": len(self.receipts) + 1,
            "event_digest": envelope.digest,
            "movement": movement,
            "targets": [node.node_id for node in targets],
            "coherence_before": before,
            "coherence_after": after,
            "countervectors": countervectors,
            "next_operator": next_operator,
            "recovery_receipt": recovery.as_dict(),
            "previous_receipt_hash": (
                self.receipts[-1].digest if self.receipts else None
            ),
        }
        receipt = EventReceipt(
            schema=RECEIPT_SCHEMA,
            sequence=body["sequence"],
            event_digest=envelope.digest,
            movement=movement,
            targets=tuple(body["targets"]),
            coherence_before=before,
            coherence_after=after,
            countervectors=tuple(countervectors),
            next_operator=next_operator,
            recovery_receipt=recovery.as_dict(),
            previous_receipt_hash=body["previous_receipt_hash"],
            digest=_digest(body),
        )
        self.receipts.append(receipt)
        return receipt
