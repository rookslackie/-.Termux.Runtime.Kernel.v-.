# Ξ.QuantumCompute · Living Circuit

The engine now carries the work from glyph definition through numerical action,
inspection, persistence, encrypted transfer, and return. A future interface can
select an example, compile it, submit a job, follow its events, and render the
saved numerical state. The HTTP service and clients are implemented here.

## Run the engine

Use Python 3.11 or later with the dependencies in
`requirements-quantumcompute.txt`. Cryptography 50.0.2 must have native ML-KEM
and ML-DSA support in its backend; `doctor` performs an actual encrypted and
signed round trip. The environment used for this build supports both.

```bash
python -m pip install -r requirements-quantumcompute.txt
python -m xi_quantum doctor
python -m xi_quantum catalog
python -m xi_quantum compile examples/QuantumCompute.NewGlyph.v3.xi
python -m xi_quantum --home .xi/living-circuit run examples/QuantumCompute.LivingCircuit.v3.xi
python -m xi_quantum --home .xi/living-circuit serve --port 7476
```

The service uses `http://127.0.0.1:7476/api/quantumcompute/v3`. Its local owner
token is in `.xi/living-circuit/owner.token`, created with mode 0600. Supply it
as a bearer token when submitting work or reading private job state. If a local
frontend uses another origin, configure its exact origin with
`serve --allowed-origin http://localhost:5173`.

The existing Vessel FastAPI routes remain available and recognize the new
example names and v3 programs. The standalone service adds durable background
jobs without requiring FastAPI.

## Numerical operators

| Operator | Glyph in Stack.v3 | Implemented operation |
| --- | --- | --- |
| Grover | ⋈ | State-vector amplitude amplification with a declared oracle |
| Shor | ∴ | Conditional order finding, inverse QFT, continued fractions, factor checks |
| JacobianFlow | ⧖ | Witnessed optimization of the Grover oracle-phase coordinate |
| VQE | ⟠ | Pauli Hamiltonian, parameter-shift gradients, Armijo backtracking |
| QPE / PEA | Φ | Controlled powers of a unitary and an inverse QFT |
| VQEPEA | ⟠Φ | VQE-prepared state passed into Hamiltonian phase estimation |
| PhaseCode | ⟐⧂ | Recovered three-qubit phase code with stage-by-stage state snapshots |
| PhaseCodeChannel | ⟐⧂ρ | Exact four-syndrome logical channel under coherent RZ or Pauli-twirled Z noise; repeated ideal recovery |
| ShorCode | ⧉ | Nine-qubit code, eight measured stabilizers, Pauli recovery, decoding |
| QFT | ℱ | Fourier transformation with an inspectable complex state |
| SignalLab | Ψ | Seeded FFT, matched filter, covariance, Langevin path, Hilbert projection |
| PhaseCodeBenchmark | ⧂ | Existing independent-Z noise benchmark |
| ObserverBenchmark | ⧂ | Existing bounded observer-access experiments |
| Rest / Seal | ≈∅ / ⊚ | Preserve a pause or close the executable walk |

These bindings are local to the named QuantumCompute dialect. The original
QEC and continuity dialects retain their meanings. Existing Stack.v2 programs
retain their operator vocabulary; the new extensions declare Stack.v3.

