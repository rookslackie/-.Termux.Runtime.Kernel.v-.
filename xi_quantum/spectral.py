"""Variational eigensolving and controlled-evolution phase estimation.

Small classical simulations. VQE uses parameter-shift gradients and a
backtracking optimizer. Hamiltonian QPE constructs its exact unitary through
classical eigendecomposition, then simulates controlled powers and inverse QFT.
"""
from __future__ import annotations

import math
import time

import numpy as np

from .algorithms import _observe
from .circuits import PAULI, cnot, gate, logical_input, ry, rz, snapshot
from .common import Profile, QuantumComputeError, digest, finite, integer


H2_TERMS = [["II", -1.052373245772859], ["IZ", 0.39793742484318045],
            ["ZI", -0.39793742484318045], ["ZZ", -0.01128010425623538],
            ["XX", 0.18093119978423156]]
H2_SOURCE = "https://qiskit-community.github.io/qiskit-algorithms/tutorials/02_vqe_advanced_options.html"


def hamiltonian(terms=None, *, profile=Profile()):
    terms = H2_TERMS if terms is None else terms
    if type(terms) is not list or not 1 <= len(terms) <= 256:
        raise QuantumComputeError("Hamiltonian needs 1..256 real Pauli terms")
    qubits = None
    cleaned = []
    for term in terms:
        if type(term) is not list or len(term) != 2 or type(term[0]) is not str:
            raise QuantumComputeError("Pauli terms use [word, real coefficient]")
        word, coefficient = term[0], finite(term[1], "Pauli coefficient")
        if not word or len(word) > 8 or set(word) - set("IXYZ"):
            raise QuantumComputeError("Pauli words must contain 1..8 I/X/Y/Z characters")
        qubits = len(word) if qubits is None else qubits
        if len(word) != qubits:
            raise QuantumComputeError("Pauli words must have the same width")
        cleaned.append([word, coefficient])
    resources = profile.reserve(2 * qubits, bytes_per_basis=96)
    matrix = np.zeros((1 << qubits, 1 << qubits), complex)
    for word, coefficient in cleaned:
        product = np.array([[1]], complex)
        for letter in word:
            product = np.kron(product, PAULI[letter])
        matrix += coefficient * product
    return matrix, cleaned, resources


def _ansatz(parameters, qubits, ansatz, layers):
    vector = np.zeros(1 << qubits, complex)
    if ansatz == "h2_odd":
        if qubits != 2 or len(parameters) != 1:
            raise QuantumComputeError("h2_odd uses two qubits and one angle")
        vector[1] = 1  # |01>; odd-parity ansatz for this explicit reduced benchmark.
        return cnot(gate(vector, ry(parameters[0]), 0, 2), 0, 1, 2)
    if ansatz != "hardware_efficient" or len(parameters) != 2 * qubits * layers:
        raise QuantumComputeError("hardware_efficient uses 2 * qubits * layers angles")
    vector[0] = 1
    index = 0
    for _ in range(layers):
        for qubit in range(qubits):
            vector = gate(vector, ry(parameters[index]), qubit, qubits)
            vector = gate(vector, rz(parameters[index + 1]), qubit, qubits)
            index += 2
        for qubit in range(qubits - 1):
            vector = cnot(vector, qubit, qubit + 1, qubits)
    return vector


