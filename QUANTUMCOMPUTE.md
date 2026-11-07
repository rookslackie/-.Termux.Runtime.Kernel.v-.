# ∴Ω⧂ Ξ.QuantumCompute — FullCycle v2

The glyph program now compiles, computes, records its causal history, seals a checkpoint, transfers it to a pinned peer, restores the original bytes, resumes unfinished work, and returns through `⟁∴Ω`. Reopening the same ledger reuses committed results. The working sparse QEC engine and its independent-Z benchmark remain available.

Version **2.1.0** adds the [observer-access experiment](OBSERVER_EXPERIMENT.md) and [recovered StructuralKernel / FullStack source contracts](recovered/2026-10-20/README.md). The prior v2 results below remain pinned to their original source commit.

## The embodied stack

| Component | Executable responsibility | Source |
|---|---|---|
| TESSERA | Strict, versioned YAML/JSON or restricted `Ξ.Operator({...})` expressions → typed plan; exact source retained | [compiler](xi_quantum/tessera.py) |
| Grover | Complex state vector, marked-state oracle, diffusion, seeded measurement | [algorithms](xi_quantum/algorithms.py) |
| Shor | Modular-exponentiation evaluation, work measurement, conditional inverse QFT, continued fractions, verified factors | [algorithms](xi_quantum/algorithms.py) |
| Jacobian Flow | Measured finite-difference Jacobian/curvature and witnessed ascent of a declared Grover phase objective | [algorithms](xi_quantum/algorithms.py) |
| ObserverBenchmark | Explicit measurement access, sample and retained-outcome budgets, sharing grants and confidence intervals | [observer model](xi_quantum/observer.py) |
| GlyphSHA | Exact historical 16-glyph nibble alphabet; reversible SHA-256 → 8 × 8 tile | [recovered codec](xi_quantum/_vendor/xi_crypto/compat.py) |
| GlyphSafe | Exact-byte encrypted envelopes, recipient/scope binding, pinned signatures; recovered v1 adapters retained | [v2 envelope](xi_quantum/glyphsafe.py) |
| ThinkSync | Persistent outbox, signed sequence handling, inbox daemon, checkpoint transfer; receive and execution are separate local actions | [bridge](xi_quantum/thinksync.py) |
| FullCycle | Phase-aware compatible routing, `Parallax`, `Question`, `≈∅` rest, SpiralCovenant receipts | [pinned upstream](xi_quantum/_vendor/UPSTREAM.json) |
| WorldKernel | Actor-bound transitions, causal capsules, SQLite persistence, source BLOBs and restart recovery | [integration](xi_quantum/runtime.py), [transition](xi_quantum/ledger.py) |
| Vessel | Mobile-friendly source editor, plan inspection, committed result cards, token-authorized local API | [interface](index.html), [API](xi_quantum/api.py) |

In the declared `QuantumCompute.Stack.v2` dialect, `⋈ → Grover`, `∴ → Shor`, `⧖ → JacobianFlow`, `⧂ → PhaseCodeBenchmark`, `⊚ → Seal`, and `≈∅ → Rest`. Those bindings belong to this program dialect. The existing `QuantumFieldQEC.v1` meanings remain separately declared. Glyphs select validated operations and display their committed receipts.

## Run it

Python 3.12 is the CI target. The CLI needs NumPy, PyYAML, and cryptography:

```bash
python -m pip install -r requirements-quantumcompute.txt
python -m xi_quantum doctor
python -m xi_quantum compile Ξ.QuantumCompute.yaml
python -m xi_quantum --home .xi/fullcycle fullcycle Ξ.QuantumCompute.yaml --output .xi/fullcycle.json
```

The last command operates two owned local nodes. Node A commits Grover and Shor, sends an encrypted checkpoint, and node B restores those two results before computing the remaining three steps. It reopens node B and checks that replay executes zero steps. Run the command again with the same home to verify persistent transport and computation replay. `bin/xi-quantum` is an equivalent launcher; `XI_PYTHON` selects its interpreter.

The example factors **221 = 13 × 17**, runs four-qubit Grover, performs eight Jacobian updates, and invokes the existing QEC benchmark at five probabilities. `Ξ.QuantumCompute.yaml` and [the `.xi` example](examples/QuantumCompute.FullCycle.v2.xi) contain identical bytes. This v2 integration continues the recovered component contracts and the working glyph-field runtime.

