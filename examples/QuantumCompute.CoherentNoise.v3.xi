schema: xi.quantumcompute.program.v3
identity: Ξ.QuantumCompute.CoherentNoise.v1
dialect: QuantumCompute.Stack.v3
anchor: ∴Ω⧂
provenance:
  intention: Preserve coherent logical interference through explicit syndrome recovery.
  model: Three-qubit phase-flip code; ideal gates and measurement; local RZ noise.
steps:
  - operator: PhaseCodeChannel
    glyph: ⟐⧂ρ
    parameters:
      state: zero
      angles: [0.2, 0.2, 0.2]
      cycles: 8
  - operator: PhaseCodeChannel
    glyph: ⟐⧂ρ
    parameters:
      state: zero
      angles: [0.2, 0.2, 0.2]
      cycles: 8
      twirled: true
  - operator: PhaseCode
    glyph: ⟐⧂
    parameters:
      state: T
      faults: []
      angles: [0.2, 0.2, 0.2]
      seed: 20261023
  - operator: Seal
    glyph: ⊚
