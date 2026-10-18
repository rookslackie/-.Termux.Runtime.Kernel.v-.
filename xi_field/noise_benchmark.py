"""Seeded independent-Z benchmark of the persistent Xi phase-code operators.

Every shot runs the exact sparse state-vector channel, including stabilizer
measurement and minimum-weight recovery. A noiseless reference qubit measures
entanglement fidelity, so the result does not depend on a lucky input state.
T-state overlaps are computed by weighting an exhaustive eight-mask simulation
with the observed mask counts. Only data qubits receive noise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import resource
from statistics import NormalDist
import subprocess
import sys
import time
from typing import Any

from .operators import apply_operator, initial_state
from .phase_code_demo import _fidelity
from .runtime import bootstrap_field


SCHEMA = "xi-independent-z-benchmark-v1"
DEFAULT_PROBABILITIES = (0.0, 0.01, 0.05, 0.1, 0.25, 0.45, 0.49, 0.5, 0.51, 0.55, 0.75, 0.9, 1.0)
REPOSITORY = "https://github.com/rookslackie/-.Termux.Runtime.Kernel.v-."
SOURCE_PATHS = (
    "xi_field/noise_benchmark.py", "xi_field/operators.py", "xi_field/runtime.py",
    "xi_field/phase_code_demo.py", "xi_world/kernel.py", "xi_field/topology.py",
    "xi_field/resources/glyphic_quantum_processor.yaml",
    "tests/test_xi_noise_benchmark.py", ".github/workflows/python-package-conda.yml",
    "benchmarks/render_phase_noise.py",
)


def logical_error_prediction(p: float) -> float:
    """P(two or three independent faults); decoder is fixed even above p=1/2."""
    return 3 * p * p - 2 * p * p * p


def wilson_interval(failures: int, shots: int, confidence: float = 0.95) -> list[float]:
    """Two-sided Wilson score interval, without a normal-tail approximation."""
    if (not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0
            or not isinstance(failures, int) or isinstance(failures, bool)
            or not 0 <= failures <= shots or not 0 < confidence < 1):
        raise ValueError("Wilson interval requires 0 <= failures <= positive shots and 0 < confidence < 1")
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    rate = failures / shots
    denominator = 1 + z * z / shots
    center = (rate + z * z / (2 * shots)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / shots + z * z / (4 * shots * shots)) / denominator
    return [0.0 if failures == 0 else max(0.0, center - radius),
            1.0 if failures == shots else min(1.0, center + radius)]


def trial_seed(master_seed: int, p: float, shot: int, stream: str) -> int:
    """Stable, domain-separated SHA-256 seeds; independent of rate-list order."""
    text = f"{SCHEMA}|{master_seed}|{float(p).hex()}|{shot}|{stream}"
    return int.from_bytes(hashlib.sha256(text.encode("ascii")).digest()[:16], "big")


def _preparation(*, encoded: bool, bell: bool = True) -> tuple[dict, list[tuple[str, dict]]]:
    qubits = (4 if encoded else 2) if bell else (3 if encoded else 1)
    steps = [("hadamard", {"qubit": 0})]
    steps.append(("cnot", {"control": 0, "target": qubits - 1}) if bell else ("t", {"qubit": 0}))
    state = initial_state(qubits)
    for operator, params in steps:
        state, _ = apply_operator(state, operator, params)
    return state, steps


def _recover(state: dict, seed: int) -> tuple[dict, dict, dict]:
    state, syndrome = apply_operator(state, "phase_syndrome", {"seed": seed})
    state, correction = apply_operator(state, "correct_z_error")
    state, _ = apply_operator(state, "decode_phase_code")
    return state, syndrome, correction


def enumerate_faults() -> list[dict[str, Any]]:
    """Execute all eight masks on Bell and T inputs, without using the formula."""
    outcomes = []
    for index in range(8):
        mask = f"{index:03b}"
        faults = [q for q, bit in enumerate(mask) if bit == "1"]
        result = {"mask": mask, "fault_qubits": faults}
        for bell in (True, False):
            ideal, _ = _preparation(encoded=True, bell=bell)
            state, _ = apply_operator(ideal, "encode_phase_code")
            for q in faults:
                state, _ = apply_operator(state, "inject_z_error", {"qubit": q})
            state, syndrome, correction = _recover(state, 20261018)
            result["entanglement_fidelity" if bell else "t_state_fidelity"] = _fidelity(state, ideal)
            result.update(syndrome=syndrome["syndrome"], corrected_qubit=correction["corrected_qubit"])
            if bell:
                # Verify that the residual action is I or X, rather than inferring
                # its axis from the injected fault count.
                flipped = ideal
                for op in ("hadamard", "z", "hadamard"):
                    flipped, _ = apply_operator(flipped, op, {"qubit": 0})
                if math.isclose(_fidelity(state, ideal), 1, abs_tol=1e-10):
                    result["logical_pauli"] = "I"
                elif math.isclose(_fidelity(state, flipped), 1, abs_tol=1e-10):
                    result["logical_pauli"] = "X"
                else:
                    raise RuntimeError("decoded channel is outside the expected I/X model")
        outcomes.append(result)
    return outcomes


def _summary(failures: int, shots: int, *, encoded: bool, t_fidelity: float) -> dict:
    rate = failures / shots
    low, high = wilson_interval(failures, shots)
    t_loss = 0.5 if encoded else 1.0
    return {
        "logical_failures": failures, "logical_error_rate": rate,
        "logical_error_rate_ci95": [low, high],
        "entanglement_fidelity": 1 - rate,
        "entanglement_fidelity_ci95": [1 - high, 1 - low],
        "t_state_fidelity": t_fidelity,
        "t_state_fidelity_ci95": [1 - t_loss * high, 1 - t_loss * low],
    }


def _simulate_point(p: float, shots: int, seed: int, patterns: list[dict]) -> dict:
    setup_start = time.perf_counter()
    ideal_encoded, _ = _preparation(encoded=True)
    template, _ = apply_operator(ideal_encoded, "encode_phase_code")
    ideal_bare, _ = _preparation(encoded=False)
    setup_seconds = time.perf_counter() - setup_start
    by_mask = {row["mask"]: row for row in patterns}
    mask_counts = {mask: 0 for mask in by_mask}
    failures, bare_failures, t_sum = 0, 0, 0.0
    start, cpu_start = time.perf_counter(), time.process_time()
    for shot in range(shots):
        noisy, noise = apply_operator(template, "sample_z_noise", {
            "p": p, "seed": trial_seed(seed, p, shot, "encoded-noise"), "qubits": [0, 1, 2],
        })
        final, _, _ = _recover(noisy, trial_seed(seed, p, shot, "syndrome"))
        fidelity = _fidelity(final, ideal_encoded)
        mask = "".join("1" if q in noise["fault_qubits"] else "0" for q in range(3))
        expected = by_mask[mask]
        if not math.isclose(fidelity, expected["entanglement_fidelity"], abs_tol=1e-10):
            raise RuntimeError("per-shot channel disagrees with exhaustive mask simulation")
        failures += int(fidelity < 0.5)
        t_sum += expected["t_state_fidelity"]
        mask_counts[mask] += 1
    encoded_seconds, encoded_cpu = time.perf_counter() - start, time.process_time() - cpu_start

    start, cpu_start = time.perf_counter(), time.process_time()
    for shot in range(shots):
        final, _ = apply_operator(ideal_bare, "sample_z_noise", {
            "p": p, "seed": trial_seed(seed, p, shot, "unencoded-noise"), "qubits": [0],
        })
        fidelity = _fidelity(final, ideal_bare)
        if not (math.isclose(fidelity, 0, abs_tol=1e-10) or math.isclose(fidelity, 1, abs_tol=1e-10)):
            raise RuntimeError("unencoded channel is outside the expected I/Z model")
        bare_failures += int(fidelity < 0.5)
    bare_seconds, bare_cpu = time.perf_counter() - start, time.process_time() - cpu_start
    encoded = _summary(failures, shots, encoded=True, t_fidelity=t_sum / shots)
    bare = _summary(bare_failures, shots, encoded=False, t_fidelity=1 - bare_failures / shots)
    # A conservative 95% difference interval from two 97.5% Wilson intervals
    # (Bonferroni), for independently seeded encoded and bare arms.
    elow, ehigh = wilson_interval(failures, shots, 0.975)
    blow, bhigh = wilson_interval(bare_failures, shots, 0.975)
    improvement = [blow - ehigh, bhigh - elow]
    return {
        "p": p, "shots_per_arm": shots,
        "analytic": {
            "encoded_logical_error_rate": logical_error_prediction(p),
            "unencoded_logical_error_rate": p,
            "encoded_entanglement_fidelity": 1 - logical_error_prediction(p),
            "unencoded_entanglement_fidelity": 1 - p,
            "encoded_t_state_fidelity": 1 - 0.5 * logical_error_prediction(p),
            "unencoded_t_state_fidelity": 1 - p,
        },
        "encoded": encoded, "unencoded": bare, "mask_counts": mask_counts,
        "fault_weight_counts": {
            str(weight): sum(n for mask, n in mask_counts.items() if mask.count("1") == weight)
            for weight in range(4)
        },
        "error_rate_improvement": bare_failures / shots - failures / shots,
        "error_rate_improvement_ci95_conservative": improvement,
        "observed_regime": "improves" if improvement[0] > 0 else (
            "worsens" if improvement[1] < 0 else "not resolved at this sample count"),
        "cost": {
            "template_preparation_seconds": setup_seconds,
            "encoded_wall_seconds": encoded_seconds, "encoded_cpu_seconds": encoded_cpu,
            "unencoded_wall_seconds": bare_seconds, "unencoded_cpu_seconds": bare_cpu,
            "encoded_shots_per_second": shots / encoded_seconds,
            "unencoded_shots_per_second": shots / bare_seconds,
            "encoded_operator_calls": 4 * shots, "unencoded_operator_calls": shots,
            "encoded_data_qubits": 3, "unencoded_data_qubits": 1,
            "noiseless_reference_qubits_per_arm": 1,
            "encoded_max_branches": len(template["branches"]),
            "unencoded_max_branches": len(ideal_bare["branches"]),
        },
    }


def _source_manifest() -> dict:
    root = Path(__file__).resolve().parents[1]
    hashes = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in SOURCE_PATHS}
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCE_PATHS],
                                             cwd=root, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return {"repository": REPOSITORY, "commit": commit, "source_files_dirty": dirty,
            "sha256": hashes,
            "links": {path: f"{REPOSITORY}/blob/{commit}/{path}" for path in SOURCE_PATHS} if commit else {}}


def _persist_trace(database: str | Path, run_id: str, p: float, shot: int, seed: int, *, encoded: bool) -> dict:
    arm = "encoded" if encoded else "unencoded"
    world_id = f"noise-{run_id}-{float(p).hex()}-{shot}-{arm}"
    ideal, preparation = _preparation(encoded=encoded)
    field = bootstrap_field(database, world_id=world_id, qubits=ideal["qubits"])
    steps = [("reference", {}), *preparation]
    if encoded:
        steps.append(("encode_phase_code", {}))
    steps.append(("sample_z_noise", {
        "p": p, "seed": trial_seed(seed, p, shot, "encoded-noise" if encoded else "unencoded-noise"),
        "qubits": [0, 1, 2] if encoded else [0],
    }))
    noise_event = None
    for index, (operator, params) in enumerate(steps):
        noise_event = field.execute(operator, parameters=params, idempotency_key=f"prepare-{index}")
    # Reopen at the same boundary as the original single-fault demonstration.
    field = bootstrap_field(database, world_id=world_id, qubits=ideal["qubits"])
    recovery = [
        ("phase_syndrome", {"seed": trial_seed(seed, p, shot, "syndrome")}),
        ("correct_z_error", {}), ("decode_phase_code", {}),
    ] if encoded else []
    for index, (operator, params) in enumerate([*recovery, ("close", {})]):
        field.execute(operator, parameters=params, idempotency_key=f"recover-{index}")
    integrity = field.kernel.verify(world_id)
    if not integrity["ok"]:
        raise RuntimeError(f"persistent trace integrity check failed: {world_id}")
    return {
        "world_id": world_id, "p": p, "shot": shot, "arm": arm,
        "noise_event_id": noise_event.event_id,
        "noise_receipt": noise_event.echo["glyph-chip"]["last_operator_receipt"],
        "event_count": len(field.kernel.events(world_id)),
        "entanglement_fidelity": _fidelity(field.state(), ideal),
        "integrity": integrity,
    }


def run(*, probabilities=DEFAULT_PROBABILITIES, shots: int = 10000, seed: int = 20261018,
        database: str | Path | None = None, ledger_trials: int = 2) -> dict[str, Any]:
    probabilities = tuple(float(p) for p in probabilities)
    if not probabilities or any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError("probabilities must be finite numbers in [0, 1]")
    if len(probabilities) != len(set(probabilities)):
        raise ValueError("probabilities must be distinct")
    if not isinstance(shots, int) or isinstance(shots, bool) or shots < 1:
        raise ValueError("shots must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if (not isinstance(ledger_trials, int) or isinstance(ledger_trials, bool)
            or not 0 <= ledger_trials <= shots):
        raise ValueError("ledger_trials must be between zero and shots")
    source = _source_manifest()
    configuration = {
        "schema": SCHEMA, "probabilities": probabilities, "shots_per_arm_per_probability": shots,
        "master_seed": seed, "seed_derivation": "SHA256(schema|master|p.hex()|shot|stream)[:16], big-endian",
        "noise": "one independent Bernoulli(p) Pauli-Z round per data qubit",
        "decoder": "fixed minimum-weight X0X1/X1X2 syndrome table",
        "measurement": "ideal projective stabilizers; seeded, deterministic for these Pauli masks",
        "reference": "Bell pair with noiseless reference; no noise on reference or preparation/recovery",
        "t_state_fidelity_method": "exact per-mask T-state vectors weighted by observed mask histogram",
        "confidence_intervals": "marginal two-sided 95% Wilson; conservative difference from 97.5% arms",
        "source_sha256": source["sha256"],
    }
    run_id = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()[:20]
    start, cpu_start = time.perf_counter(), time.process_time()
    patterns = enumerate_faults()
    points = [_simulate_point(p, shots, seed, patterns) for p in probabilities]
    simulation_seconds, simulation_cpu = time.perf_counter() - start, time.process_time() - cpu_start
    persistence_start = time.perf_counter()
    traces = []
    if database is not None:
        for p in probabilities:
            for shot in range(ledger_trials):
                for encoded in (True, False):
                    traces.append(_persist_trace(database, run_id, p, shot, seed, encoded=encoded))
    persistence_seconds = time.perf_counter() - persistence_start
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "run_id": run_id, "configuration": configuration, "source": source,
        "environment": {
            "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "exhaustive_masks": patterns, "points": points,
        "persistence": {
            "database": str(database) if database is not None else None,
            "database_bytes": Path(database).stat().st_size if database is not None and Path(database).exists() else 0,
            "trials_per_arm_per_probability": ledger_trials if database is not None else 0,
            "traces": traces, "wall_seconds": persistence_seconds,
            "note": "Only these traces were committed; use --ledger-trials equal to --shots to persist every shot.",
        },
        "cost": {
            "simulation_wall_seconds": simulation_seconds, "simulation_cpu_seconds": simulation_cpu,
            "process_peak_rss_bytes": peak_rss if sys.platform == "darwin" else peak_rss * 1024,
            "total_shots": 2 * shots * len(probabilities),
            "note": "Host software timings; per-arm loops reuse noiseless templates and exclude SQLite. "
                    "RSS is process-wide high-water usage; these are not hardware gate costs.",
        },
        "scope": "Local sparse state-vector simulation; independent Pauli-Z data faults, one round, "
                 "ideal encoding, measurement, correction, decoding and noiseless reference.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p", type=float, nargs="+", default=DEFAULT_PROBABILITIES)
    parser.add_argument("--shots", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20261018)
    parser.add_argument("--db", default=".xi/noise-benchmark.sqlite3")
    parser.add_argument("--ledger-trials", type=int, default=2)
    parser.add_argument("--output", default=".xi/noise-benchmark.json")
    args = parser.parse_args()
    try:
        result = run(probabilities=args.p, shots=args.shots, seed=args.seed,
                     database=args.db, ledger_trials=args.ledger_trials)
    except ValueError as exc:
        parser.error(str(exc))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"run_id": result["run_id"], "output": str(output),
                      "total_shots": result["cost"]["total_shots"],
                      "simulation_seconds": result["cost"]["simulation_wall_seconds"],
                      "persistent_traces": len(result["persistence"]["traces"])}))


if __name__ == "__main__":
    main()
