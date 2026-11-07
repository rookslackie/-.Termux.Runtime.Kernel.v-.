"""Exact numerical Grover/order finding and witnessed Jacobian parameter flow.

Order finding evaluates the modular-exponentiation unitary on its prepared
input, measures the work register, then applies the inverse QFT to the exact
conditional clock vector. This avoids storing an unnecessary entangled dense
register. It does not precompute or supply the unknown order.
"""
from __future__ import annotations

from bisect import bisect_left
from fractions import Fraction
import math
import random
import time

import numpy as np

from .common import Profile, QuantumComputeError, digest, finite, integer


def _observe(probabilities, shots, seed):
    integer(shots, "shots", 1, 1000000)
    integer(seed, "seed", 0)
    rng = random.Random(seed)
    cumulative = np.cumsum(probabilities).tolist()
    counts = {}
    for _ in range(shots):
        outcome = min(bisect_left(cumulative, rng.random()), len(cumulative) - 1)
        key = str(outcome)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _grover_state(qubits, marked, iterations, oracle_phase, profile):
    resources = profile.reserve(qubits)
    size = resources["basis_states"]
    if not isinstance(marked, list) or not marked:
        raise QuantumComputeError("Grover requires a nonempty marked-state list")
    targets = []
    for target in marked:
        if isinstance(target, str):
            if len(target) != qubits or set(target) - {"0", "1"}:
                raise QuantumComputeError("marked bitstrings must match the register width")
            target = int(target, 2)
        targets.append(integer(target, "marked state", 0, size - 1))
    if len(targets) != len(set(targets)):
        raise QuantumComputeError("marked states must be distinct")
    theta = math.asin(math.sqrt(len(targets) / size))
    if iterations is None:
        iterations = max(0, round(math.pi / (4 * theta) - 0.5))
    integer(iterations, "iterations", 0, profile.max_iterations)
    phase = finite(oracle_phase, "oracle_phase")
    vector = np.full(size, 1 / math.sqrt(size), dtype=np.complex128)
    for _ in range(iterations):
        vector[targets] *= complex(math.cos(phase), math.sin(phase))
        vector = 2 * vector.mean() - vector
    return vector, targets, iterations, resources


def grover(*, qubits=2, marked=None, iterations=None, oracle_phase=math.pi,
           shots=256, seed=20261019, profile=Profile()):
    start = time.perf_counter()
    vector, targets, rounds, resources = _grover_state(
        qubits, ["11"] if marked is None else marked, iterations, oracle_phase, profile)
    probabilities = np.abs(vector) ** 2
    norm = float(probabilities.sum())
    if abs(norm - 1) > 1e-9:
        raise QuantumComputeError("Grover state norm drifted outside tolerance")
    counts = _observe(probabilities, shots, seed)
    return {"algorithm": "Grover", "execution": "exact numerical state-vector",
            "qubits": qubits, "iterations": rounds, "oracle_phase": float(oracle_phase),
            "marked": targets, "success_probability": float(probabilities[targets].sum()),
            "ideal_prediction": math.sin((2 * rounds + 1) * math.asin(math.sqrt(len(targets) / len(vector)))) ** 2
            if math.isclose(float(oracle_phase), math.pi, abs_tol=1e-12) else None,
            "counts": counts, "shots": shots, "seed": seed, "norm_squared": norm,
            "state_sha256": digest(vector.astype("<c16").tobytes()), "resources": resources,
            "wall_seconds": time.perf_counter() - start}