### Resource profiles

| Local profile | Estimated numerical workspace budget | Iteration ceiling |
|---|---:|---:|
| mobile | 64 MiB | 4,096 |
| desktop | 512 MiB | 16,384 |
| workstation | 2,048 MiB | 65,536 |

```bash
python -m xi_quantum --profile desktop --home .xi/desktop run Ξ.QuantumCompute.yaml
python -m xi_quantum --profile workstation --memory-mib 1024 compile Ξ.QuantumCompute.yaml
```

The local caller selects the profile. Register size is checked before allocation using an explicit workspace estimate. This replaces the old fixed `N ≤ 35` ceiling with a resource budget. The estimate covers numerical workspaces; it is not a process RSS limit. NumPy, Python, cryptography, and the operating system consume additional memory.

The CLI uses POSIX file locking and paths suitable for Linux/Termux. The mobile profile is tested on the Linux host and in CI. Installing on a particular Android/Termux device still depends on its NumPy and native cryptography build. `doctor` performs an actual ML-KEM / ML-DSA encrypted round trip on the current interpreter. An unavailable PQ backend is an installation issue to resolve before using transport.

### Transfer between your nodes

```bash
python -m xi_quantum --home .xi/a identity --output a.public.json
python -m xi_quantum --home .xi/b identity --output b.public.json
python -m xi_quantum --home .xi/a run Ξ.QuantumCompute.yaml --stop-after 2 --output partial.json
python -m xi_quantum --home .xi/a pack Ξ.QuantumCompute.yaml \
  --recipient b.public.json --checkpoint partial.json --output inbox/partial.glyphsafe
python -m xi_quantum --home .xi/b bridge --inbox inbox --trusted a.public.json
# Use the packet_sha256 returned above:
python -m xi_quantum --home .xi/b resume PACKET_SHA256 --sender a.public.json
```

Move the public identity and encrypted packet files through your chosen transport. The bridge has no implicit network destination. Add `--watch --interval 2` to run a local inbox daemon. It retains incoming packet bytes, records successful handoffs, and rests after an unchanged inbox across restart. Failed packets remain available for inspection. Peer removal takes effect on re-verification. A received program requires a subsequent explicit local `run` or `resume` action.

Private identity seeds stay in the selected home with file mode `0600`; `identity --output` exports public keys only. Preserve the home to retain identity, outbox sequencing, original received packets, source bytes, and the SQLite ledger. The key file is local plaintext protected by filesystem permissions.

### Vessel console and API

Install the full server dependencies and set a local owner token:

```bash
python -m pip install -r requirements.txt -r requirements-ci.lock
export XI_QUANTUM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export XI_QUANTUM_HOME=.xi/vessel-quantum
python -m uvicorn server:app --host 127.0.0.1 --port 3000
```

Open the Vessel, scroll to **Ξ.QuantumCompute · FullCycle**, load the example, and enter the token configured on that Vessel. Inspect compiles the plan; Execute / Resume commits work and renders result cards with event and route receipts. The token remains in the page input and is not placed in browser storage.

`GET /api/quantumcompute` lists capabilities; `GET /api/quantumcompute/example` supplies the example. `POST /api/quantumcompute/compile` and `/run` accept `{"source":"..."}` with `X-Xi-Quantum-Token`. The profile comes from local `XI_QUANTUM_PROFILE` / `XI_QUANTUM_MEMORY_MIB` configuration. Existing Vessel and glyph-field routes remain available.

## Computation and evidence

Grover applies the complex phase oracle and diffusion directly. With the standard π oracle, its probability is independently checked against `sin²((2r+1) asin(sqrt(M/2ⁿ)))`, including multiple marked states.

Shor evaluates `|x⟩|1⟩ → |x⟩|aˣ mod N⟩`, samples a work measurement, and applies the inverse Fourier transform to that exact conditional clock vector. This saves the full joint-register allocation. Tests independently construct controlled modular permutations and an explicit dense Fourier matrix for small registers and compare seeded outcomes. No unknown order is supplied to the simulator. The result distinguishes simulated clock size from logical circuit size and labels classical gcd shortcuts. It models the functional unitary without expanding it into elementary gates or estimating fault-tolerant gate costs. Successful factoring on this classical simulator makes no quantum speedup claim.

