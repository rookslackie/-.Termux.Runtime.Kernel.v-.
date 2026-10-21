"""Inspectable state-vector circuits and two distinct error-correction codes.

Qubit 0 is the leftmost bit. Snapshots retain amplitudes above 1e-14 and report
the omitted L2 norm. These are classical numerical experiments.
"""
from __future__ import annotations

import math
import random
import time

import numpy as np

from .common import Profile, QuantumComputeError, digest, finite, integer


I = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.diag([1, -1]).astype(complex)
H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
PAULI = {"I": I, "X": X, "Y": Y, "Z": Z}


def gate(vector, unitary, qubit, qubits):
    tensor = np.moveaxis(vector.reshape((2,) * qubits), qubit, 0)
    changed = np.tensordot(unitary, tensor, axes=(1, 0))
    return np.moveaxis(changed, 0, qubit).reshape(-1)


def cnot(vector, control, target, qubits):
    indices = np.arange(len(vector))
    destination = indices ^ (((indices >> (qubits - 1 - control)) & 1) << (qubits - 1 - target))
    result = np.empty_like(vector)
    result[destination] = vector
    return result


def ry(theta):
    return np.array([[math.cos(theta / 2), -math.sin(theta / 2)],
                     [math.sin(theta / 2), math.cos(theta / 2)]], dtype=complex)


def rz(theta):
    return np.diag([np.exp(-0.5j * theta), np.exp(0.5j * theta)])


def pauli_action(vector, word):
    result = vector
    for qubit, letter in enumerate(word):
        if letter != "I":
            result = gate(result, PAULI[letter], qubit, len(word))
    return result


def snapshot(vector):
    qubits = len(vector).bit_length() - 1
    retained = np.abs(vector) > 1e-14
    return {"qubits": qubits, "bit_order": "q0-leftmost", "branches": [
        [format(index, f"0{qubits}b"), [float(value.real), float(value.imag)]]
        for index, value in enumerate(vector) if retained[index]],
        "norm_squared": float(np.vdot(vector, vector).real),
        "omitted_l2_norm": float(np.linalg.norm(vector[~retained]))}


def logical_input(state="T"):
    named = {"zero": [1, 0], "one": [0, 1], "plus": [2**-.5, 2**-.5],
             "minus": [2**-.5, -2**-.5], "T": [2**-.5, (1 + 1j) / 2],
             "y_plus": [2**-.5, 1j * 2**-.5]}
    if isinstance(state, str):
        if state not in named:
            raise QuantumComputeError("Unknown logical input; choose zero, one, plus, minus, T, or y_plus")
        return np.array(named[state], dtype=complex)
    if type(state) is not list or len(state) != 2:
        raise QuantumComputeError("A custom qubit uses two [real, imaginary] amplitude pairs")
    values = []
    for pair in state:
        if type(pair) is not list or len(pair) != 2:
            raise QuantumComputeError("A custom qubit uses two [real, imaginary] amplitude pairs")
        values.append(complex(finite(pair[0], "real amplitude"), finite(pair[1], "imaginary amplitude")))
    result = np.array(values, dtype=complex)
    if abs(float(np.vdot(result, result).real) - 1) > 1e-10:
        raise QuantumComputeError("Logical input must be normalized")
    return result


def phase_code(*, state="T", faults=None, seed=20261021, profile=Profile()):
    """Reuse the recovered three-qubit encoder, stabilizers, and decoder."""
    from xi_field.operators import apply_operator, initial_state
    start = time.perf_counter()
    resources = profile.reserve(3)
    integer(seed, "seed", 0)
    faults = [1] if faults is None else faults
    if type(faults) is not list or len(faults) > 32:
        raise QuantumComputeError("faults must be a list of at most 32 Z-fault indices")
    for qubit in faults:
        integer(qubit, "fault qubit", 0, 2)
    logical = logical_input(state)
    current = initial_state(3)
    current["branches"] = [[bits, [float(value.real), float(value.imag)]]
                           for bits, value in zip(["000", "100"], logical) if abs(value) > 1e-14]
    reference = {bits: complex(*pair) for bits, pair in current["branches"]}
    trace = [{"stage": "prepare", "state": dict(current)}]
    cycle = [("encode_phase_code", {})]
    cycle += [("inject_z_error", {"qubit": qubit}) for qubit in faults]
    cycle += [("phase_syndrome", {"seed": seed}), ("correct_z_error", {}), ("decode_phase_code", {})]
    syndrome, correction = None, None
    for operator, parameters in cycle:
        current, receipt = apply_operator(current, operator, parameters)
        trace.append({"stage": operator, "parameters": parameters, "receipt": receipt, "state": current})
        if operator == "phase_syndrome":
            syndrome = receipt["syndrome"]
        if operator == "correct_z_error":
            correction = receipt["corrected_qubit"]
    overlap = sum(reference.get(bits, 0j).conjugate() * complex(*pair) for bits, pair in current["branches"])
    fidelity = float(abs(overlap)**2)
    return {"algorithm": "PhaseCode", "execution": "exact sparse state-vector",
            "code": "three-qubit phase-flip repetition", "fault_model": "declared Pauli-Z sequence",
            "input": snapshot(logical), "faults": faults, "seed": seed,
            "stabilizers": ["XXI", "IXX"], "syndrome": syndrome,
            "corrected_qubit": correction, "recovered_state_fidelity": fidelity,
            "within_single_fault_scope": sum(faults.count(q) % 2 for q in range(3)) <= 1,
            "trace": trace, "output": current, "resources": resources,
            "wall_seconds": time.perf_counter() - start}


