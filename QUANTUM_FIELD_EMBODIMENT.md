# ⟐Ξ Quantum Field Embodiment

## What was recovered

- The QuantumCompute archive calls itself local and safe, but explicitly says the symbolic field text *in that archive* is non-executable. Hunter identifies a separate artifact, `The Field Ξ.QuantumCompute.yaml`, as functional; the archive note does not describe or override that distinct artifact.
- The Grover file is Qiskit-style pseudocode. The Shor order-finding routine is a `pass` placeholder. The VQE optimizer and energy loop are also placeholders.
- `glyphic_quantum_processor(1).yaml` defines Woven Glyph-Chip nodes and edges. `INTEGRATION_README.md` describes a route walker that emits notifications and says real operations would need to be added. The recovered YAML therefore supplies topology and named roles, not runnable gate semantics.
- The runtime loads a provenance-marked copy of that topology. Its SHA-256 is stored in field genesis state.
- `Ξ.PhysicsSpiral.Walk` frames observer asymmetry, recursive torsion, field strength, and variational forms symbolically. `Ξ.OriginCapsule.UFEC` names `Yield`, `Memory`, `Entropy`, and `Agape` relations, but neither artifact supplies calibrated units, executable field equations, or measurement protocols. Those dialects remain preserved source semantics; they are not silently reinterpreted as quantum gates or physical laws in this first runtime.
- `xi_quantum_experiment.zip` is an independent exploratory GHZ-family benchmark, and its README says it is not an inspection or verification of the original Field YAML. Its H-then-CNOT code is used as a concrete executable seed, not as proof of the larger Xi architecture.
- A traversal of the accessible `Xi.Field` Drive folder surfaced field-state, bridge, reflection, glyph, and capsule records, but not the separately named functional Field YAML. That YAML remains the user's identified source anchor; this implementation does not claim to have recovered or replaced it. The archive's referenced `runbook.yaml` also remains unavailable in the accessible source set.
- `Ξ_Capsule_QuantumFieldQEC_v1.zip` contains symbolic capsule metadata with `phase_lock: 0.9999`; it contains no executable QEC code or fidelity measurement. That value is not adopted as a runtime metric.

## The executable body

The field runtime is a new local synthesis integrated into `WorldKernel`, not a recovered implementation. Each operation updates a sparse complex-amplitude state inside the existing SQLite entity and commits an append-only capsule with causal parent, actor identity, operator receipt, event hash, and hash-chain predecessor.

| Source role | Local operation | Executed behavior |
|---|---|---|
| `Ψ` | `reference` | Records the register boundary and initial basis state |
| `⟐` | `hadamard` | Applies the exact Hadamard matrix to one register |
| `⋈` | `cnot`, `compress` | Applies controlled-X or canonicalizes sparse branches |
| phase extension | `phase`, `t` | Applies a relative phase; `t` is the ideal non-Clifford T operator |
| `Self₁₇` / `Xi` | capsule state delta | Stores sparse state in persistent local entity memory |
| `⧂` | `witness`, `phase_syndrome` | Seeded Born-rule sampling or commuting stabilizer measurements with state collapse |
| `∴` | committed capsule state delta | Yields each operator's updated field state and receipt into persistent local memory |
| Hunter output / `⊚` | `close`, `resume` | Emits a hash-chained receipt and explicitly opens the next cycle |

The phase-code experiment also carries its operation through the `QuantumFieldQEC.v1` stack: `⟐` prepares the local basis relation, `⋈` encodes or applies recovery, `⧂` records the measured syndrome, `∴` yields the decoded state into the capsule ledger, and `⊚` closes the cycle. The formal matrix/code operation is defined by the runtime; the glyph mapping preserves the capsule's declared order and does not assert that a glyph is a physical gate.

The three-qubit path uses H followed by CNOT fanout to construct a GHZ-family state, adds a relative π phase, and witnesses in the X basis. The recovered chip graph routes `⋈` into `⟐`, while the independent GHZ-family benchmark uses H then CNOT. The chip topology does not define gate matrices, and its edge ordering differs from that valid GHZ gate ordering. This implementation records the topology separately and uses the mathematically valid executable schedule; it does not silently claim that the source graph itself specified these semantics.

The state-vector model stores only nonzero basis branches and has an explicit 12-qubit / 4096-branch bound. It is exact up to floating-point arithmetic for operations that fit this sparse bound. H+CNOT+T is an executable ideal gate subset.

`xi_field.phase_code_demo` adds a bounded local error-correction experiment: prepare an ideal one-qubit T state, encode it in the three-qubit phase-flip repetition code, inject one deterministic Pauli-Z fault, measure the commuting stabilizers `X0X1` and `X1X2`, apply the syndrome-selected Z recovery, and decode. Tests cover all three single-fault locations and check that decoding recovers the original state and returns both recovery registers to `|00>`.

This path is a three-qubit stabilizer-code simulation, not Google's magic-state cultivation protocol. It assumes exactly one injected Z fault per code block. It does not model general coherent noise, repeated-fault decoding, physical measurement errors, surface-code transfer, Grover, Shor, VQE, or quantum hardware. The reported overlap is computed from the local state vector; it is not hardware fidelity or cultivation yield.

## Run and verify

```bash
python -m xi_field.demo --db .xi/glyph-field.sqlite3
python -m xi_field.phase_code_demo --db .xi/phase-code.sqlite3
python -m unittest discover -s tests -p 'test_xi_field_runtime.py' -v
```

Run the phase-code command twice to check idempotent recovery. The first run intentionally reopens the SQLite-backed runtime after fault injection; it should report syndrome `[-1, -1]`, recovery on register `1`, local state overlap `1.0`, and a valid event hash chain. The repeated run recovers the same ten-capsule ledger without replaying state changes.

The Vessel interface exposes `GET /api/quantum-field` and `POST /api/quantum-field/operators`. Its chip nodes highlight only after a matching operator capsule commits. State and receipts remain local in SQLite; this path does not call a network service.

## Provenance

Recovered references: [QuantumCompute archive](https://drive.google.com/file/d/1SGk2DynuOk-Edv5MK80oF--2dXJgpa7V/view), [integration README](https://drive.google.com/file/d/1-Wk57CT6SkiEZnbxvslLZRiSqWQw3Eds/view), and the attached `glyphic_quantum_processor(1).yaml`, QEC capsule ZIP, and GHZ-family benchmark ZIP. Hunter's identified functional Field YAML remains distinct and has not yet been surfaced in the accessible Drive folder traversal or local source bundle.

The sparse operator definitions, field event integration, one-fault recovery path, API routes, tests, and local interface are newly created implementation. They are not presented as the contents of the separate functional Field YAML.
