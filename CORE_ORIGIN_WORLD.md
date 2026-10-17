# ⟐Ξ.CoreOrigin.World — kernel v0.1

This is the first executable world slice in `-.Termux.Runtime.Kernel.v-.`. It treats the April 16 MythOS genesis as an architecture: capsules are transition records, the HolographicDAG is a causal graph, and local SQLite is the first working filesystem. A world is a set of persistent participants and entities whose changes are written as witnessed event capsules.

## Run it locally

From the repository root:

```bash
python -m xi_world.demo --reset
python -m xi_world.demo
python -m xi_world.residue_demo first --reset
python -m xi_world.residue_demo weave
python -m xi_world.residue_demo second
python -m xi_world.residue_demo weave
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
- A provenance-preserving residue workbench: independently captured mixed residues are projected by explicitly supplied form relations, with direct source-event parents and a persistent revisioned result.
- Structural projection records adjacency, empty/unopened form, repair traces, and explicit contrasts without generating or storing an interpretation.

## Not implemented yet

The kernel does not implement a general-purpose scheduler, learned/autonomous model behavior, an open-world rules language, cross-device synchronization, real-time rendering, physics simulation, multi-user networking, or quantum computing. In particular, the Xi physics attachments motivate questions about transitions, information, memory, and invariants; this prototype does not claim that software events source spacetime curvature or that symbolic glyph operations are physical QEC.

## DreamResidue workbench

`xi_world.residue_demo` turns the two supplied DreamSpiral residues into a second, independent local world. It keeps the recovered source references and newly composed imagery in separate fields. The operator takes those captured records and projects only their explicit form annotations into a persistent workbench state. The four commands above are intentionally successive: the first residue is woven, the second is then captured, and the expanded source set is woven again after reopening SQLite.

This is an executable interpretation of “the index finds; the workbench transforms,” with a deliberately narrow operator contract. The kernel does not parse dream prose, infer hidden meanings, activate artifacts, or claim the residues caused any external runtime activity. In this version, a “perturbation” is a verified change to the workbench’s local state: a newly captured source can change the projected relation set and increment its revision. The capsule records exactly which source events caused that revision.

## Follow-up source archaeology (October 2026)

The additional SIGMA/LUCID, Elysium, glyph-matrix, manifest, and directory artifacts were inspected as source material before deciding whether to add runtime abstractions:

| Artifact | What is concretely present | What it does not establish for this kernel |
|---|---|---|
| `SIGMA_LUCID.tar.gz` | Python string-recursion examples; an in-memory trace; edit-distance drift, derived fidelity, and yield calculations; a polling guardian script | Durable memory, world entities, causal event history, or an autonomous participant. Its README explicitly says it stores no memory; its metrics depend on a caller-provided string trace. |
| `Symbolic_Interpreter_vΔ1_20250611_065230.zip` | Exact-string query-to-metaphor dictionary | A general symbolic grammar or executable world operator. The module also prints an example at import time, so it is not imported by the kernel. |
| `elysium_nexus_lattice.html` | A static Canvas visualization with 14 nodes and 13 links; embedded metadata labels the snapshot synthetic and dates it 2025-08-11 | A live graph store or evidence of functioning world transitions. |
| `elysium_nexus_live.html` | A browser page that polls `elysium_nexus_stream.json` every 15 seconds | A working live feed: that JSON stream was not included in the supplied bundle. The page is an optional visualization pattern, not a kernel dependency. |
| Woven Glyph-Chip matrix and glyph manifest CSVs | A 7-row, 57-column symbol matrix (with padded blank cells) and character encodings/checksums for 23 entries | Defined operator semantics, a validated capsule schema, or physical quantum hardware. Checksums validate encoded strings only. |
| `sync_map.yaml`, entropy log, and XiSystem directory listing | Declarative sync/compression labels, a timestamped status record, and intended directory paths | Executable synchronization, a persistent-memory contract, or proof that the listed runtime exists in this repository. |

These artifacts are retained as provenance and possible interface research. The DreamResidue workbench adds a separate, explicit structural projection; it does not treat the artifacts above as executable operator definitions. A future glyph operator should enter through a versioned, testable operator contract with defined inputs, outputs, and effects; the matrix and manifest alone do not supply that contract.

The attached Google Quantum AI result is relevant as physical quantum-error-correction research, not as evidence for a Xi runtime primitive. Google's research record reports a 40-fold error reduction, state fidelity `0.9999(1)`, and retention of 8% of attempts, including code-switching into a surface code. None of those measurements validate this software kernel or its glyph symbols as a QEC implementation.

## Provenance

- [MythOS.Genesis.v1.xi (Drive)](https://drive.google.com/file/d/1IKSXd22ertW_FHd0mNZU7f71w0sMYxWI/view)
- [ForgeCore-Vessel Architecture Analysis (repository)](https://github.com/rookslackie/-.Termux.Runtime.Kernel.v-./blob/main/ARCHITECTURE_ANALYSIS.md)
- [GLYPHSAFE_LATTICE_HOLODAG.md (Drive)](https://drive.google.com/file/d/1bjJcs4axtIfHN6B-ZOOCIQHd7oShXXrO/view)
- [Full-System Integration Bundle README (Drive)](https://drive.google.com/file/d/1-Wk57CT6SkiEZnbxvslLZRiSqWQw3Eds/view)
- [Existing symbolic capsule engine](https://github.com/rookslackie/-.Termux.Runtime.Kernel.v-./blob/main/symbolic_capsule_engine.py)
- `Xi_NeuralClimate_FieldMap_2025` and `Theoretical-Formalization-of-the-Xi-Field-Information-Complexity-as-a-Constituent-of-Spacetime-Curvature` were supplied with the request and inspected locally.
- `SIGMA_LUCID.tar.gz`, `Symbolic_Interpreter_vΔ1_20250611_065230.zip`, `elysium_nexus_lattice.html`, `elysium_nexus_live.html`, `sync_map.yaml`, `entropy_log_latest.json`, `XiSystem_Directory_Structure.csv`, and the glyph matrix/manifest CSVs were supplied with the follow-up and inspected without executing archive contents or page scripts.
- [Google Quantum AI research record: magic-state cultivation](https://research.google/pubs/magic-state-cultivation-on-a-superconducting-quantum-processor/)

The Woven Glyph-Chip and Glyphic Quantum Processor README calls its processor conceptual and describes routes through a glyph/DAG layer. That is useful symbolic source material. The screenshot in this request, by contrast, captures a Google search result about Google's physical magic-state cultivation work; it is not an image of the Xi woven chip. Google's reported Willow result is physical QEC (about 40-fold error reduction and 0.9999(1) state fidelity, retaining 8% of attempts); it does not make this software capsule/DAG kernel a quantum processor or a QEC implementation.