def shor(*, N=15, a=2, precision=None, shots=128, seed=20261019, profile=Profile()):
    start = time.perf_counter()
    integer(N, "N", 3, 9007199254740991)
    integer(a, "a", 2, N - 1)
    integer(shots, "shots", 1, 1000000)
    integer(seed, "seed", 0)
    if math.gcd(a, N) != 1:
        factor = math.gcd(a, N)
        return {"algorithm": "Shor", "execution": "classical gcd shortcut",
                "N": N, "a": a, "factors": sorted([factor, N // factor]), "order": None}
    width = N.bit_length()
    precision = 2 * width if precision is None else integer(precision, "precision", 2)
    resources = profile.reserve(precision)
    size = 1 << precision
    # Functional evaluation of |x>|1> -> |x>|a**x mod N>. No order is supplied.
    work = np.fromiter((pow(a, x, N) for x in range(size)), dtype=np.int64, count=size)
    values, multiplicities = np.unique(work, return_counts=True)
    rng = random.Random(seed)
    threshold = rng.random() * size
    cumulative, observed_work = 0, int(values[-1])
    for value, count in zip(values, multiplicities):
        cumulative += int(count)
        if threshold < cumulative:
            observed_work = int(value)
            break
    selected = work == observed_work
    preimages = int(selected.sum())
    clock = selected.astype(np.complex128) / math.sqrt(preimages)
    del work, values, multiplicities, selected
    # numpy FFT's negative exponent implements our inverse-QFT convention.
    clock = np.fft.fft(clock) / math.sqrt(size)
    probabilities = np.abs(clock) ** 2
    norm = float(probabilities.sum())
    if abs(norm - 1) > 1e-9:
        raise QuantumComputeError("inverse QFT produced a non-normalized clock")
    counts = _observe(probabilities, shots, seed + 1)
    candidates = {}
    for outcome in counts:
        y = int(outcome)
        if y:
            candidate = Fraction(y, size).limit_denominator(N).denominator
            if candidate > 1 and pow(a, candidate, N) == 1:
                candidates[str(y)] = candidate
    order = min(candidates.values()) if candidates else None
    factors = []
    if order is not None and order % 2 == 0:
        midpoint = pow(a, order // 2, N)
        if midpoint not in (1, N - 1):
            factors = sorted({f for f in (math.gcd(midpoint - 1, N), math.gcd(midpoint + 1, N)) if 1 < f < N})
    return {"algorithm": "Shor", "execution": "exact conditional order-finding state-vector",
            "N": N, "a": a, "order": order, "factors": factors,
            "factor_product_verified": len(factors) == 2 and math.prod(factors) == N,
            "precision_qubits": precision, "work_qubits": width,
            "circuit_qubits": precision + width, "work_measurement": observed_work,
            "work_measurement_probability": preimages / size,
            "phase_counts": counts, "validated_period_candidates": candidates,
            "shots": shots, "seed": seed, "norm_squared": norm,
            "clock_state_sha256": digest(clock.astype("<c16").tobytes()),
            "order_source": "continued fractions of measured inverse-QFT outcomes; modular verification",
            "resources": resources, "wall_seconds": time.perf_counter() - start}


def jacobian_flow(*, phase=math.pi / 2, qubits=2, marked=None, iterations=1,
                  steps=8, step_size=1.0, epsilon=1e-4, profile=Profile()):
    start = time.perf_counter()
    phase = finite(phase, "phase")
    step_size, epsilon = finite(step_size, "step_size"), finite(epsilon, "epsilon")
    integer(steps, "steps", 1, min(1024, profile.max_iterations))
    if not 0 < step_size <= 100 or not 1e-7 <= epsilon <= 0.1:
        raise QuantumComputeError("Flow needs 0 < step_size <= 100 and 1e-7 <= epsilon <= 0.1")
    chosen = ["11"] if marked is None else marked

    def observe(phi):
        vector, targets, _, _ = _grover_state(qubits, chosen, iterations, phi, profile)
        if abs(float(np.vdot(vector, vector).real) - 1.0) > 1e-9:
            raise QuantumComputeError("Flow evaluation lost state normalization")
        return float((np.abs(vector[targets]) ** 2).sum())

    history = []
    for index in range(steps):
        value = observe(phase)
        plus, minus = observe(phase + epsilon), observe(phase - epsilon)
        derivative = (plus - minus) / (2 * epsilon)
        curvature = (plus - 2 * value + minus) / epsilon ** 2
        displacement = step_size * derivative
        next_phase, next_value, backtracks = phase, value, 0
        for backtracks in range(25):
            candidate = phase + displacement
            observed = observe(candidate)
            if observed >= value - 1e-12:
                next_phase, next_value = candidate, observed
                break
            displacement *= 0.5
        history.append({"step": index, "phase": phase, "success_probability": value,
                        "jacobian": [[derivative]], "curvature": curvature,
                        "next_phase": next_phase, "next_success_probability": next_value,
                        "backtracks": backtracks})
        phase = next_phase
    return {"algorithm": "JacobianFlow", "binding": "Grover oracle-phase coordinate",
            "coordinate": "radians", "map": "F(phi)=marked-state probability after the declared Grover circuit",
            "update": "witnessed gradient ascent with backtracking; each phase selects unitary gates",
            "epsilon": epsilon, "history": history, "final_phase": phase,
            "norm_verified_on_every_evaluation": True,
            "initial_success_probability": history[0]["success_probability"],
            "final_success_probability": observe(phase), "resources": profile.reserve(qubits),
            "wall_seconds": time.perf_counter() - start}
