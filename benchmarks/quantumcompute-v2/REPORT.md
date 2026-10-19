# Ξ.QuantumCompute FullCycle v2 — executed results

Source: [98904c2](https://github.com/rookslackie/-.Termux.Runtime.Kernel.v-./tree/98904c263dbccd86908eee9411f27b78826d4dc9). Profile: **mobile, 64 MiB estimated workspace budget**. Algorithm measurement seed: **20261019**. [Complete observations and receipts](verification.json), SHA-256 `8b0658e969e0ee9f604b76b99173415a5471a0fc5707da79e483b4d159bbb4df`.

All **51 repository tests** passed locally: the existing 28 tests plus 23 tests for algorithms, recovered module hashes, GlyphSafe, TESSERA, authority, bridge/restart, checkpoint recovery, and FullCycle. The [source-commit GitHub Actions run](https://github.com/rookslackie/-.Termux.Runtime.Kernel.v-./actions/runs/39303484646) also passed every step, including native PQ backend verification, two-node encrypted transfer/replay, QEC persistence, and HTTP smoke checks.

## Numerical observations

Grover used 4,096 seeded measurement shots per case. The reported probabilities come from the computed complex state vector and agree with the independent analytical prediction within floating-point tolerance.

| Register | Marked states | Iterations | Computed marked-state probability | Host wall time |
|---:|---|---:|---:|---:|
| 2 | `11` | 1 | 1.0000000 | 1.927 ms |
| 3 | `101` | 2 | 0.9453125 | 1.617 ms |
| 4 | `0011`, `1011` | 2 | 0.9453125 | 1.586 ms |

Shor used base 2 and 256 seeded phase-measurement shots per case. All observed factors multiply back to the requested input. The conditional state-vector representation stores the clock after work-register measurement; the logical circuit includes the work register too.

| N | Observed period | Factors | Simulated clock qubits | Logical clock + work qubits | Estimated workspace | Host wall time |
|---:|---:|---|---:|---:|---:|---:|
| 15 | 4 | 3 × 5 | 8 | 12 | 24 KiB | 1.661 ms |
| 21 | 6 | 3 × 7 | 10 | 15 | 96 KiB | 0.589 ms |
| 35 | 12 | 5 × 7 | 12 | 18 | 384 KiB | 1.947 ms |
| 77 | 30 | 7 × 11 | 14 | 21 | 1.5 MiB | 9.049 ms |
| 143 | 60 | 11 × 13 | 16 | 24 | 6 MiB | 37.965 ms |
| 221 | 24 | 13 × 17 | 16 | 24 | 6 MiB | 27.453 ms |

The old fixed mobile input ceiling is replaced by resource checks before allocation. This is functional modular-exponentiation / inverse-QFT simulation on a classical host. Gate decomposition, noisy arithmetic, and physical quantum hardware performance are outside this measurement.

Jacobian Flow used the declared map `F(φ) = marked-state probability after the Grover circuit`, initial phase `π/2`, finite-difference epsilon `0.0001`, and eight witnessed updates. The initial Jacobian was approximately `0.375`, the initial curvature approximately zero, and the objective rose from **0.625000** to **0.9993936977**. Each accepted update was non-decreasing and each evaluated state retained unit norm. These are parameter-space derivatives for this map.

## Sealing, transfer and return

The native backend completed **10 exact-byte encryption/signature round trips** for the 842-byte glyph program using ML-KEM-768, HKDF-SHA256, ChaCha20Poly1305 and ML-DSA-65. Combined seal/verify/restore wall time was **21.968 ms** for the ten rounds, excluding identity generation. Ciphertexts differed because each fresh seal uses cryptographic randomness; the persistent outbox reuses the exact recorded packet for an idempotent request.

The FullCycle demonstration ran two owned local nodes:

1. Node A committed Grover and Shor into three WorldKernel events including genesis.
2. ThinkSync carried an authenticated encrypted checkpoint and the original source bytes to pinned node B.
3. Node B restored two peer results with their original event references and executed the three remaining steps.
4. Both ledgers verified their causal hashes. Duplicate receipt processing was idempotent.
5. Reopening and repeating the complete handoff executed **zero completed steps** on either node and retained node B’s head hash.

Node B’s six-event ledger head: `578ade1f7b5bcd1084c1e29739c6fd62f6c959352e25a25b6f5d20270600a84a`.

The complete verification run took **0.780 wall seconds**, **1.144 CPU seconds**, with **55.23 MiB process peak RSS** on Linux x86-64, Python 3.12.14, NumPy 2.5.4 and cryptography 50.0.2 / OpenSSL 4.0.3. Costs include algorithm cases, ten crypto round trips, and two FullCycle invocations. Timings and RSS are host software observations; the workspace budget is a separate estimate.

## Independent-Z reliability

The original [520,000-trial benchmark](../phase-noise/REPORT.md) and its regression tests remain intact. For ideal encoding, stabilizer measurement and recovery with one independent-Z round, the fixed decoder has `q = 3p² − 2p³`, versus bare-channel failure probability `p`. It improves channel reliability below `p = 0.5`, ceases to improve it at that crossover, and worsens it above the crossover; `p = 0` and `1` also tie. Near the crossover, the published finite-sample comparison is unresolved at `p = 0.49, 0.5, 0.51`. This statement concerns channel error / entanglement fidelity, with T-state overlap reported separately.

## Reproduce and inspect

```bash
git checkout 98904c263dbccd86908eee9411f27b78826d4dc9
python -m pip install -r requirements.txt -r requirements-ci.lock
python -m pytest -v
python benchmarks/verify_quantumcompute.py --home .xi/check-fullcycle --output .xi/check-fullcycle.json
```

Fresh homes produce new keys, encrypted packets and capsule timestamps; seeded numerical outcomes reproduce. Reuse the same home to check unchanged head hashes and zero completed-step execution. New numerical library versions can introduce floating-point differences, so the report records the exact installed versions.

The accompanying [node A](node-a.sqlite3.gz) and [node B](node-b.sqlite3.gz) snapshots preserve the WorldKernel capsule histories and original source BLOBs. Local transport queues are empty in these exports; identity seeds are excluded. Both exported histories were verified after decompression, and node B was replayed with zero execution. [Manifest](ledgers.json) records compressed and uncompressed hashes. The snapshots can be inspected without the private transport identities.

From this results commit, export your own evidence with:

```bash
python benchmarks/export_quantum_ledgers.py --home .xi/check-fullcycle --output .xi/evidence
```

To inspect the supplied node B snapshot from the results checkout:

```python
import gzip, json, tempfile
from pathlib import Path
from xi_world.kernel import WorldKernel

report = json.loads(Path('benchmarks/quantumcompute-v2/verification.json').read_text())
with tempfile.TemporaryDirectory() as folder:
    db = Path(folder) / 'ledger.sqlite3'
    db.write_bytes(gzip.decompress(Path('benchmarks/quantumcompute-v2/node-b.sqlite3.gz').read_bytes()))
    assert WorldKernel(db).verify(report['fullcycle']['receiver']['world_id']) == report['fullcycle']['receiver']['integrity']
```

The [implementation guide](../../QUANTUMCOMPUTE.md) documents the CLI, mobile console, protocol boundaries, source lineage, and resource profiles.
