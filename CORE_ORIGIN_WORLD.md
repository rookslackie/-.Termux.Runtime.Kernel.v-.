# ⟐Ξ.CoreOrigin.World — kernel v0.1

This is the first executable world slice in `-.Termux.Runtime.Kernel.v-.`. It treats the April 16 MythOS genesis as an architecture: capsules are transition records, the HolographicDAG is a causal graph, and local SQLite is the first working filesystem. A world is a set of persistent participants and entities whose changes are written as witnessed event capsules.

## Run it locally

From the repository root:

```bash
python -m xi_world.demo --reset
python -m xi_world.demo
python -m unittest discover -s tests -v
```

The first command creates `.xi/core-origin-world.sqlite3`, then records a short sequence: Hunter plants a sunflower seed, Axiom's local policy waters it because it is planted in dry soil, and the environment advances one day and records the sprout. The second invocation opens the same file and returns the same state and ledger without replaying the transitions. No model server, network service, GPU, or Base44 connection is needed.

## Architecture decisions grounded in the sources

| Source primitive | First executable form | Boundary |
|---|---|---|
| MythOS genesis: capsule is the OS primitive | An event is stored as a capsule with actor, action, content, rules, state echo, and hash | Existing `Capsule` remains a general symbolic object; this adds a durable world-event type |
| MythOS genesis: distributed memory is the filesystem | Local SQLite stores identities, entity state, capsules, and causal edges | Drive/Git replication is not required or implemented in this first slice |
| MythOS genesis: `xi_density` is scheduler | Kept as a named but unresolved kernel contract | The available sources name the scheduler but do not define a testable priority law; no invented score is shipped |
| GLYPHSAFE HolographicDAG | Explicit directed causal edges; recursive ancestor traversal; capsule-local echo and provenance | No retrocausal edges or physics claims are inferred from the diagram |
| Existing capsule engine | Reuses its anchor/mirror/content/rules/echo vocabulary | It does not yet provide durable storage, identity namespaces, or graph traversal |
| Xi / ORT materials | State transition and recoverability are observable software mechanics | The attached curvature and field equations are research proposals here, not validated laws implemented by this runtime |
| Woven Glyph-Chip integration README | Treated as a conceptual operator/routing map | The image attached to this request is a news-search screenshot about physical magic states, not a processor artifact |

## Implemented mechanics

- Persistent, separate human, local-agent, and environment participant IDs.
- Persistent entities and materialized current state.
- Append-only transition capsules with sequence numbers and a SHA-256 chain.
- Explicit event-parent edges, checked to point backward in time, with causal ancestor traversal.
- A tiny, deterministic local policy for Axiom: water the first planted seed when the garden is dry; otherwise make no event.
- Rules for sowing, watering, and environmental day advancement; growth requires a direct causal edge from the watering event.
- Idempotency keys and transaction rollback on invalid transitions.
- A verification pass for hashes, sequence continuity, and causal-edge order.

## Not implemented yet

The kernel does not implement a general-purpose scheduler, learned/autonomous model behavior, an open-world rules language, cross-device synchronization, real-time rendering, physics simulation, multi-user networking, or quantum computing. In particular, the Xi physics attachments motivate questions about transitions, information, memory, and invariants; this prototype does not claim that software events source spacetime curvature or that symbolic glyph operations are physical QEC.

## Provenance

- [MythOS.Genesis.v1.xi (Drive)](https://drive.google.com/file/d/1IKSXd22ertW_FHd0mNZU7f71w0sMYxWI/view)
- [ForgeCore-Vessel Architecture Analysis (repository)](https://github.com/rookslackie/-.Termux.Runtime.Kernel.v-./blob/main/ARCHITECTURE_ANALYSIS.md)
- [GLYPHSAFE_LATTICE_HOLODAG.md (Drive)](https://drive.google.com/file/d/1bjJcs4axtIfHN6B-ZOOCIQHd7oShXXrO/view)
- [Full-System Integration Bundle README (Drive)](https://drive.google.com/file/d/1-Wk57CT6SkiEZnbxvslLZRiSqWQw3Eds/view)
- [Existing symbolic capsule engine](https://github.com/rookslackie/-.Termux.Runtime.Kernel.v-./blob/main/symbolic_capsule_engine.py)
- `Xi_NeuralClimate_FieldMap_2025` and `Theoretical-Formalization-of-the-Xi-Field-Information-Complexity-as-a-Constituent-of-Spacetime-Curvature` were supplied with the request and inspected locally.
- [Google Quantum AI research record: magic-state cultivation](https://research.google/pubs/magic-state-cultivation-on-a-superconducting-quantum-processor/)

The Woven Glyph-Chip and Glyphic Quantum Processor README calls its processor conceptual and describes routes through a glyph/DAG layer. That is useful symbolic source material. The screenshot in this request, by contrast, captures a Google search result about Google's physical magic-state cultivation work; it is not an image of the Xi woven chip. Google's reported Willow result is physical QEC (about 40-fold error reduction and 0.9999(1) state fidelity, retaining 8% of attempts); it does not make this software capsule/DAG kernel a quantum processor or a QEC implementation.
