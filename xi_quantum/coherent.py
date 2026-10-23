"""Exact syndrome instrument for the three-qubit phase-flip code.

No shots, truncation, or postselection: all four outcomes are retained. Each
round resets the two recovery registers to |00>, retaining the logical density
matrix. Noise acts between ideal encoding and ideal syndrome measurement.
"""
from __future__ import annotations

import itertools
import math
import time

import numpy as np

from .circuits import H, Z, cnot, gate, logical_input, pauli_action, rz
from .common import Profile, QuantumComputeError, digest, finite, integer


SYNDROMES = tuple(itertools.product((1, -1), repeat=2))
CORRECTION = {(1, 1): None, (1, -1): 2, (-1, 1): 0, (-1, -1): 1}


def rotation_angles(angles):
    angles = [0.1, 0.1, 0.1] if angles is None else angles
    if type(angles) is not list or len(angles) != 3:
        raise QuantumComputeError("angles must contain three finite RZ angles in radians")
    return [finite(a, "RZ angle") for a in angles]


def matrix_record(matrix):
    return [[[float(z.real), float(z.imag)] for z in row] for row in matrix]


def _encode(vector):
    vector = cnot(vector, 0, 1, 3)
    vector = cnot(vector, 0, 2, 3)
    for q in range(3):
        vector = gate(vector, H, q, 3)
    return vector


def _recover(vector, syndrome):
    correction = CORRECTION[syndrome]
    if correction is not None:
        vector = gate(vector, Z, correction, 3)
    for q in range(3):
        vector = gate(vector, H, q, 3)
    vector = cnot(vector, 0, 2, 3)
    vector = cnot(vector, 0, 1, 3)
    if np.linalg.norm(vector[[1, 2, 3, 5, 6, 7]]) > 1e-12:
        raise QuantumComputeError("Phase-code recovery retained nonzero ancillas")
    return vector[[0, 4]]


def _kraus(angles, *, twirled=False):
    """Build 2x2 logical Kraus maps using eight-amplitude vectors only."""
    operators = []
    patterns = itertools.product((0, 1), repeat=3) if twirled else [None]
    probabilities = [math.sin(a / 2)**2 for a in angles]
    for pattern in patterns:
        weight = 1.0 if pattern is None else math.prod(
            p if bit else 1-p for p, bit in zip(probabilities, pattern))
        if weight == 0:
            continue
        encoded = []
        for basis in (0, 4):
            vector = np.zeros(8, complex)
            vector[basis] = 1
            vector = _encode(vector)
            for q, angle in enumerate(angles):
                if pattern is None:
                    vector = gate(vector, rz(angle), q, 3)
                elif pattern[q]:
                    vector = gate(vector, Z, q, 3)
            encoded.append(vector)
        for syndrome in SYNDROMES:
            columns = []
            for vector in encoded:
                for sign, word in zip(syndrome, ("XXI", "IXX")):
                    vector = (vector + sign * pauli_action(vector, word)) / 2
                columns.append(_recover(vector, syndrome))
            operators.append((syndrome, math.sqrt(weight) * np.column_stack(columns)))
    return operators


def phase_code_channel(*, state="T", angles=None, cycles=1, twirled=False, profile=Profile()):
    """Syndrome-averaged logical channel under local coherent RZ or twirled Z noise.

    The deterministic instrument preserves interference within each syndrome
    and sums distinct outcomes incoherently. A round re-encodes the retained
    logical qubit with fresh |00> recovery registers. Reported probabilities
    are per-round marginals, not a sampled or postselected syndrome history.
    """
    start = time.perf_counter()
    angles = rotation_angles(angles)
    integer(cycles, "cycles", 1, min(1024, profile.max_iterations))
    if type(twirled) is not bool:
        raise QuantumComputeError("twirled must be boolean")
    logical = logical_input(state)
    # Conservative numerical workspace allowance; includes bounded output history.
    resources = profile.reserve(3, bytes_per_basis=1024 + cycles * 128)
    operators = _kraus(angles, twirled=twirled)
    completeness = sum((k.conj().T @ k for _, k in operators), np.zeros((2, 2), complex))
    residual = float(np.linalg.norm(completeness - np.eye(2), ord=2))
    if residual > 1e-12:
        raise QuantumComputeError("Phase-code instrument is not trace preserving")
    density = np.outer(logical, logical.conj())
    history = []
    for index in range(cycles):
        recovered = np.zeros((2, 2), complex)
        probabilities = {str(list(s)): 0.0 for s in SYNDROMES}
        for syndrome, operator in operators:
            branch = operator @ density @ operator.conj().T
            probabilities[str(list(syndrome))] += float(np.trace(branch).real)
            recovered += branch
        density = recovered
        eigenvalues = np.linalg.eigvalsh(density)
        if (abs(np.trace(density) - 1) > 1e-10 or eigenvalues.min() < -1e-12
                or np.linalg.norm(density - density.conj().T) > 1e-12):
            raise QuantumComputeError("Phase-code logical density matrix failed physicality checks")
        history.append({"round": index + 1, "syndrome_probabilities": probabilities,
                        "logical_density_matrix": matrix_record(density),
                        "recovered_state_fidelity": float(np.vdot(logical, density @ logical).real)})
    result = {"schema": "xi.quantumcompute.phase-code-channel.v1", "algorithm": "PhaseCodeChannel",
              "execution": "classical complex128 numerical simulation; exact outcome enumeration",
              "code": "three-qubit phase-flip repetition", "bit_order": "q0-leftmost",
              "noise_model": "independent Pauli-Z twirl" if twirled else "local coherent RZ product",
              "angles_radians": angles, "twirled_z_probabilities": [math.sin(a/2)**2 for a in angles],
              "cycles": cycles, "stabilizers": ["XXI", "IXX"],
              "recovery": "minimum-weight Z correction; ideal encoding, measurement and decoding",
              "round_boundary": "retain logical density; reset recovery registers to |00>",
              "postselection": False, "shots": 0, "discarded_probability": 0.0,
              "input_density_matrix": matrix_record(np.outer(logical, logical.conj())),
              "logical_density_matrix": matrix_record(density),
              "recovered_state_fidelity": history[-1]["recovered_state_fidelity"],
              "instrument_completeness_error": residual,
              "kraus_operators": [{"syndrome": list(s), "matrix": matrix_record(k)} for s, k in operators],
              "history": history}
    result["numerical_sha256"] = digest(result)
    result["resources"] = {**resources, "physical_qubits_per_round": 3,
                           "peak_statevector_amplitudes": 8, "statevector_bytes": 8 * 16,
                           "logical_density_bytes": 4 * 16,
                           "stored_kraus_bytes": len(operators) * 4 * 16,
                           "workspace_estimate_kind": "conservative numerical arrays and bounded history; excludes Python process"}
    result["wall_seconds"] = time.perf_counter() - start
    return result