def vqe(*, terms=None, ansatz="h2_odd", parameters=None, layers=1, steps=64,
        step_size=1.0, tolerance=1e-9, profile=Profile()):
    start = time.perf_counter()
    matrix, terms, resources = hamiltonian(terms, profile=profile)
    qubits = len(terms[0][0])
    integer(layers, "layers", 1, 8)
    integer(steps, "steps", 1, min(4096, profile.max_iterations))
    step_size, tolerance = finite(step_size, "step_size"), finite(tolerance, "tolerance")
    if not 0 < step_size <= 100 or not 1e-14 <= tolerance <= 0.1:
        raise QuantumComputeError("VQE requires 0 < step_size <= 100 and 1e-14 <= tolerance <= .1")
    count = 1 if ansatz == "h2_odd" else 2 * qubits * layers
    if count * steps * 4 > profile.max_iterations * 16:
        raise QuantumComputeError("VQE evaluation budget exceeds the selected profile")
    parameters = [0.0] * count if parameters is None else parameters
    if type(parameters) is not list or len(parameters) != count:
        raise QuantumComputeError(f"This ansatz needs {count} parameter values")
    theta = np.array([finite(v, "parameter") for v in parameters])
    evaluations, history = 0, []

    def energy(angles):
        nonlocal evaluations
        evaluations += 1
        state = _ansatz(angles, qubits, ansatz, layers)
        return float(np.vdot(state, matrix @ state).real)

    initial = energy(theta)
    reason = "iteration_budget"
    for iteration in range(steps):
        value = energy(theta)
        gradient = []
        for coordinate in range(count):
            plus, minus = theta.copy(), theta.copy()
            plus[coordinate] += math.pi / 2
            minus[coordinate] -= math.pi / 2
            gradient.append((energy(plus) - energy(minus)) / 2)
        gradient = np.array(gradient)
        norm = float(np.linalg.norm(gradient))
        scale, candidate, next_value, backtracks = step_size, theta.copy(), value, 0
        if norm > tolerance:
            for backtracks in range(32):
                attempt = theta - scale * gradient
                observed = energy(attempt)
                if observed <= value - 1e-4 * scale * norm**2 + 1e-14:
                    candidate, next_value = attempt, observed
                    break
                scale *= .5
        history.append({"iteration": iteration, "parameters": theta.tolist(), "energy": value,
                        "gradient": gradient.tolist(), "gradient_norm": norm,
                        "next_energy": next_value, "accepted_step_size": scale,
                        "backtracks": backtracks})
        theta = candidate
        if norm <= tolerance:
            reason = "gradient_tolerance"
            break
        if np.array_equal(history[-1]["parameters"], theta):
            reason = "line_search_stalled"
            break
    output = _ansatz(theta, qubits, ansatz, layers)
    energy_final = float(np.vdot(output, matrix @ output).real)
    # This is a separate classical reference, not the optimizer's source of answers.
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    return {"algorithm": "VQE", "execution": "state-vector variational optimization",
            "hamiltonian": {"terms": terms, "qubit_order": "leftmost Pauli acts on q0",
                            "source": H2_SOURCE if terms == H2_TERMS else "caller-declared Pauli terms"},
            "energy_units": "hartree for the supplied H2 benchmark; caller-defined for custom terms",
            "energy_offset": "No separate nuclear-repulsion term is added",
            "ansatz": ansatz, "ansatz_initial_state": "01" if ansatz == "h2_odd" else "0" * qubits,
            "optimizer": "parameter-shift gradient descent with Armijo backtracking",
            "initial_energy": initial, "energy": energy_final, "optimized_parameters": theta.tolist(),
            "exact_reference_energy": float(eigenvalues[0]),
            "variational_gap": energy_final - float(eigenvalues[0]),
            "ground_state_overlap": float(abs(np.vdot(eigenvectors[:, 0], output))**2),
            "converged": reason == "gradient_tolerance", "stop_reason": reason,
            "evaluations": evaluations, "history": history, "state": snapshot(output),
            "state_sha256": digest(output.astype("<c16").tobytes()),
            "resources": resources, "wall_seconds": time.perf_counter() - start}


