# Coherent phase-code execution receipt · 2026-10-23

Implementation revision: `4d985c7082155464f5321d8ae291d3a523dcb73e`.
Engine SHA-256: `b567db1bbef737c0bf9bfe1f0575a0435cdc99151f8d8d8e639107e68067fb30`.
The working tree was clean when the numerical receipt was generated. Later
receipt-only commits retain this implementation and engine digest.

## Observed results

| Check | Measured result | Acceptance |
| --- | --- | --- |
| Channel comparisons against separate dense oracle | 756 cases passed | All cases |
| Sampled sparse-field conditional-state comparisons | 216 cases passed | All cases |
| Maximum per-round syndrome-probability error | 4.108e-15 | < 1e-12 |
| Maximum logical-state trace distance | 2.193e-15 | < 1e-10 |
| Maximum normalized Choi trace distance | 2.223e-16 | < 1e-10 |
| Maximum sampled conditional-state trace distance | 1.961e-15 | < 1e-10 |
| Maximum twirled binomial-baseline error | 8.882e-16 | < 1e-12 |
| Complete repository suite | 108 tests passed; three existing framework deprecation warnings | Pass |
| Focused new tests | 15 passed | Includes reversed-sign and wrong-correction negative controls |
| Syntax/undefined-name check | No findings with repository flake8 selection | Pass |
| Existing Living Circuit receipt | Reproduced 24 phase-code cases, 108 Shor-code cases, spectra, attached Grover curve, and encrypted FullCycle | Pass |
| Installed 3.1.0 wheel outside checkout | Example compiled; exact-source encrypted transfer, ledger integrity and zero-step replay passed | Pass |

`results.json` contains every case, configuration, tolerances, source hashes,
environment, and resource measurements. `installed-wheel.json` records the
installed-package check. `living-regression.json` records the existing engine
regression receipt without replacing the historical October 21 receipt.

The oracle uses separately implemented dense matrices; these checks were
executed locally by Codex. They are not third-party replication or quantum
hardware experiments. The stated precision applies only to this finite set
of small classical numerical experiments and its specified ideal recovery.

## Concrete model difference

For logical |1>, angles `[0.2, 0.2, 0.2]` radians and eight ideal recovery
rounds, the coherent-versus-twirled logical-state trace distance was
**0.01561766946862589**. This is the largest difference in the recorded grid.
It is a model difference, not a reference error. Fidelity to an input alone
can conceal logical off-diagonal differences; the full density/Choi checks
retain them. The one-round |0> comparison also matches the closed form
`2 |cos(a/2) sin(a/2)|³` in a separate unit test.

## Measured resources

Linux x86_64, AMD EPYC 9V74; Python 3.12.14; NumPy 2.5.4. OMP, OpenBLAS and
MKL thread environment variables were each set to one. The receipt includes
the NumPy/BLAS build configuration. No GPU was used.

- Full verifier wall time: **28.521 seconds**, including Python allocation tracing.
- Whole verifier process peak RSS: **45,764,608 bytes (43.64 MiB)**.
- Python traced peak allocations: **1,348,636 bytes**.
- Individual production physical statevector: **128 bytes**.
- Individual dense reference physical density matrix: **1,024 bytes**.

RSS includes Python, imported libraries and the whole verification run.
Individual array sizes do not describe total memory consumption. These are
single-run observations, not performance guarantees or throughput benchmarks.

## Integration correction

Registering the new operator initially diluted the existing fabric coherence
calculation and suppressed an earlier Parallax pause. Execution and ledger
verification now share a stable v3.0 routing cohort, extended only by operators
used in the compiled plan. The original Parallax test passes, and a regression
test confirms that an unused future catalogue entry cannot alter the cohort.

Reproduction commands and model boundaries are in [README.md](README.md).
CI runs the dense comparison and retains its generated JSON artifact.
