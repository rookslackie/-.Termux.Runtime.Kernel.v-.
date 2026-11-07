schema: xi.quantumcompute.program.v3
dialect: QuantumCompute.Stack.v3
identity: Ξ.Nervous.DiscoverFunction.v1
anchor: ∴Ω⧂
provenance:
  source: XiSkill_DiscoverFunction.zip
  skill_version: 0.1.0
  role: Nervous capability-gap routing
steps:
  - glyph: ⚡⟳⏁
    operator: DiscoverFunction
    parameters:
      request: X
      capabilities: [Z]
      authorized_capabilities: []
      observations:
        - kind: observer_basis
          available: Z
      constraints:
        preserve_unresolved: true
      tests:
        - expected_state: UNRESOLVED
  - glyph: ⊚
    operator: Seal