def phase_estimation(*, phase=.375, precision=5, shots=1024, seed=20261021, profile=Profile()):
    """QPE for U=diag(1, exp(2*pi*i*phase)) with target eigenstate |1>."""
    phase = finite(phase, "phase")
    if not 0 <= phase < 1:
        raise QuantumComputeError("phase must lie in [0, 1)")
    integer(precision, "precision", 1, 16)
    resources = profile.reserve(precision + 1)
    size = 1 << precision
    joint = np.zeros((size, 2), complex)
    joint[:, 1] = 1 / math.sqrt(size)
    unitary = np.diag([1, np.exp(2j * math.pi * phase)])
    powers = []
    for bit in range(precision):
        selected = (np.arange(size) & (1 << bit)) != 0
        joint[selected] = joint[selected] @ unitary.T
        powers.append(1 << bit)
        unitary = unitary @ unitary
    joint = np.fft.fft(joint, axis=0) / math.sqrt(size)
    probabilities = np.sum(np.abs(joint)**2, axis=1)
    probabilities /= probabilities.sum()
    peak = int(np.argmax(probabilities))
    return {"algorithm": "QPE", "aliases": ["PEA"], "execution": "controlled-unitary state-vector plus inverse QFT",
            "unitary": "diag(1, exp(2*pi*i*phase))", "target_eigenstate": "1",
            "phase": phase, "precision_qubits": precision, "controlled_powers": powers,
            "estimated_phase": peak / size, "phase_resolution": 1 / size,
            "circular_phase_error": min(abs(peak/size-phase), 1-abs(peak/size-phase)),
            "phase_probabilities": probabilities.tolist(), "counts": _observe(probabilities, shots, seed),
            "shots": shots, "seed": seed, "resources": resources,
            "state_sha256": digest(joint.astype("<c16").tobytes())}


def vqe_pea(*, terms=None, parameters=None, vqe_steps=64, precision=8,
            shots=2048, seed=20261021, profile=Profile()):
    """Optimize the two-qubit ansatz, then feed that state into energy QPE."""
    start = time.perf_counter()
    integer(precision, "precision", 1, 16)
    prepared = vqe(terms=terms, parameters=parameters, steps=vqe_steps, profile=profile)
    matrix, terms, matrix_resources = hamiltonian(terms, profile=profile)
    qubits, size = len(terms[0][0]), 1 << precision
    resources = profile.reserve(precision + qubits)
    total_workspace = resources["estimated_workspace_bytes"] + matrix_resources["estimated_workspace_bytes"]
    if total_workspace > profile.memory_mib * 1024 * 1024:
        raise QuantumComputeError("Combined Hamiltonian and phase-register workspace exceeds profile budget")
    vector = _ansatz(prepared["optimized_parameters"], qubits, "h2_odd", 1)
    bound = sum(abs(coefficient) for _, coefficient in terms)
    ceiling, span = bound + 1, 2 * bound + 2
    values, vectors = np.linalg.eigh(matrix)
    unitary = (vectors * np.exp(2j * math.pi * (ceiling-values) / span)) @ vectors.conj().T
    joint = np.tile(vector, (size, 1)) / math.sqrt(size)
    for bit in range(precision):
        selected = (np.arange(size) & (1 << bit)) != 0
        joint[selected] = joint[selected] @ unitary.T
        unitary = unitary @ unitary
    joint = np.fft.fft(joint, axis=0) / math.sqrt(size)
    probabilities = np.sum(np.abs(joint)**2, axis=1)
    probabilities /= probabilities.sum()
    peak = int(np.argmax(probabilities))
    estimate = ceiling - span * peak / size
    return {"algorithm": "VQEPEA", "execution": "VQE-prepared state followed by controlled-evolution QPE",
            "vqe": prepared, "pea": {"precision_qubits": precision,
                "phase_probabilities": probabilities.tolist(), "counts": _observe(probabilities, shots, seed),
                "shots": shots, "seed": seed, "peak_phase": peak/size,
                "energy_ceiling": ceiling, "energy_span": span, "energy_resolution": span/size,
                "estimated_energy": estimate, "energy_error_vs_reference": estimate-float(values[0]),
                "unitary": "exp(-i*(H-energy_ceiling*I)*t), t=2*pi/energy_span",
                "unitary_construction": "classical Hermitian eigendecomposition for this small simulation",
                "input_ground_overlap": prepared["ground_state_overlap"]},
            "resources": {**resources, "combined_estimated_workspace_bytes": total_workspace},
            "wall_seconds": time.perf_counter() - start}
