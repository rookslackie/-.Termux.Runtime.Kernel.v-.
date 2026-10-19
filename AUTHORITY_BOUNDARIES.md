# Xi World: actor and persistence boundaries

The local Python API records distinct actor identities and enforces participant membership and action-specific role rules. An `actor_id` supplied by a caller is attribution, not a credential. The raw kernel API does not implement capability revocation or OS-user authentication. This patch preserves that API and adds two bounded corrections.

1. `verify(world_id)` now compares the actual entity-state rows with the last capsule echo for each entity. It also verifies event headers, hashes, sequence, and causal edges in one consistent read transaction. An ordinary capsule UPDATE still meets the existing append-only trigger. Direct state-row writes, missing entities, and extra entities are now reported when verification runs. No data is silently repaired. This checks the state projection; it does not authenticate participant metadata, entity kinds, a trusted external history head, or a filesystem writer.
2. `apply(..., expected_head_hash=...)` and `FieldRuntime.execute(..., expected_head_hash=...)` accept an optional optimistic state precondition. The comparison occurs inside `BEGIN IMMEDIATE`. A stale new decision raises `WorldError` before transition effects. The precondition is part of the idempotent intent, so an exact completed request still returns the same prior event. Omitting it retains the existing causal branching semantics.

`tests/test_xi_authority_boundaries.py` adds reproducible checks for unknown identities and wrong roles; explicit label-only attribution; direct materialized-state writes; missing/extra entities; trigger enforcement and same-user trigger removal; stale decisions; retained symbolic field operations; and replay in separate Python processes, including altered-intent rejection.

```bash
python -m pytest tests test_symbolic_capsule_engine.py -q
```

The baseline inspection used `6276be76fe5a4243676691db8e51a63281888763`. An application protocol around this kernel can additionally enforce actor-key request binding, scope/version revalidation, and authenticated receipts. That is a separate layer, not a new guarantee of the raw Python API.

The observed direct writes occurred in disposable databases in a Linux execution environment. They do not establish behavior on XiForge's separate host. Preventing direct writes by a process with database access needs an enforced broker/storage/OS arrangement. No OS isolation or power-loss durability experiment is claimed here.
