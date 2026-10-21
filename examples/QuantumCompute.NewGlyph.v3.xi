schema: xi.quantumcompute.program.v3
dialect: QuantumCompute.Stack.v3
identity: Ξ.QuantumCompute.NewGlyph.v3
anchor: ∴Ω⧂
definitions:
  - name: ReturnLight
    version: 1
    glyph: ⟠⋈⧂
    meaning: Search a declared target, then witness a correctable phase disturbance.
    parameters:
      target:
        type: string
        default: '101011'
      fault:
        type: integer
        minimum: 0
        maximum: 2
        default: 1
    steps:
      - operator: Grover
        glyph: ⋈
        parameters:
          qubits: 6
          marked: ['$target']
          iterations: 6
          shots: 512
          seed: 20261021
      - operator: PhaseCode
        glyph: ⟐⧂
        parameters:
          state: T
          faults: ['$fault']
          seed: 20261021
steps:
  - operator: ReturnLight
    glyph: ⟠⋈⧂
    parameters:
      target: '101011'
      fault: 2
  - operator: Seal
    glyph: ⊚
