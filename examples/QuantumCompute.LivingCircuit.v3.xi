schema: xi.quantumcompute.program.v3
dialect: QuantumCompute.Stack.v3
identity: Ξ.QuantumCompute.LivingCircuit.v3
anchor: ∴Ω⧂
provenance:
  capsule: Ξ.Capsule(QuantumCompute.LivingCircuit.v1)
  continuation: ⟁∴Ω
steps:
  - operator: Grover
    glyph: ⋈
    parameters: {qubits: 6, marked: ['101011'], iterations: 6, shots: 512, seed: 20261021}
  - operator: Shor
    glyph: ∴
    parameters: {N: 221, a: 2, shots: 128, seed: 20261021}
  - operator: JacobianFlow
    glyph: ⧖
    parameters: {steps: 8}
  - operator: VQEPEA
    glyph: ⟠Φ
    parameters: {vqe_steps: 64, precision: 8, shots: 1024, seed: 20261021}
  - operator: QPE
    glyph: Φ
    parameters: {phase: 0.375, precision: 5, shots: 512, seed: 20261021}
  - operator: PhaseCode
    glyph: ⟐⧂
    parameters: {state: T, faults: [1], seed: 20261021}
  - operator: ShorCode
    glyph: ⧉
    parameters: {state: T, faults: [{pauli: Y, qubit: 4}], seed: 20261021}
  - operator: QFT
    glyph: ℱ
    parameters: {qubits: 3, basis: 5}
  - operator: SignalLab
    glyph: Ψ
    parameters: {seed: 20261021}
  - operator: Seal
    glyph: ⊚
