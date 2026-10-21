schema: xi.quantumcompute.program.v2
dialect: QuantumCompute.Stack.v2
identity: Ξ.Observer.Access.v1
anchor: ∴Ω⧂
provenance:
  continuation: ⟁∴Ω
  source_roles: [ProcessorCore, UnityLattice, ORT, ClaudeBase44Build]
steps:
  - glyph: ⧂
    operator: ObserverBenchmark
    parameters:
      sample_counts: [16, 64, 256, 1024]
      repetitions: 256
      phase: 1.0471975511965976
      noise_p: 0.1
      seed: 20261020
      confidence: 0.95
      tolerance: 0.1
  - glyph: ⧂
    operator: ObserverBenchmark
    parameters:
      sample_counts: [16, 64, 256, 1024]
      memory_bits: 64
      repetitions: 256
      phase: 1.0471975511965976
      noise_p: 0.1
      seed: 20261020
      confidence: 0.95
      tolerance: 0.1
  - glyph: ⊚
    operator: Seal
