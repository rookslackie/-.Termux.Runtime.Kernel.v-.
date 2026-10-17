"""Exact sparse-amplitude operators for a bounded glyph-chip field.

This is a local mathematical execution model, not a physical quantum backend.
The sparse basis representation is exact (up to floating-point arithmetic) and
is intentionally guarded against branch explosion.
"""

from __future__ import annotations

import math
import random
from typing import Any, Mapping


MAX_QUBITS = 12
MAX_BRANCHES = 4096
SQRT_HALF = 1 / math.sqrt(2)


class FieldOperatorError(ValueError):
    """An unsupported or invalid field transition."""


def initial_state(qubits: int) -> dict[str, Any]:
    if not isinstance(qubits, int) or isinstance(qubits, bool) or not 1 <= qubits <= MAX_QUBITS:
        raise FieldOperatorError(f"qubits must be an integer from 1 to {MAX_QUBITS}")
    return {"qubits": qubits, "branches": [["0" * qubits, [1.0, 0.0]]], "closed": False, "cycle": 0}


def _complex_pair(pair: list[float]) -> complex:
    return complex(float(pair[0]), float(pair[1]))


def _canonical(state: Mapping[str, Any], amplitudes: Mapping[str, complex]) -> dict[str, Any]:
    qubits = int(state["qubits"])
    cleaned = {bits: amp for bits, amp in amplitudes.items() if abs(amp) > 1e-14}
    if len(cleaned) > MAX_BRANCHES:
        raise FieldOperatorError(f"operator would exceed the {MAX_BRANCHES}-branch local field limit")
    norm = sum(abs(amp) ** 2 for amp in cleaned.values())
    if not math.isfinite(norm) or abs(norm - 1.0) > 1e-9:
        raise FieldOperatorError(f"operator produced a non-normalized state (norm²={norm})")
    result = dict(state)
    result["branches"] = [
        [bits, [round(amplitudes[bits].real, 15), round(amplitudes[bits].imag, 15)]]
        for bits in sorted(cleaned)
    ]
    return result


def _amplitudes(state: Mapping[str, Any]) -> dict[str, complex]:
    qubits = state.get("qubits")
    branches = state.get("branches")
    if not isinstance(qubits, int) or not isinstance(branches, list) or not branches:
        raise FieldOperatorError("field state must contain qubits and non-empty branches")
    result: dict[str, complex] = {}
    for item in branches:
        if (not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], str)
                or len(item[0]) != qubits or set(item[0]) - {"0", "1"}
                or not isinstance(item[1], list) or len(item[1]) != 2):
            raise FieldOperatorError("invalid sparse branch encoding")
        if item[0] in result:
            raise FieldOperatorError("duplicate branch; run ⋈ compression before execution")
        result[item[0]] = _complex_pair(item[1])
    return result


def _qubit(index: Any, count: int, name: str = "qubit") -> int:
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < count:
        raise FieldOperatorError(f"{name} must be an index from 0 to {count - 1}")
    return index


def _hadamard(amplitudes: Mapping[str, complex], qubit: int) -> dict[str, complex]:
    out: dict[str, complex] = {}
    for bits, amp in amplitudes.items():
        twin = bits[:qubit] + ("1" if bits[qubit] == "0" else "0") + bits[qubit + 1:]
        out[bits] = out.get(bits, 0j) + (amp if bits[qubit] == "0" else -amp) * SQRT_HALF
        out[twin] = out.get(twin, 0j) + amp * SQRT_HALF
    return out


def _cnot(amplitudes: Mapping[str, complex], control: int, target: int) -> dict[str, complex]:
    out: dict[str, complex] = {}
    for bits, amp in amplitudes.items():
        if bits[control] == "1":
            bits = bits[:target] + ("0" if bits[target] == "1" else "1") + bits[target + 1:]
        out[bits] = out.get(bits, 0j) + amp
    return out


def _sample(amplitudes: Mapping[str, complex], seed: int) -> str:
    ordered = sorted(amplitudes.items())
    total = sum(abs(amp) ** 2 for _, amp in ordered)
    if abs(total - 1.0) > 1e-9:
        raise FieldOperatorError("cannot witness a non-normalized state")
    needle = random.Random(seed).random()
    cumulative = 0.0
    for bits, amp in ordered:
        cumulative += abs(amp) ** 2
        if needle < cumulative:
            return bits
    return ordered[-1][0]