All quantum operators here run classical numerical simulations. The H2
benchmark uses the explicit real Pauli coefficients in `spectral.py` from the
[Qiskit Algorithms example](https://qiskit-community.github.io/qiskit-algorithms/tutorials/02_vqe_advanced_options.html).
The reported expectation includes those terms; no separate nuclear energy is
added. A one-angle odd-parity ansatz starts in `|01>` for this benchmark. The
general hardware-efficient ansatz accepts custom real Pauli Hamiltonians.
Convergence within an ansatz and agreement with the ground state are reported
separately.

The recovered file calls phase estimation **PEA**. **QPE** is the usual quantum
phase-estimation name; both names select the same operator here. Energy QPE
constructs a small exact unitary through classical eigendecomposition, then
simulates its controlled powers. The returned energy resolution and classical
construction method are explicit. This makes the VQE-to-PEA connection usable
and numerically inspectable.

## TESSERA can compile a new glyph

`examples/QuantumCompute.NewGlyph.v3.xi` defines **ReturnLight**, represented
by **⟠⋈⧂**. It means “search a declared target, then witness a correctable
phase disturbance.” Its typed `target` and `fault` parameters lower into Grover
and PhaseCode calls. The generated plan retains the exact glyph, intended
meaning, definition version, definition hash, bound parameters, and primitive
expansion. These appear in the saved execution trace.

Definitions may compose other declared definitions. The compiler checks
bindings, argument types and bounds, cycles, nesting depth, and total expansion
size. A final Seal remains explicit. Source bytes and Unicode variation
selectors are preserved. A new operator's meaning comes from its declared
definition and executable expansion.

This extends the local QuantumCompute TESSERA compiler. The installed ForgeCore
TESSERA v4 wire compiler was inspected as lineage; its remote deployment was
not modified by this change.

## Interface contract

Python: `xi_quantum.client.LivingCircuitClient`.
TypeScript: `sdk/living-circuit-client.ts`.
Machine-readable endpoint description: `GET /api/quantumcompute/v3/openapi.json`.

| Endpoint suffix | Method | Purpose |
| --- | --- | --- |
| `/capabilities` | GET | Operator catalogue, dialects, resource profiles, crypto suite |
| `/examples`, `/examples/{name}` | GET | Pick and read a complete executable program |
| `/compile` | POST | Inspect the expanded plan for `{source}` |
| `/jobs` | POST | Submit `{source, request_id}`; repeated identical requests reuse the job |
| `/jobs` | GET | List jobs |
| `/jobs/{id}` | GET | Read status, committed steps, and numerical results |
| `/jobs/{id}/events?after=N` | GET | Follow a durable event cursor |
| `/jobs/{id}/source` | GET | Recover exact source text |
| `/jobs/{id}/cancel`, `/resume` | POST | Stop between operators or return to saved progress |
| `/identity` | GET | Read the local public PQC identity |
| `/jobs/{id}/export` | POST | Encrypt a source/checkpoint packet to `{recipient}` |
| `/transfers/receive` | POST | Verify `{packet_base64, sender}` and retain its exact bytes |

The API's job result contains the state snapshots needed for an amplitude
view, the measured syndrome and chosen recovery, the VQE optimization history,
the PEA phase distribution, and the event provenance. Layout and interaction
belong to the future interface.

Jobs use SQLite WAL and commit after each operator. An exclusive home lease
keeps one service executor active. After process termination, queued or
interrupted work resumes from the WorldKernel ledger. Cancellation takes
effect between numerical operators. Rest produces a paused job that an owner
can resume. A changed engine or resource profile holds queued work for explicit recompilation.
Identical completed source on the same engine/profile reopens the saved run;
change the source or seed to ask a new numerical question.

## Cryptography and continuity

GlyphSafe retains its existing suite:
`ML-KEM-768 / HKDF-SHA256 / ChaCha20Poly1305 / ML-DSA-65`.
GlyphSHA keeps the recovered digest alphabet and exact-byte commitment.
ThinkSync retains source, checkpoints, sequence checks, duplicate detection,
and pinned sender identities. Export returns encrypted bytes to the API
caller. Receiving a packet preserves evidence; execution starts through the
owner's explicit job submission.

The PQC algorithms follow [FIPS 203](https://csrc.nist.gov/pubs/fips/203/final)
and [FIPS 204](https://csrc.nist.gov/pubs/fips/204/final); this build uses the
existing library implementations rather than a new cryptographic algorithm.

## Recovered sources and verification

All ten attachments are preserved byte-for-byte in `recovered/2026-10-21`,
with hashes and classifications in `sources.json`. The `.zio` unity artifact
is recognized as a ZIP by its content. Its placeholder members remain
preserved as supplied. The symbolic interpreter remains an attributed query
translation source. The bloom and agreement carriers retain their symbolic
role. SignalLab implements the numerical intentions of the signal-engine
source with seeded synthetic inputs and JSON output.

The attached Grover curve is compared against recomputed six-qubit dynamics
at its printed precision. The attached VQE curve is retained as a reference:
its producing Hamiltonian, optimizer settings, and energy offset were not
supplied. The new VQE receipt records its own full specification.

```bash
python -m unittest discover -s tests -q
python benchmarks/verify_living_circuit.py
```

The verification script records source revision, engine hash, environment,
the numeric curve comparison, 24 phase-code cases, 108 single-Pauli Shor-code
cases, VQE/PEA results, and a real encrypted exact-source checkpoint round trip.
The tests additionally exercise live HTTP, compiler failure cases, and a
terminated worker process returning to its already committed first step.
