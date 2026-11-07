"""Bounded observer views over the existing sparse quantum measurement engine.

The evaluator owns state preparation and reference values. Observer objects
receive only outcome records, never amplitudes, preparation parameters, noise
probabilities, or the evaluator's expectation values.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import hashlib
import math
import random
import time

import numpy as np

from xi_field.noise_benchmark import wilson_interval
from xi_field.operators import apply_operator, initial_state
from .common import Profile, QuantumComputeError, canonical, digest, finite, integer


SCHEMA = "xi.observer-access.v1"


@dataclass(frozen=True)
class ObserverContract:
    observer_id: str
    direct_bases: tuple[str, ...]
    sample_budget: int
    memory_bits: int
    confidence: float = 0.95
    tolerance: float = 0.1

    def __post_init__(self):
        if not isinstance(self.observer_id, str) or not self.observer_id:
            raise QuantumComputeError("Observer needs a nonempty local identity")
        if (type(self.direct_bases) is not tuple or not self.direct_bases
                or any(b not in ("X", "Z") for b in self.direct_bases)
                or len(set(self.direct_bases)) != len(self.direct_bases)):
            raise QuantumComputeError("Observer direct bases must be distinct X/Z labels")
        integer(self.sample_budget, "sample_budget", 1, 1000000)
        integer(self.memory_bits, "memory_bits", 1, 1000000)
        if not 0 < finite(self.confidence, "confidence") < 1 or not 0 < finite(self.tolerance, "tolerance") < 1:
            raise QuantumComputeError("Confidence and expectation tolerance must lie between zero and one")


@dataclass(frozen=True)
class Observation:
    sample_id: str
    basis: str
    outcome: int

    def __post_init__(self):
        if (not isinstance(self.sample_id, str) or not self.sample_id or self.basis not in ("X", "Z")
                or type(self.outcome) is not int or self.outcome not in (0, 1)):
            raise QuantumComputeError("Observation needs an ID, X/Z basis, and a binary outcome")


@dataclass(frozen=True)
class ShareGrant:
    """Local caller decision. Historical trust labels or payload fields do not create it."""
    sender: str
    recipient: str
    bases: frozenset[str]


class Observer:
    def __init__(self, contract: ObserverContract):
        self.contract = contract
        self._records = deque(maxlen=contract.memory_bits)
        self._seen = {}
        self._direct_count = 0

    def _check_record(self, record):
        if not isinstance(record, Observation):
            raise QuantumComputeError("Observer accepts typed outcome records")
        previous = self._seen.get(record.sample_id)
        if previous is not None and previous != digest(asdict(record)):
            raise QuantumComputeError("Conflicting outcome for an existing sample ID")

    def witness(self, record: Observation):
        self._check_record(record)
        if record.basis not in self.contract.direct_bases:
            raise QuantumComputeError("Observer has no direct access to that measurement basis")
        if record.sample_id in self._seen:
            return False
        if self._direct_count >= self.contract.sample_budget:
            raise QuantumComputeError("Observer sample budget is exhausted")
        self._direct_count += 1
        self._accept(record)
        return True

    def _accept(self, record):
        self._records.append(record)
        # Replay metadata is outside the explicitly named outcome-bit budget.
        self._seen[record.sample_id] = digest(asdict(record))

    def share(self, recipient, *, grant: ShareGrant):
        if (not isinstance(grant, ShareGrant) or grant.sender != self.contract.observer_id
                or grant.recipient != recipient.contract.observer_id
                or type(grant.bases) is not frozenset or not grant.bases <= {"X", "Z"}):
            raise QuantumComputeError("A matching local sharing grant is required")
        records = [record for record in self._records if record.basis in grant.bases]
        for record in records:
            recipient._check_record(record)
        before = recipient.evidence_digest()
        accepted = 0
        for record in records:
            if record.sample_id not in recipient._seen:
                recipient._accept(record)
                accepted += 1
        return {"schema": "xi.observer-share.receipt.v1", "sender": grant.sender,
                "recipient": grant.recipient, "bases": sorted(grant.bases), "accepted_records": accepted,
                "payload_sha256": digest([asdict(record) for record in records]),
                "recipient_before": before, "recipient_after": recipient.evidence_digest(),
                "direct_measurement_access_changed": False}

    def evidence_digest(self):
        return digest([asdict(record) for record in self._records])

    def predict(self, basis="X"):
        if basis not in ("X", "Z"):
            raise QuantumComputeError("Prediction target must be X or Z")
        matching = [record for record in self._records if record.basis == basis]
        n = len(matching)
        base = {"observer_id": self.contract.observer_id, "target": basis,
                "retained_target_samples": n, "retained_outcome_bits": len(self._records),
                "direct_samples_used": self._direct_count, "confidence": self.contract.confidence,
                "tolerance": self.contract.tolerance, "evidence_sha256": self.evidence_digest()}
        if not n:
            return {**base, "identifiable_from_available_evidence": False, "estimate": None,
                    "interval": [-1.0, 1.0], "interval_kind": "unidentified range",
                    "half_width": 1.0, "precision_resolved": False}
        zeros = sum(record.outcome == 0 for record in matching)
        low, high = wilson_interval(zeros, n, self.contract.confidence)
        low, high = 2 * low - 1, 2 * high - 1
        half_width = (high - low) / 2
        return {**base, "identifiable_from_available_evidence": True, "estimate": 2 * zeros / n - 1,
                "zeros": zeros, "ones": n - zeros, "interval": [low, high],
                "interval_kind": "marginal Wilson expectation interval", "half_width": half_width,
                "precision_resolved": half_width <= self.contract.tolerance}


def _prepare(phase):
    state, _ = apply_operator(initial_state(1), "hadamard", {"qubit": 0})
    state, _ = apply_operator(state, "phase", {"angle": phase})
    return state


def reference(phase, noise_p):
    """Evaluator-only density calculation, independently checked against the analytic map."""
    state = _prepare(phase)
    vector = np.zeros(2, dtype=complex)
    for bits, (real, imag) in state["branches"]:
        vector[int(bits, 2)] = complex(real, imag)
    z = np.diag([1, -1])
    rho = np.outer(vector, vector.conj())
    rho = (1 - noise_p) * rho + noise_p * z @ rho @ z
    x = np.array([[0, 1], [1, 0]])
    return {"X": float(np.trace(rho @ x).real), "Z": float(np.trace(rho @ z).real),
            "trace": float(np.trace(rho).real), "minimum_eigenvalue": float(np.linalg.eigvalsh(rho).min())}


def _seed(master, repetition, stream):
    return int.from_bytes(hashlib.sha256(f"{SCHEMA}|{master}|{repetition}|{stream}".encode()).digest()[:16], "big")


def _pool(template, noise_p, shots, master, repetition, basis):
    noise_rng = random.Random(_seed(master, repetition, basis + "/noise"))
    measurement_rng = random.Random(_seed(master, repetition, basis + "/measurement"))
    records, faults = [], 0
    for index in range(shots):
        state = template
        if noise_rng.random() < noise_p:
            state, _ = apply_operator(state, "z", {"qubit": 0})
            faults += 1
        _, receipt = apply_operator(state, "witness", {"basis": basis.lower(), "seed": measurement_rng.getrandbits(128)})
        records.append(Observation(f"{basis}/{repetition}/{index}", basis, int(receipt["outcome"])))
    return records, faults


def run(*, sample_counts=(16, 64, 256, 1024), memory_bits=None, repetitions=64,
        phase=math.pi / 3, noise_p=0.1, seed=20261020, confidence=0.95,
        tolerance=0.1, profile=Profile()):
    start, cpu_start = time.perf_counter(), time.process_time()
    resources = profile.reserve(1)
    phase, noise_p = finite(phase, "phase"), finite(noise_p, "noise_p")
    if not 0 <= noise_p <= 1:
        raise QuantumComputeError("noise_p must lie between zero and one")
    integer(seed, "seed", 0)
    integer(repetitions, "repetitions", 1, min(10000, profile.max_iterations))
    if not isinstance(sample_counts, (list, tuple)) or not 1 <= len(sample_counts) <= 32:
        raise QuantumComputeError("Supply one to 32 sample counts")
    counts = [integer(n, "sample count", 1, profile.max_iterations) for n in sample_counts]
    if len(counts) != len(set(counts)):
        raise QuantumComputeError("Sample counts must be distinct")
    if memory_bits is not None:
        integer(memory_bits, "memory_bits", 1, 1000000)
    if 2 * max(counts) * repetitions > 2000000:
        raise QuantumComputeError("Observer benchmark exceeds two million prepared samples")
    record_workspace = 4096 * max(counts)
    if record_workspace > profile.memory_mib * 1024 * 1024:
        raise QuantumComputeError("Observer record workspace exceeds the local memory budget")
    resources["estimated_record_workspace_bytes"] = record_workspace
    # Validate before sampling, including the statistical settings.
    ObserverContract("check", ("X",), max(counts), memory_bits or max(counts), confidence, tolerance)
    truth = reference(phase, noise_p)
    expected = (1 - 2 * noise_p) * math.cos(phase)
    if abs(truth["X"] - expected) > 1e-12 or abs(truth["trace"] - 1) > 1e-12:
        raise QuantumComputeError("Independent evaluator reference check failed")
    epsilon = 1e-5
    jacobian = {basis: (reference(phase + epsilon, noise_p)[basis] - reference(phase - epsilon, noise_p)[basis]) / (2 * epsilon)
                for basis in ("X", "Z")}
    accumulators = {n: {"squared_error": 0.0, "covered": 0, "resolved": 0, "half_width": 0.0} for n in counts}
    examples, transcript = {}, hashlib.sha256()
    faults = 0
    template = _prepare(phase)
    for repetition in range(repetitions):
        pools = {}
        for basis in ("X", "Z"):
            pools[basis], injected = _pool(template, noise_p, max(counts), seed, repetition, basis)
            faults += injected
            transcript.update(canonical([asdict(record) for record in pools[basis]]))
        for n in counts:
            capacity = n if memory_bits is None else memory_bits
            a = Observer(ObserverContract("observer-a", ("Z",), n, capacity, confidence, tolerance))
            b = Observer(ObserverContract("observer-b", ("X",), n, capacity, confidence, tolerance))
            for record in pools["Z"][:n]:
                a.witness(record)
            for record in pools["X"][:n]:
                b.witness(record)
            before, peer = a.predict(), b.predict()
            share = b.share(a, grant=ShareGrant("observer-b", "observer-a", frozenset({"X"})))
            after = a.predict()
            if before["estimate"] is not None or after["estimate"] != peer["estimate"] or after["interval"] != peer["interval"]:
                raise QuantumComputeError("Observer information boundary or exact sharing invariant failed")
            row = accumulators[n]
            row["squared_error"] += (after["estimate"] - truth["X"]) ** 2
            row["covered"] += after["interval"][0] <= truth["X"] <= after["interval"][1]
            row["resolved"] += after["precision_resolved"]
            row["half_width"] += after["half_width"]
            if repetition == 0:
                examples[n] = {"before": before, "peer": peer, "share": share, "after": after,
                               "contracts": [asdict(a.contract), asdict(b.contract)]}
    points = []
    for n in counts:
        row, retained = accumulators[n], min(n, n if memory_bits is None else memory_bits)
        points.append({"samples_per_observer": n, "memory_outcome_bits": n if memory_bits is None else memory_bits,
            "retained_target_samples": retained, "repetitions": repetitions,
            "before_unidentified_count": repetitions, "before_precision_resolved_count": 0,
            "after_rmse": math.sqrt(row["squared_error"] / repetitions),
            "analytic_rmse": math.sqrt(max(0, 1 - truth["X"] ** 2) / retained),
            "interval_coverage_count": row["covered"], "interval_coverage_fraction": row["covered"] / repetitions,
            "coverage_fraction_wilson_interval": wilson_interval(row["covered"], repetitions),
            "mean_interval_half_width": row["half_width"] / repetitions,
            "after_precision_resolved_count": row["resolved"], "example": examples[n]})
    return {"schema": SCHEMA, "algorithm": "ObserverBenchmark",
        "configuration": {"sample_counts": counts, "memory_bits": memory_bits, "repetitions": repetitions,
                          "phase": phase, "noise_p": noise_p, "seed": seed,
                          "confidence": confidence, "tolerance": tolerance},
        "model": {"preparation": "(|0> + exp(i*phase)|1>)/sqrt(2), freshly prepared per sample",
                  "noise": "one independent Bernoulli(noise_p) Pauli-Z per fresh qubit",
                  "measurement": "existing xi_field.apply_operator z / projective X or Z witness",
                  "inference": "sample mean of Pauli eigenvalues; no preparation/noise oracle passed to observers",
                  "memory": "FIFO retained outcome bits; Python objects, replay metadata and evaluator storage excluded",
                  "precision_resolved": "Wilson expectation interval half-width <= declared tolerance",
                  "scope": "restricted statistical observer model; no calibration of ORT presence or physical collapse"},
        "evaluator_reference": {**truth, "analytic_X": expected, "phase_jacobian": jacobian},
        "points": points, "outcome_transcript_sha256": transcript.hexdigest(),
        "cost": {"prepared_samples": 2 * max(counts) * repetitions, "witness_operator_calls": 2 * max(counts) * repetitions,
                 "injected_z_operator_calls": faults, "resources": resources,
                 "wall_seconds": time.perf_counter() - start, "cpu_seconds": time.process_time() - cpu_start},
        "return_operator": "⟁∴Ω"}
