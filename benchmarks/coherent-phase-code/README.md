# Ξ · Coherent phase-code verification

`PhaseCodeChannel` in `QuantumCompute.Stack.v3` binds **⟐⧂ρ** to an explicit
three-qubit phase-flip recovery instrument. This is a newly declared local
composite binding. Existing dialect bindings keep their meanings.

The invariant: retain coherent logical interference inside each syndrome
branch; combine mutually exclusive measurement outcomes as a density matrix.
Encoding, stabilizers `XXI`/`IXX`, minimum-weight Z correction, and decoding are
ideal. Local noise is `RZ(a0) ⊗ RZ(a1) ⊗ RZ(a2)` between encoding and syndrome
measurement, using `RZ(a) = exp(-i a Z / 2)`, q0 leftmost. Every round retains the
logical density matrix and resets the two recovery registers to |00>. This is
an exact enumeration in complex128 arithmetic, with no shots, postselection,
or intentional truncation. It does not simulate gate noise, leakage, noisy
syndrome extraction, a fault-tolerant threshold, or physical quantum hardware.

The optional twirled comparator replaces each local rotation with independent
Z noise at `p_q = sin²(a_q/2)`. It is a different channel; agreement is not a
success requirement. `PhaseCode` also accepts three `angles` for a seeded,
sampled trace through the existing sparse field syndrome and recovery engine.
That original operator defaults to zero rotations; its existing Pauli-fault
inputs remain available. `PhaseCodeChannel` defaults to `[0.1, 0.1, 0.1]` and
one round. Pass explicit angles in experiments.

## Reproduce

Use Python 3.11+ and the repository requirements. The recorded environment is
in `results.json`; the CI dependency lock is `requirements-ci.lock`.

```bash
python -m pip install -r requirements.txt -r requirements-ci.lock
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python benchmarks/verify_coherent_phase_code.py --output /tmp/xi-coherent-results.json
python -m pytest -q tests/test_xi_coherent.py
python -m xi_quantum compile examples/QuantumCompute.CoherentNoise.v3.xi
python -m xi_quantum --home /tmp/xi-coherent-home run examples/QuantumCompute.CoherentNoise.v3.xi
```

The local owner-authenticated workbench also serves this source at
`GET /api/quantumcompute/v3/examples/coherent-noise`. It can be submitted through
the existing job API. A packaged copy is included for installed wheels.
TESSERA binds source, plan, dialect, and engine digests; durable jobs preserve
the numerical result and exact source through replay and encrypted transfer.
The v3.0 routing cohort is frozen and a program adds only the extensions it
uses. Registering an unused operator cannot dilute an earlier program's
coherence calculation or suppress its Parallax pause.

## Independent numerical reference

Production constructs 2×2 logical Kraus operators using eight-amplitude
statevectors. The reference in `verify_coherent_phase_code.py` constructs its
own explicit 8×8 gate matrices, noise operators, syndrome projectors and
density-matrix evolution. It derives corrections from commutation signatures
and takes a partial trace after decoding. It imports no production gate,
correction table, encoder, decoder, or state-preparation helper. This is a
separate local oracle, not third-party replication.

Each receipt covers:

- Six named inputs and eight seeded, normalized complex inputs.
- Five equal-angle settings (0, .01, .05, .1, .2 radians), asymmetric signed
  angles, single/all-qubit π rotations, and a tiny-angle boundary case.
- One, two and eight recovery rounds under both coherent and twirled noise:
  **756 channel cases**.
- **216 sampled sparse-field trajectories**, checked against their corresponding
  dense conditional state, including possible logical errors.
- Per-round syndrome probabilities, logical density matrices and normalized
  Choi matrices (a complete one-round channel comparison).
- The equal-p twirled logical-error baseline `3p² − 2p³` for logical |0>.

Failure means any syndrome probability or analytic error reaches `1e-12`, or
any logical, Choi or conditional-state trace distance reaches `1e-10`.
The verifier exits nonzero and writes its receipt on a numerical comparison
failure. Unexpected exceptions fail immediately. CI retains generated JSON
when present. Unit tests also deliberately reverse the rotation sign and
misassign a correction, showing these errors are detected.

For logical |0>, one equal-angle round leaves a coherent-versus-twirled
trace distance of `2 |cos(a/2) sin(a/2)|³`. Their state fidelities alone can
agree while this off-diagonal logical information differs. Multiple ideal
rounds can accumulate that difference. This is a consequence of the specified
small model, not evidence of hardware performance.

## Resources and receipts

Production's largest physical statevector has eight complex128 amplitudes
(128 bytes); the dense reference's physical density matrix has 64 entries
(1,024 bytes). These are individual array sizes, not total runtime memory.
The receipt separately records whole-process peak RSS, Python traced peak
allocations, wall time, dependency versions, CPU, thread settings, engine and
source hashes, every case and a deterministic case digest.

The profile check precedes Kraus construction and bounds rounds (at most
1,024, further limited by the caller's profile). Its workspace estimate is a
conservative numerical/history allowance, not a limit on the Python process.
Syndrome histories are per-round marginals; this implementation does not
retain an exponential joint history or condition future rounds on it.

`REPORT.md` and `results.json` record the measured run. Reproduction on another
machine should compare numerical tolerances, configuration and source hashes;
wall time, memory, and floating-point hashes need not match across platforms.
