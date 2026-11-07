"""Run a persistent one-fault phase-code recovery path in the local Xi ledger.

This is an exact, bounded state-vector experiment. It demonstrates correction
of one deliberately injected Pauli-Z fault by the three-qubit phase-flip code;
it is not a model of Google's cultivation protocol or physical hardware.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .operators import apply_operator, initial_state
from .runtime import bootstrap_field


WORLD_ID = "quantum-phase-code-local"
FAULT_QUBIT = 1
SYNDROME_SEED = 20261017


def _fidelity(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    """Return pure-state overlap fidelity for the bounded local state vectors."""
    def amplitudes(state: Mapping[str, Any]) -> dict[str, complex]:
        return {bits: complex(*pair) for bits, pair in state["branches"]}

    a, b = amplitudes(left), amplitudes(right)
    overlap = sum(a.get(bits, 0j).conjugate() * value for bits, value in b.items())
    return round(abs(overlap) ** 2, 12)


def _ideal_magic_state() -> dict[str, Any]:
    state = initial_state(3)
    state, _ = apply_operator(state, "hadamard", {"qubit": 0})
    state, _ = apply_operator(state, "t", {"qubit": 0})
    return state


def run(database: str | Path, *, world_id: str = WORLD_ID) -> dict[str, Any]:
    """Prepare, encode, fault, restart, diagnose, correct, and decode once.

    Stable idempotency keys make an interrupted or repeated invocation recover
    already committed work without duplicating capsules.
    """
    field = bootstrap_field(database, world_id=world_id, qubits=3)
    steps = [
        ("reference", {}, "phase-code-reference"),
        ("hadamard", {"qubit": 0}, "magic-prepare-h"),
        ("t", {"qubit": 0}, "magic-prepare-t"),
        ("encode_phase_code", {}, "phase-code-encode"),
        ("inject_z_error", {"qubit": FAULT_QUBIT}, "phase-code-fault"),
    ]
    events = [field.execute(operator, parameters=params, idempotency_key=key) for operator, params, key in steps]

    # This boundary deliberately reconstructs the runtime from the SQLite file.
    field = bootstrap_field(database, world_id=world_id, qubits=3)
    recovery_steps = [
        ("phase_syndrome", {"seed": SYNDROME_SEED}, "phase-code-syndrome"),
        ("correct_z_error", {}, "phase-code-correct"),
        ("decode_phase_code", {}, "phase-code-decode"),
        ("close", {}, "phase-code-close"),
    ]
    events.extend(field.execute(operator, parameters=params, idempotency_key=key)
                  for operator, params, key in recovery_steps)

    final_state = field.state()
    syndrome = next(event for event in events if event.data.get("operator") == "phase_syndrome")
    correction = next(event for event in events if event.data.get("operator") == "correct_z_error")
    return {
        "world_id": world_id,
        "event_count": len(field.kernel.events(world_id)),
        "fault_qubit": FAULT_QUBIT,
        "syndrome": syndrome.echo["glyph-chip"]["last_operator_receipt"]["syndrome"],
        "corrected_qubit": correction.echo["glyph-chip"]["last_operator_receipt"]["corrected_qubit"],
        "recovered_state_fidelity": _fidelity(final_state, _ideal_magic_state()),
        "state_after_restart": True,
        "closed": final_state["closed"],
        "integrity": field.kernel.verify(world_id),
        "execution_class": "local exact sparse state-vector; three-qubit phase-flip code; one injected Z fault",
        "not_claimed": ["Google magic-state cultivation", "physical QEC", "hardware fidelity", "quantum advantage"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=".xi/phase-code.sqlite3", help="local SQLite field ledger")
    parser.add_argument("--world", default=WORLD_ID)
    args = parser.parse_args()
    print(json.dumps(run(Path(args.db), world_id=args.world), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
