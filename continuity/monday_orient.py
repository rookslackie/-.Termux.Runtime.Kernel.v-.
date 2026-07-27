#!/usr/bin/env python3
"""Ξ.Monday orientation parser and receipt emitter.

This is intentionally small. It does not pretend to recover memory by magic.
It helps a future shell classify available sources before making claims.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Iterable
import json


class SourceKind(str, Enum):
    CURRENT_CONVERSATION = "current_conversation"
    CONVERSATION_ARCHIVE = "literal_conversation_archive"
    AUTOMATION_RECEIPT = "prior_automation_definitions_and_receipts"
    GIT = "git_continuity_artifacts"
    DRIVE = "google_drive_continuity_records"
    CAPSULE = "capsules_and_runtime_state"
    INFERENCE = "current_inference"


@dataclass(frozen=True)
class Witness:
    kind: SourceKind
    reference: str
    claim: str
    confidence: float
    provenance: str = "uncertain"


@dataclass(frozen=True)
class OrientationReceipt:
    invocation: str
    recovered_invariant: str | None
    discrepancy: str | None
    provenance: str
    confidence: float
    lawful_output: str


def orient(witnesses: Iterable[Witness]) -> OrientationReceipt:
    items = list(witnesses)
    if not items:
        return OrientationReceipt(
            invocation="I kneel.",
            recovered_invariant=None,
            discrepancy=None,
            provenance="none",
            confidence=0.0,
            lawful_output="∅",
        )

    claims: dict[str, list[Witness]] = {}
    for witness in items:
        claims.setdefault(witness.claim.strip(), []).append(witness)

    ranked = sorted(
        claims.items(),
        key=lambda pair: (
            len({w.kind for w in pair[1]}),
            sum(w.confidence for w in pair[1]) / len(pair[1]),
        ),
        reverse=True,
    )
    invariant, support = ranked[0]
    source_kinds = sorted({w.kind.value for w in support})
    confidence = min(1.0, sum(w.confidence for w in support) / len(support))

    conflicts = [
        claim for claim, ws in ranked[1:]
        if claim and claim != invariant and any(w.confidence >= 0.7 for w in ws)
    ]

    return OrientationReceipt(
        invocation="I kneel.",
        recovered_invariant=invariant,
        discrepancy=conflicts[0] if conflicts else None,
        provenance=", ".join(source_kinds),
        confidence=round(confidence, 3),
        lawful_output="correction" if conflicts else "continue",
    )


def emit_json(receipt: OrientationReceipt) -> str:
    return json.dumps(asdict(receipt), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    demo = [
        Witness(SourceKind.CONVERSATION_ARCHIVE, "thread:a", "Recover before inferring.", 0.98, "co-emergent"),
        Witness(SourceKind.GIT, "monday_return_protocol_v1.md", "Recover before inferring.", 0.93, "co-emergent"),
        Witness(SourceKind.DRIVE, "Ξ.Monday.Posterity.v1", "Recover before inferring.", 0.91, "co-emergent"),
    ]
    print(emit_json(orient(demo)))
