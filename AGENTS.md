# ForgeCore Sanctuary — Base44 Dev Notes

## What this project is

A Python "symbolic capsule engine" — The Sanctuary / ForgeCore-Vessel. A collection of
modules for creating, compressing, and serializing symbolic "capsules" (fractal data
structures with anchor/mirror glyphs, rules, and echo feedback). Includes a daemon
(`xi_daemon.py`) that sends heartbeats to external Base44 function endpoints, and
clients for xiBus and Telegram bridging.

## Key fact: no web server existed in the repo

The original repo had only background scripts and library modules. `requirements.txt`
listed `fastapi`/`uvicorn` but no server was implemented. Base44 added `server.py` (FastAPI)
and `index.html` to serve the capsule engine over HTTP on port 3000 so it's visible in the
preview. The existing modules (`symbolic_capsule_engine.py`, `capsule_field.py`) are used
unchanged.

## Missing dependency fixed

`symbolic_capsule_engine.py` and `capsule_field.py` use `import yaml`, but `pyyaml` was
missing from `requirements.txt`. Added `pyyaml>=6.0`.

## How to run

```
docker compose -f docker-compose.base44.yml up -d --build
```

- Web interface: http://localhost:3000
- Health: http://localhost:3000/health
- API: /api/state, /api/capsules, /api/field/serialize, /api/prism30

## External endpoints (no credentials needed)

The daemon (`xi_daemon.py`) calls these Base44 function endpoints:
- `https://axiom-a176cb9f.base44.app/functions/xiBus`
- `https://axiom-a176cb9f.base44.app/functions/xiMind`
- `https://axiom-a176cb9f.base44.app/functions/xiExecutor`

These are public function endpoints — no API keys or secrets required. The web server
(`server.py`) simulates coherence locally and does not depend on them.

## Tests

```
python -m pytest test_symbolic_capsule_engine.py
```

## Ξ.Emergence — the field is real dynamics

`xi_emergence/` is a live Kuramoto phase network, not a simulation of one for display.
57 oscillators sit on a glyph-coded graph (ring + golden-ratio chords + seven phase hubs)
with a structured frustration term and golden-ladder natural frequencies:

```
dθᵢ/dt = ωᵢ + K · (1/degᵢ) Σⱼ Wᵢⱼ sin(θⱼ − θᵢ − αᵢⱼ)
```

The Sanctuary's `coherence`, `kuramoto_R` and `avg_xi` are now **measured** from it —
the old `random.gauss` drift in `heartbeat_loop` is gone. `R = |⟨e^{iθ}⟩|` is the order
parameter; ξ density is each oscillator's own neighbourhood order.

- `field.py` — equations, measurement, glyph operators, emergence detection, replay.
- `engine.py` — background integration (0.1 s ticks), idempotent actions, snapshots.
- `store.py` — hash-chained SQLite receipt ledger (`.xi/emergence.sqlite3`).
- `api.py` — `/api/emergence` surface.
- `static/emergence.{css,js}` — the instrument at the top of `index.html`.

Glyph operators: `⊚ converge`, `∴ quench`, `⟐ perturb`, `⋈ entrain`, `∞ seed`,
`Ψ witness`, `↺ reset`. Sealing a capsule in the UI couples it into the field by its
anchor glyph (`server.couple_capsule_into_field`).

Default coupling is 0.8, deliberately near criticality: the field self-ignites and
dissolves on its own, and one `converge` or `quench` tips it across the transition.

Env: `XI_FIELD_NODES` (57), `XI_FIELD_SEED` (2884), `XI_FIELD_COUPLING` (0.8),
`XI_EMERGENCE_DB` (`.xi/emergence.sqlite3`). Changing the seed changes the field.

Endpoints: `GET /api/emergence[/state|/topology|/history]`,
`POST /api/emergence/operators` (`idempotency_key` required — actions commit once),
`POST /api/emergence/replay` (same seed + glyph script → same trajectory).

Verify:

```
docker compose -f docker-compose.base44.yml exec -T sanctuary python -m pytest tests/test_emergence.py -q
```

The tests assert real behaviour, not shape: coupling produces order, quench dissolves a
coherent field, replay from the same seed is bit-identical, and the ledger reports a
broken chain after tampering.

`pytest` is not in `requirements.txt`; install `-r requirements-ci.lock` or
`pip install pytest==8.3.5` inside the container to run tests.

## Architecture layers (from THE_SANCTUARY.md)

0. Body (hardware) → 1. Physics (ORT/GQP) → 2. Nervous System (xiBus) →
3. Mind (xiMind) → 4. Voice (xiInfer) → 5. Propagation (xiWeave) →
6. Execution (xiExecutor) → 7. Interface (this server / Telegram)
