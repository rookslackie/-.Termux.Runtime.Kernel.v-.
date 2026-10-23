#!/usr/bin/env python3
"""Verify Xi's coherent phase-code channel against an independent dense oracle.

The oracle imports no production gate, encoder, decoder, syndrome table, or
state-preparation helper. Production imports appear only in the run driver.
Run with a single BLAS thread for comparable timing. Exit nonzero on failure;
write the failed receipt too. All experiments are classical simulations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import itertools
import json
import math
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import tracemalloc

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STATES = {"zero": [1, 0], "one": [0, 1], "plus": [2**-.5, 2**-.5],
          "minus": [2**-.5, -2**-.5], "T": [2**-.5, np.exp(1j*math.pi/4)*2**-.5],
          "y_plus": [2**-.5, 1j*2**-.5]}
PROBABILITY_TOLERANCE = 1e-12
TRACE_DISTANCE_TOLERANCE = 1e-10


def unpack(record):
    a = np.asarray(record, float)
    return a[..., 0] + 1j*a[..., 1]


def trace_distance(left, right):
    return float(np.linalg.svd(left-right, compute_uv=False).sum()/2)


def reference(*, vector, angles, cycles=1, twirled=False):
    """8x8 density matrices, explicit projectors, no production implementation."""
    identity = np.eye(2, dtype=complex)
    x = np.array([[0, 1], [1, 0]], complex)
    z = np.diag([1, -1]).astype(complex)
    h = np.array([[1, 1], [1, -1]], complex) / np.sqrt(2)

    def tensor(a, b, c):
        return np.kron(np.kron(a, b), c)

    def cx(target):
        matrix = np.zeros((8, 8), complex)
        for column in range(8):
            row = column ^ (1 << (2-target)) if column & 4 else column
            matrix[row, column] = 1
        return matrix

    encoder = tensor(h, h, h) @ cx(2) @ cx(1)
    embedding = encoder[:, [0, 4]]
    signs = list(itertools.product((1, -1), repeat=2))
    stabilizers = (tensor(x, x, identity), tensor(identity, x, x))
    projectors = [(np.eye(8)+a*stabilizers[0]) @ (np.eye(8)+b*stabilizers[1])/4
                  for a, b in signs]
    # Derive the correction from its stabilizer commutation pattern.
    corrections = []
    for syndrome in signs:
        if syndrome == (1, 1):
            corrections.append(np.eye(8))
        else:
            for q in range(3):
                signature = (-1 if q in (0, 1) else 1, -1 if q in (1, 2) else 1)
                if signature == syndrome:
                    corrections.append(tensor(*[z if i == q else identity for i in range(3)]))
                    break
    if twirled:
        p = [math.sin(a/2)**2 for a in angles]
        noise = [(math.prod(p[q] if bits[q] else 1-p[q] for q in range(3)),
                  tensor(*[z if bit else identity for bit in bits]))
                 for bits in itertools.product((0, 1), repeat=3)]
    else:
        # Construct all eight diagonal entries directly from computational bits.
        diagonal = [np.exp(-.5j*sum(a * (1 if not index & (1 << (2-q)) else -1)
                                        for q, a in enumerate(angles))) for index in range(8)]
        noise = [(1.0, np.diag(diagonal))]
    density = np.outer(vector, np.conjugate(vector))
    history = []
    for _ in range(cycles):
        encoded = embedding @ density @ embedding.conj().T
        noisy = sum((weight * u @ encoded @ u.conj().T for weight, u in noise),
                    np.zeros((8, 8), complex))
        density = np.zeros((2, 2), complex)
        branches = {}
        for syndrome, projector, correction in zip(signs, projectors, corrections):
            recovered = correction @ projector @ noisy @ projector @ correction.conj().T
            decoded = encoder.conj().T @ recovered @ encoder
            # Partial trace over recovery registers; no assumption they vanished.
            logical = np.einsum('arbr->ab', decoded.reshape(2, 4, 2, 4))
            branches[str(list(syndrome))] = logical
            density += logical
        history.append({"density": density.copy(), "branches": branches})
    kraus = [math.sqrt(weight) * embedding.conj().T @ correction @ projector @ u @ embedding
             for weight, u in noise for projector, correction in zip(projectors, corrections)]
    choi = sum((np.outer(k.reshape(4), k.reshape(4).conj())/2 for k in kraus),
               np.zeros((4, 4), complex))
    return density, history, choi


def run():
    from xi_quantum.circuits import phase_code
    from xi_quantum.coherent import phase_code_channel
    from xi_quantum.common import digest
    from xi_quantum.tessera import engine_hash

    started = time.perf_counter()
    tracemalloc.start()
    grid = [[a]*3 for a in (0, .01, .05, .1, .2)]
    grid += [[.13, -.07, .21], [math.pi, 0, 0], [math.pi]*3, [1e-8, -.31, .7]]
    inputs = list(STATES.items())
    rng = np.random.default_rng(20261023)
    for index in range(8):
        vector = rng.normal(size=2) + 1j*rng.normal(size=2)
        inputs.append((f"seeded_complex_{index}", vector/np.linalg.norm(vector)))
    rows = []
    max_probability_error = max_density_error = max_choi_error = max_trajectory_error = 0.0
    max_analytic_error = 0.0
    trajectory_cases = 0
    twirl_gap = {"distance": 0.0}
    for name, values in inputs:
        vector = np.asarray(values, complex)
        state = name if name in STATES else [[float(a.real), float(a.imag)] for a in vector]
        for angles in grid:
            for cycles in (1, 2, 8):
                coherent_result = None
                for twirled in (False, True):
                    result = phase_code_channel(state=state, angles=angles, cycles=cycles, twirled=twirled)
                    expected, history, expected_choi = reference(
                        vector=vector, angles=angles, cycles=cycles, twirled=twirled)
                    error = trace_distance(unpack(result["logical_density_matrix"]), expected)
                    max_density_error = max(max_density_error, error)
                    probability_error = max(abs(float(np.trace(h["branches"][s]).real)-
                                                r["syndrome_probabilities"][s])
                                            for h, r in zip(history, result["history"])
                                            for s in h["branches"])
                    max_probability_error = max(max_probability_error, probability_error)
                    choi = sum((np.outer((k := unpack(item["matrix"])).reshape(4), k.reshape(4).conj())/2
                                for item in result["kraus_operators"]), np.zeros((4, 4), complex))
                    choi_error = trace_distance(choi, expected_choi)
                    max_choi_error = max(max_choi_error, choi_error)
                    if not twirled:
                        coherent_result = unpack(result["logical_density_matrix"])
                    else:
                        distance = trace_distance(coherent_result, unpack(result["logical_density_matrix"]))
                        if distance > twirl_gap["distance"]:
                            twirl_gap = {"distance": distance, "state": name, "angles": angles, "cycles": cycles}
                    if twirled and cycles == 1 and name == "zero" and len(set(angles)) == 1:
                        p = math.sin(angles[0]/2)**2
                        analytic = 3*p*p-2*p*p*p
                        max_analytic_error = max(max_analytic_error,
                            abs(unpack(result["logical_density_matrix"])[1, 1].real-analytic))
                    rows.append({"state": name, "angles": angles, "cycles": cycles, "twirled": twirled,
                                 "trace_distance": error, "probability_error": probability_error,
                                 "choi_trace_distance": choi_error, "fidelity": result["recovered_state_fidelity"],
                                 "numerical_sha256": result["numerical_sha256"]})
                # Exercise the original sparse field's sampled measurement and correction.
                if cycles == 1 and name in STATES:
                    _, conditional, _ = reference(vector=vector, angles=angles)
                    for seed in (0, 1, 7, 20261023):
                        sampled = phase_code(state=state, faults=[], angles=angles, seed=seed)
                        branch = conditional[0]["branches"][str(sampled["syndrome"])]
                        probability = float(np.trace(branch).real)
                        if probability <= 0:
                            raise RuntimeError("Sparse engine sampled an impossible reference syndrome")
                        output = np.zeros(8, complex)
                        for bits, pair in sampled["output"]["branches"]:
                            output[int(bits, 2)] = complex(*pair)
                        reduced = np.einsum('ar,br->ab', output.reshape(2, 4), output.reshape(2, 4).conj())
                        max_trajectory_error = max(max_trajectory_error, trace_distance(reduced, branch/probability))
                        trajectory_cases += 1
    traced_current, traced_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    metrics = {"max_syndrome_probability_error": max_probability_error,
               "max_logical_trace_distance": max_density_error, "max_choi_trace_distance": max_choi_error,
               "max_sampled_conditional_trace_distance": max_trajectory_error,
               "max_twirled_binomial_error": max_analytic_error}
    passed = (max_probability_error < PROBABILITY_TOLERANCE
              and max(max_density_error, max_choi_error, max_trajectory_error) < TRACE_DISTANCE_TOLERANCE
              and max_analytic_error < PROBABILITY_TOLERANCE)
    paths = ["xi_quantum/coherent.py", "xi_quantum/circuits.py", "xi_field/operators.py",
             "benchmarks/verify_coherent_phase_code.py"]
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {"schema": "xi.coherent-phase-code.verification.v1", "passed": bool(passed),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "working_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
            "engine_sha256": engine_hash(),
            "source_sha256": {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
            "execution": "classical numerical simulation; locally executed, no physical quantum hardware",
            "independence": "separate dense-matrix oracle; not independent third-party reproduction",
            "conditions": {"states": len(inputs), "angle_vectors": grid, "cycles": [1, 2, 8],
                           "models": ["coherent local RZ", "independent Pauli-Z twirl"],
                           "dtype": "complex128", "rng_seed": 20261023, "postselection": False,
                           "measurement": "all four exact syndrome outcomes; ideal recovery and fresh ancillas"},
            "tolerances": {"probability_absolute": PROBABILITY_TOLERANCE, "trace_distance": TRACE_DISTANCE_TOLERANCE},
            "metrics": metrics, "channel_cases": len(rows), "sampled_trajectory_cases": trajectory_cases,
            "largest_coherent_vs_twirled_gap": twirl_gap, "cases": rows, "cases_sha256": digest(rows),
            "resources": {"wall_seconds": time.perf_counter()-started,
                          "python_tracemalloc_peak_bytes": traced_peak,
                          "python_tracemalloc_current_bytes": traced_current,
                          "process_peak_rss_bytes": int(rss if sys.platform == "darwin" else rss*1024),
                          "rss_scope": "whole verifier process including Python and NumPy; not just state arrays",
                          "production_peak_statevector_bytes": 128, "dense_reference_matrix_bytes": 1024,
                          "gpu_count": 0},
            "environment": {"python": platform.python_version(), "numpy": importlib.metadata.version("numpy"),
                            "numpy_build": np.show_config(mode="dicts"),
                            "platform": platform.platform(), "machine": platform.machine(),
                            "cpu_model": next((line.split(':', 1)[1].strip() for line in
                                Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),
                                platform.processor()) if Path('/proc/cpuinfo').exists() else platform.processor(),
                            "thread_environment": {k: os.environ.get(k) for k in
                                ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+"\n")
    print(json.dumps({k: result[k] for k in ("passed", "channel_cases", "sampled_trajectory_cases", "metrics", "resources")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
