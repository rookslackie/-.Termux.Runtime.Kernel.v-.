schema: xi.quantumcompute.program.v2
identity: Ξ.QuantumCompute.FullCycle.v2
dialect: QuantumCompute.Stack.v2
anchor: ∴Ω⧂
provenance:
  lineage: Grover.Shôr.JacobianFlow.v1
  continuation: ⟁∴Ω
steps:
  - glyph: ⋈
    operator: Grover
    phase: 0.0
    parameters:
      qubits: 4
      marked: ['1011']
      iterations: 3
      shots: 256
      seed: 20261019
  - glyph: ∴
    operator: Shor
    phase: 0.2
    parameters:
      N: 221
      a: 2
      shots: 128
      seed: 20261019
  - glyph: ⧖
    operator: JacobianFlow
    phase: 0.4
    parameters:
      phase: 1.5707963267948966
      steps: 8
      step_size: 1.0
  - glyph: ⧂
    operator: PhaseCodeBenchmark
    phase: 0.0
    parameters:
      probabilities: [0.0, 0.1, 0.5, 0.9, 1.0]
      shots: 256
      seed: 20261019
  - glyph: ⊚
    operator: Seal