def _measure(vector, word, rng):
    transformed = pauli_action(vector, word)
    expectation = float(np.vdot(vector, transformed).real)
    p_plus = min(1.0, max(0.0, (1 + expectation) / 2))
    sign = 1 if rng.random() < p_plus else -1
    probability = p_plus if sign == 1 else 1 - p_plus
    if probability < 1e-14:
        raise QuantumComputeError("Attempted a zero-probability syndrome outcome")
    return (vector + sign * transformed) / (2 * math.sqrt(probability)), sign, probability


def shor_code(*, state="T", faults=None, seed=20261021, profile=Profile()):
    """Nine-qubit Shor code with eight measured commuting stabilizers."""
    start = time.perf_counter()
    resources = profile.reserve(9)
    integer(seed, "seed", 0)
    faults = [{"pauli": "Y", "qubit": 4}] if faults is None else faults
    if type(faults) is not list or len(faults) > 32:
        raise QuantumComputeError("faults must contain at most 32 Pauli fault objects")
    for fault in faults:
        if (type(fault) is not dict or set(fault) != {"pauli", "qubit"}
                or fault["pauli"] not in ("X", "Y", "Z")):
            raise QuantumComputeError("Each Shor-code fault needs pauli X/Y/Z and qubit 0..8")
        integer(fault["qubit"], "fault qubit", 0, 8)
    logical = logical_input(state)
    vector = np.zeros(512, complex)
    vector[0], vector[256] = logical
    reference = vector.copy()
    trace = [{"stage": "prepare", "state": snapshot(vector)}]
    gates = [("CX", 0, 3), ("CX", 0, 6)]
    gates += [("H", q, None) for q in (0, 3, 6)]
    gates += [("CX", q, q + d) for q in (0, 3, 6) for d in (1, 2)]
    for name, q, target in gates:
        vector = gate(vector, H, q, 9) if name == "H" else cnot(vector, q, target, 9)
    trace.append({"stage": "encode", "gates": gates, "state": snapshot(vector)})
    for fault in faults:
        vector = gate(vector, PAULI[fault["pauli"]], fault["qubit"], 9)
    trace.append({"stage": "fault", "faults": faults, "state": snapshot(vector)})
    stabilizers = []
    for block in (0, 3, 6):
        for left, right in ((block, block + 1), (block + 1, block + 2)):
            stabilizers.append("".join("Z" if q in (left, right) else "I" for q in range(9)))
    stabilizers += ["XXXXXXIII", "IIIXXXXXX"]
    rng, syndrome, probabilities = random.Random(seed), [], []
    for word in stabilizers:
        vector, sign, probability = _measure(vector, word, rng)
        syndrome.append(sign)
        probabilities.append(probability)
    trace.append({"stage": "syndrome", "stabilizers": stabilizers, "syndrome": syndrome,
                  "probabilities": probabilities, "state": snapshot(vector)})
    locate = {(1, 1): None, (-1, 1): 0, (-1, -1): 1, (1, -1): 2}
    corrections = []
    for block in range(3):
        offset = locate[tuple(syndrome[2*block:2*block + 2])]
        if offset is not None:
            qubit = 3*block + offset
            vector = gate(vector, X, qubit, 9)
            corrections.append({"pauli": "X", "qubit": qubit})
    phase_block = locate[tuple(syndrome[6:])]
    if phase_block is not None:
        vector = gate(vector, Z, 3*phase_block, 9)
        corrections.append({"pauli": "Z", "qubit": 3*phase_block})
    trace.append({"stage": "correct", "corrections": corrections, "state": snapshot(vector)})
    for name, q, target in reversed(gates):
        vector = gate(vector, H, q, 9) if name == "H" else cnot(vector, q, target, 9)
    trace.append({"stage": "decode", "state": snapshot(vector)})
    return {"algorithm": "ShorCode", "execution": "exact nine-qubit state-vector",
            "code": "Shor [[9,1,3]]", "input": snapshot(logical), "faults": faults,
            "stabilizers": stabilizers, "syndrome": syndrome, "corrections": corrections,
            "recovered_state_fidelity": float(abs(np.vdot(reference, vector))**2),
            "norm_squared": float(np.vdot(vector, vector).real), "trace": trace,
            "seed": seed, "resources": resources, "wall_seconds": time.perf_counter() - start}


def qft(*, qubits=3, basis=1, inverse=False, profile=Profile()):
    resources = profile.reserve(qubits)
    integer(basis, "basis", 0, (1 << qubits) - 1)
    if type(inverse) is not bool:
        raise QuantumComputeError("inverse must be boolean")
    vector = np.zeros(1 << qubits, complex)
    vector[basis] = 1
    output = np.fft.fft(vector) / math.sqrt(len(vector)) if inverse else np.fft.ifft(vector) * math.sqrt(len(vector))
    recovered = np.fft.ifft(output) * math.sqrt(len(vector)) if inverse else np.fft.fft(output) / math.sqrt(len(vector))
    return {"algorithm": "QFT", "execution": "exact numerical Fourier transform",
            "convention": "forward uses positive exponent", "inverse": inverse,
            "input": snapshot(vector), "output": snapshot(output),
            "roundtrip_fidelity": float(abs(np.vdot(vector, recovered))**2),
            "state_sha256": digest(output.astype("<c16").tobytes()), "resources": resources}
