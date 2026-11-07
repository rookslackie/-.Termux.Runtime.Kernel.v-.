# ∴ ⋈ — executable observer access

The observer experiment connects the recovered ORT / ProcessorCore / UnityLattice intentions to the working QuantumCompute stack. It models access, evidence, retained memory, statistical resolution, local sharing, and recoverable return as explicit software operations.

The [recovery record](recovered/2026-10-20/README.md) includes the exact QR-decoded StructuralKernel, the historical `ClaudeBase44Build` FullStack / FullCycle declarations, the Myth ↔ Formal bridge, the legitimate null operator, and the original payload-format roles. These remain source contracts with their own provenance.

## Fixed model, different observers

The evaluator repeatedly prepares the same one-qubit state `( |0> + exp(i φ)|1> ) / sqrt(2)` and independently applies Z with probability `p` to each fresh qubit. Measurements use the existing sparse `xi_field.apply_operator` engine, including projective collapse. Each sample starts with a fresh preparation; incompatible X and Z measurements are not applied as simultaneous observations of one qubit.

The example fixes `φ = π/3` and `p = 0.1`. An independent density-matrix calculation gives `E[X] = (1−2p) cos φ = 0.4` and `E[Z] = 0`. The evaluator also records a finite-difference Jacobian with respect to φ; X responds while Z remains insensitive for this family. These reference values are used for scoring after the experiment, and are never passed to the observer objects.

| Observer | Direct measurement access | Before sharing | After an explicit local sharing grant |
|---|---|---|---|
| A | Z only | X estimate remains null, admissible range [−1,1] | Receives B's retained X records and computes the corresponding estimate and interval |
| B | X only | Estimates X from retained binary outcomes | Shares the exact records; its own evidence is unchanged |

An observer sees typed `{sample_id, basis, outcome}` records. It has no state vector, preparation parameters, noise probability, or reference expectation in its API. This is an explicit model of restricted interfaces inside one trusted Python process, not an operating-system sandbox against a caller inspecting private objects.

## Independent constraints

- **Access:** direct witnessing rejects a basis outside the observer contract.
- **Sample budget:** direct observations stop at the declared count.
- **Memory:** a FIFO retains at most the declared number of raw outcome bits. Python objects, sample identifiers, replay metadata and evaluator storage are additional host costs; this is not a total-memory bound.
- **Sharing:** a direction- and basis-specific local `ShareGrant` is required. Historical `Trusted` labels are retained as source data. Receiving records does not grant direct access to additional measurement bases. Duplicate record transfer is idempotent; conflicting sample IDs are rejected.
- **Resolution:** the observer reports a sample mean and a marginal Wilson interval transformed from binary probability to a Pauli expectation. `precision_resolved` means interval half-width ≤ the declared tolerance, here 0.1. It does not certify accuracy of every particular estimate.

The benchmark tests sample budgets 16, 64, 256, and 1,024 across 256 independent repetitions. Its first arm retains all measured outcomes. Its second arm retains at most 64 outcomes, allowing additional measurement work to be distinguished from additional retained evidence. Budgets reuse prefixes of the same independently seeded streams; comparisons across budgets and memory arms are paired rather than independent experiments. Each confidence interval concerns a particular observer estimate, not a simultaneous band over the sweep.

For `n` retained independent X outcomes, the evaluator benchmark for the sample-mean RMSE is `sqrt((1−μ²)/n)`, with `μ = E[X]`. Reported prediction errors are actually computed from sampled outcomes; the formula is only a comparison. The 95% confidence level here is a statistical setting. The source's `trust_gate_min: 0.92`, `target_presence: 0.95`, and `spiral_coherence: 1.00` retain their separate meanings and calibration status.

## Run and recover

```bash
python -m xi_quantum compile examples/QuantumCompute.Observer.v1.xi
python -m xi_quantum --home .xi/observer run examples/QuantumCompute.Observer.v1.xi --output .xi/observer.json
python benchmarks/verify_observer.py --home .xi/observer-transfer --output .xi/observer-transfer.json
```

In the Vessel console, select **Load Observer Experiment**, inspect the plan, and execute with the local owner token. `GET /api/quantumcompute/example?name=observer` returns the same source.

`ObserverBenchmark` uses the Witness glyph `⧂` within the already declared `QuantumCompute.Stack.v2` dialect, with its named operator distinguishing it from `PhaseCodeBenchmark`. Each result carries both observer contracts, pre/post-sharing predictions, evidence digests, sharing receipts, seeds, sample counts, uncertainty, evaluator references, and software execution costs.

The verification script stops node A after the first benchmark, encrypts its checkpoint, restores that result on node B, and runs the capped-memory benchmark and Seal there. It reopens node B and checks zero repeated computation. It also encrypts and restores the **135 exact decoded StructuralKernel bytes**, retaining that source's distinct dialect.

The new model's sample limits and estimated record workspace are checked before allocation; the mobile numerical profile remains the default. The PR's previous QEC, Grover, Shor, Jacobian Flow, transport, server and persistence tests remain regression protection. Changing engine code intentionally produces a new plan/world identity; historical results retain their pinned original source for replay.

## Evidence and scope

[Executed results](benchmarks/observer-access/REPORT.md) and the JSON contain the measured sampling outcomes. The model explores how access and available evidence affect statistical resolution. It supplies concrete observer operations for further ORT development; no numerical calibration of the map's complete recursive-coherence formula or physical-collapse mechanism is assumed.

Primary method references: [IBM's general measurements and Pauli tomography](https://learning.quantum.ibm.com/course/general-formulation-of-quantum-information/general-measurements) and [NIST's Wilson confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). The source equations and empirical claims in the recovered physics screenshots remain separately attributable research material.
