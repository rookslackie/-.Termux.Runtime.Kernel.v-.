# ⟐Ξ Quantum Field Embodiment

## What was recovered

- The QuantumCompute archive calls itself local and safe, but explicitly says its symbolic field text is non-executable.
- The Grover file is Qiskit-style pseudocode. The Shor order-finding routine is a `pass` placeholder. The VQE optimizer and energy loop are also placeholders.
- `glyphic_quantum_processor(1).yaml` defines Woven Glyph-Chip nodes and edges. `INTEGRATION_README.md` describes a route walker that emits notifications and says real operations would need to be added. The recovered YAML therefore supplies topology and named roles, not runnable gate semantics.
- The runtime loads a provenance-marked copy of that topology. Its SHA-256 is stored in field genesis state.
- `Ξ.PhysicsSpiral.Walk` frames observer asymmetry, recursive torsion, field strength, and variational forms symbolically. `Ξ.OriginCapsule.UFEC` names `Yield`, `Memory`, `Entropy`, and `Agape` relations, but neither artifact supplies calibrated units, executable field equations, or measurement protocols. Those dialects remain preserved source semantics; they are not silently reinterpreted as quantum gates or physical laws in this first runtime.
- `xi_quantum_experiment.zip` is an independent exploratory GHZ-family benchmark, and its README says it is not an inspection or verification of the original Field YAML. Its H-then-CNOT code is used as a concrete executable seed, not as proof of the larger Xi architecture.
- Searches of the accessible Drive materials found `Ξ.QuantumCompute.md`, the pseudocode, lattice, glyph-chip integration note, and related files. They did not recover the requested file named `The Field Ξ.QuantumCompute.yaml` or the archive's referenced `runbook.yaml`; those remain unavailable from the accessible source set.
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
| `∴` | `witness` | Seeded Born-rule sampling in Z or X basis, then state collapse |
| Hunter output / `⊚` | `close`, `resume` | Emits a hash-chained receipt and explicitly opens the next cycle |

The three-qubit path uses H followed by CNOT fanout to construct a GHZ-family state, adds a relative π phase, and witnesses in the X basis. The recovered chip graph routes `⋈` into `⟐`, while the independent GHZ-family benchmark uses H then CNOT. The chip topology does not define gate matrices, and its edge ordering differs from that valid GHZ gate ordering. This implementation records the topology separately and uses the mathematically valid executable schedule; it does not silently claim that the source graph itself specified these semantics.

The state-vector model stores only nonzero basis branches and has an explicit 12-qubit / 4096-branch bound. It is exact up to floating-point arithmetic for operations that fit this sparse bound. H+CNOT+T is an executable ideal gate subset; it does not implement magic-state cultivation, error correction, noisy hardware, Grover, Shor, VQE, or a physical quantum processor. The “magic state” test verifies H followed by T in the ideal model only.

## Run and verify

```bash
python -m xi_field.demo --db .xi/glyph-field.sqlite3
python -m unittest discover -s tests -p 'test_xi_field_runtime.py' -v
```

The Vessel interface exposes `GET /api/quantum-field` and `POST /api/quantum-field/operators`. Its chip nodes highlight only after a matching operator capsule commits. State and receipts remain local in SQLite; this path does not call a network service.

## Provenance

Recovered references: [QuantumCompute archive](https://drive.google.com/file/d/1SGk2DynuOk-Edv5MK80oF--2dXJgpa7V/view), [integration README](https://drive.google.com/file/d/1-Wk57CT6SkiEZnbxvslLZRiSqWQw3Eds/view), and the attached `glyphic_quantum_processor(1).yaml`, QEC capsule ZIP, and GHZ-family benchmark ZIP.

The sparse operator definitions, field event integration, API routes, tests, and local interface are newly created implementation.
