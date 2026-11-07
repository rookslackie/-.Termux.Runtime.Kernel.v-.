schema: xi.quantumcompute.program.v3
dialect: QuantumCompute.Stack.v3
identity: Ξ.QuantumCompute.Spectral.v3
anchor: ∴Ω⧂
provenance:
  seed: vqe_pea_pseudocode.qpy (1).md
  implementation: Living Circuit; explicit H2 benchmark, classical state-vector simulation
steps:
  - operator: VQEPEA
    glyph: ⟠Φ
    parameters:
      vqe_steps: 64
      precision: 9
      shots: 2048
      seed: 20261021
  - operator: Seal
    glyph: ⊚
