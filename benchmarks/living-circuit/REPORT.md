# Living Circuit execution receipt · 2026-10-21

Implementation source: `3ffcb260276880127307d055617ece1c361b3e75`.
Engine digest: `5570dbc984d58993759eb7863d65f780b0f27e8c83910e4a81c22477f52a062a`.
The complete numerical results, source commitments, expanded glyph plan, and
encrypted-transfer receipts are in `results.json`.

| Check | Observed result |
| --- | --- |
| Complete test suite | 93 passed; three existing framework deprecation warnings |
| New engine tests | 34 passed, including actual worker-process termination and return |
| Syntax and undefined-name gate | Passed with the repository's flake8 selection |
| Installed wheel | Packaged examples, live HTTP client, compilation, execution, and ledger integrity passed outside the source checkout |
| Attached source preservation | All 10 attachment hashes matched |
| Grover curve | All eight supplied rows matched recomputed six-qubit dynamics at six-decimal CSV precision |
| Three-qubit phase code | All 24 input/fault cases recovered with fidelity within 1e-12 of one |
| Nine-qubit Shor code | All 108 input/single-Pauli cases recovered with fidelity within 1e-12 of one |
| VQE | Energy -1.85727503020238 for the explicit reduced H2 Pauli benchmark; agreement with its classical matrix reference within 1e-9 |
| PEA / QPE | Exact 0.375 phase recovered on the selected grid |
| VQE → PEA | Prepared-state energy estimate within half of its reported finite-precision energy bin of the reference |
| TESSERA | New glyph ⟠⋈⧂ compiled to Grover and PhaseCode with definition version, meaning, bound parameters, and source hash |
| GlyphSafe / ThinkSync | Actual signed/encrypted exact-source checkpoint transfer; duplicate receipt idempotence; restart without reexecuting completed steps |
| Signal operations | Seeded synthetic FFT recovered dominant 50 Hz and 120 Hz components |

The VQE energy uses only the explicitly listed Hamiltonian terms. The attached
VQE CSV retains its own supplied energy values; its producing Hamiltonian and
energy offset were not provided. The two records are preserved separately.

The numerical circuits are classical simulations. PQC operations use the
existing native ML-KEM-768 and ML-DSA-65 implementations, HKDF-SHA256, and
ChaCha20Poly1305. The interface boundary is an implemented local HTTP API with
OpenAPI, durable cursor events, and Python and TypeScript clients.

Reproduce from the implementation revision or a later revision with the same
engine digest:

```bash
python -m pytest -q
python benchmarks/verify_living_circuit.py --output /tmp/living-circuit-results.json
```

Publication preserves the exact implementation tree of the original locally tested commit. The numerical receipt was regenerated against the published implementation revision above.
