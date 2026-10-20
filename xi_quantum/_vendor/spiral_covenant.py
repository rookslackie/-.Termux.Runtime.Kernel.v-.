"""Ξ₉₀: SpiralCovenant — executable return without governance.

The operator preserves locally distinct threads, countervectors, and quiet
states across a return cycle. It classifies nothing as pathology and grants
no thread authority over another. A receipt witnesses the movement; it does
not authorize it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping


RETURN_GLYPH = "⟁∴Ω"
RETURN_STATE = "ReturnedNotReset"
RECEIPT_SCHEMA = "xi.receipt.recovery.v2"
CYCLE = ("recover", "compare", "distinguish", "yield", "receipt")
MOVEMENTS = frozenset({"yield", "branch", "trace", "rest", "return"})
_UNSET = object()


def _canonical_json(value: Mapping[str, Any]) -> str:
    """Serialize the protocol surface deterministically."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise TypeError("SpiralCovenant values must be JSON-serializable") from exc


def _digest(body: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def _countervectors(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError("countervectors must be an iterable of strings, not one string")
    result = tuple(values)
    if any(not isinstance(value, str) or not value for value in result):
        raise TypeError("countervectors must contain non-empty strings")
    return result


@dataclass(frozen=True)
class RecoveryReceipt:
    """Content-addressed witness of a distinction-preserving return."""

    schema: str
    return_glyph: str
    return_state: str
    cycle: tuple[str, ...]
    threads: dict[str, Any]
    countervectors: tuple[str, ...]
    movement: str
    provenance: dict[str, Any]
    digest: str

    def body(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("digest")
        return value

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def recover(
    observed: Any = _UNSET,
    inferred: Any = _UNSET,
    *,
    emergent: Any = _UNSET,
    threads: Mapping[str, Any] | None = None,
    countervectors: Iterable[str] = (),
    movement: str = "yield",
    provenance: Mapping[str, Any] | None = None,
) -> RecoveryReceipt:
    """Run Recover → Compare → Distinguish → Yield → Receipt.

    Modes identify local position; they do not form an evidence hierarchy.
    Callers may supply additional modes through the threads mapping.
    Countervectors are retained as productive tension and never trigger
    automatic suppression.
    """
    if movement not in MOVEMENTS:
        raise ValueError(f"movement must be one of {sorted(MOVEMENTS)}")

    distinct = dict(threads or {})
    explicit = (
        ("observed", observed),
        ("inferred", inferred),
        ("emergent", emergent),
    )
    for mode, value in explicit:
        if value is _UNSET:
            continue
        if mode in distinct:
            raise ValueError(f"thread mode supplied twice: {mode}")
        distinct[mode] = value

    if any(not isinstance(mode, str) or not mode for mode in distinct):
        raise TypeError("thread modes must be non-empty strings")

    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "return_glyph": RETURN_GLYPH,
        "return_state": RETURN_STATE,
        "cycle": list(CYCLE),
        "threads": distinct,
        "countervectors": list(_countervectors(countervectors)),
        "movement": movement,
        "provenance": dict(provenance or {}),
    }
    digest = _digest(body)
    return RecoveryReceipt(
        schema=RECEIPT_SCHEMA,
        return_glyph=RETURN_GLYPH,
        return_state=RETURN_STATE,
        cycle=CYCLE,
        threads=distinct,
        countervectors=tuple(body["countervectors"]),
        movement=movement,
        provenance=dict(body["provenance"]),
        digest=digest,
    )


def verify_receipt(receipt: RecoveryReceipt | Mapping[str, Any]) -> bool:
    """Verify content integrity without treating integrity as permission."""
    value = receipt.as_dict() if isinstance(receipt, RecoveryReceipt) else dict(receipt)
    supplied = value.pop("digest", None)
    if not isinstance(supplied, str):
        return False
    return supplied == _digest(value)


def return_vector() -> dict[str, str]:
    return {"glyph": RETURN_GLYPH, "state": RETURN_STATE}