def apply_operator(state: Mapping[str, Any], operator: str, parameters: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one explicit operator and return (new_state, operation_receipt)."""
    params = dict(parameters or {})
    count = state.get("qubits")
    amplitudes = _amplitudes(state)
    receipt: dict[str, Any] = {"operator": operator, "branch_count_before": len(amplitudes)}

    if operator == "reference":
        if state.get("closed"):
            raise FieldOperatorError("a closed field must resume before a new reference")
        receipt["meaning"] = "Ψ establishes the observed register boundary"
    elif operator == "compress":
        # Canonicalization merges duplicate basis paths and removes numerical zeroes.
        receipt["meaning"] = "⋈ merges equivalent sparse paths while preserving amplitudes"
    elif operator == "hadamard":
        if state.get("closed"):
            raise FieldOperatorError("closed field; apply resume before another operator")
        q = _qubit(params.get("qubit"), count)
        amplitudes = _hadamard(amplitudes, q)
        receipt.update(qubit=q, meaning="⟐ applies a Hadamard basis relation")
    elif operator == "cnot":
        if state.get("closed"):
            raise FieldOperatorError("closed field; apply resume before another operator")
        control = _qubit(params.get("control"), count, "control")
        target = _qubit(params.get("target"), count, "target")
        if control == target:
            raise FieldOperatorError("control and target must be distinct")
        amplitudes = _cnot(amplitudes, control, target)
        receipt.update(control=control, target=target, meaning="⋈ composes a controlled-X relation")
    elif operator == "phase":
        if state.get("closed"):
            raise FieldOperatorError("closed field; apply resume before another operator")
        angle = params.get("angle")
        if not isinstance(angle, (int, float)) or isinstance(angle, bool) or not math.isfinite(angle):
            raise FieldOperatorError("phase angle must be a finite number of radians")
        pattern = params.get("pattern", "1" * count)
        if not isinstance(pattern, str) or len(pattern) != count or set(pattern) - {"0", "1"}:
            raise FieldOperatorError("phase pattern must be a bitstring matching the register width")
        factor = complex(math.cos(float(angle)), math.sin(float(angle)))
        amplitudes = {bits: amp * factor if bits == pattern else amp for bits, amp in amplitudes.items()}
        receipt.update(angle=float(angle), pattern=pattern, meaning="phase is attached to the selected relational branch")
    elif operator == "t":
        if state.get("closed"):
            raise FieldOperatorError("closed field; apply resume before another operator")
        q = _qubit(params.get("qubit"), count)
        factor = complex(math.cos(math.pi / 4), math.sin(math.pi / 4))
        amplitudes = {bits: amp * factor if bits[q] == "1" else amp for bits, amp in amplitudes.items()}
        receipt.update(qubit=q, angle=math.pi / 4,
                       meaning="T is an explicit non-Clifford phase operator in the ideal local model")
    elif operator == "witness":
        if state.get("closed"):
            raise FieldOperatorError("closed field; apply resume before another operator")
        basis = params.get("basis", "z")
        seed = params.get("seed")
        if basis not in {"z", "x"}:
            raise FieldOperatorError("witness basis must be 'z' or 'x'")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise FieldOperatorError("witness requires an integer seed for reproducible local replay")
        rotated = amplitudes
        if basis == "x":
            for q in range(count):
                rotated = _hadamard(rotated, q)
        outcome = _sample(rotated, seed)
        collapsed = {outcome: 1 + 0j}
        if basis == "x":
            for q in range(count):
                collapsed = _hadamard(collapsed, q)
        amplitudes = collapsed
        receipt.update(basis=basis, seed=seed, outcome=outcome,
                       meaning="∴ records a seeded Born-rule witness and collapses the local state")
    elif operator == "resume":
        if not state.get("closed"):
            raise FieldOperatorError("resume is available only after ⊚ close")
        receipt.update(cycle=int(state.get("cycle", 0)) + 1,
                       meaning="⊚ returns a closed state to the next local cycle")
    elif operator == "close":
        if state.get("closed"):
            raise FieldOperatorError("field is already closed")
        receipt["meaning"] = "⊚ closes this operator cycle into the hash-chained capsule ledger"
    else:
        raise FieldOperatorError(f"unknown glyph-field operator: {operator}")

    new_state = _canonical(state, amplitudes)
    new_state["last_operator_receipt"] = receipt
    if operator == "resume":
        new_state["closed"] = False
        new_state["cycle"] = receipt["cycle"]
    elif operator == "close":
        new_state["closed"] = True
    receipt["branch_count_after"] = len(new_state["branches"])
    receipt["norm_squared"] = round(sum(abs(a) ** 2 for a in _amplitudes(new_state).values()), 12)
    return new_state, receipt