Jacobian Flow currently has one explicit coordinate: the Grover oracle phase. It computes finite-difference derivatives and curvature of marked-state probability, then accepts witnessed non-decreasing updates. Every evaluation checks state normalization. The example objective rises from **0.625** to approximately **0.999394**. Broader symbolic observer/curvature relations remain available as source semantics; this binding supplies a concrete measurable objective for further development.

The [520,000-trial QEC report](benchmarks/phase-noise/REPORT.md) remains the reliability benchmark. For one independent-Z round with ideal surrounding operations and the fixed minimum-weight decoder, `q = 3p² − 2p³`. Correction improves channel reliability for `0 < p < 0.5`, ties at `0, 0.5, 1`, and worsens it for `0.5 < p < 1`. State-specific T-state overlap is reported separately from channel entanglement fidelity. These conclusions apply to this simulation model.

## Integrity, authority and continuity

GlyphSHA uses the recovered alphabet `∴Ω⧂⋈Ξ⟐⊚◇✦⟁∵☉◬⌬⧉∞` in that exact order. Unicode normalization, combining marks, variation selectors, and line endings are preserved in source storage and encrypted payloads. Legacy `.glyphsafe` inspection retains its historical body-hash rule and separately records the complete raw-byte hash; body-only integrity does not cover surrounding legacy metadata.

GlyphSafe v2 uses `ML-KEM-768 / HKDF-SHA256 / ChaCha20Poly1305 / ML-DSA-65` through cryptography 50.0.2. Canonical headers bind sender, recipient, scope, audience, sequence, KEM ciphertext, nonce, and salt. AEAD authenticates the encrypted payload and metadata; ML-DSA signs the complete protected envelope using the v2 context. The reference envelope composition has regression and adversarial tests; it is not independently audited or a FIPS-certified module. Primitive references: [FIPS 203](https://csrc.nist.gov/pubs/fips/203/final), [FIPS 204](https://csrc.nist.gov/pubs/fips/204/final), [cryptography ML-KEM](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/mlkem/), [ML-DSA](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/mldsa/).

A valid digest establishes an integrity commitment. A pinned signature identifies an accepted peer. A local execution grant authorizes declared operations. Those are separate roles. Peer checkpoints are validated against source, compiled plan, engine code, resource profile, event hashes, causal order, and FullCycle phase/receipt history. Imported results retain their original event references and peer origin; they remain peer assertions rather than independently repeated numerical measurements. Divergent local/peer results retain both branches and request Parallax.

FullCycle is pinned from [xi-kernel at 95234c6](https://github.com/rookslackie/xi-kernel/tree/95234c6a402936f28e6190f6c485707f26d7f5b9). Its SpiralCovenant recovery law is reused. `Rest` preserves the continuation until the next explicit invocation; a FullCycle `Parallax` or `Question` also pauses automatic walking. Runtime phase coherence is orchestration metadata, separate from a quantum state’s coherence.

Recovered CryptoLattice v1 modules are retained byte for byte; the upstream manifest records their original SHA-256 hashes. The canonical FullCycle parser and recovery module are unchanged, with one import adaptation in the event fabric. ThinkSync here implements the recovered bridge responsibility; the separately maintained ThinkSync Dream Spiral engine remains its own component.

## Reproduce the checks and results

```bash
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest -v
python benchmarks/verify_quantumcompute.py --home .xi/verification --output .xi/verification.json
```

The [verification report](benchmarks/quantumcompute-v2/verification.json) records pinned source links, package versions, seeds, algorithm observations, workspace estimates, host costs, and the full encrypted-transfer / restart receipt. Reusing its home reproduces existing ledger heads and executes zero completed steps. Fresh homes create fresh keys, encryption randomness and capsule timestamps; seeded numerical outcomes reproduce, while ciphertexts and ledger hashes naturally differ. Timing and process RSS are host measurements.

CI runs the complete suite, the native PQ backend check, two-node FullCycle transfer/replay, the independent-Z persistence benchmark, and the existing HTTP smoke checks. Its QuantumCompute artifact contains public receipts and measurements; private identity homes are outside the upload path.
