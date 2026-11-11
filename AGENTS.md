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

### Development container notes

- `Dockerfile.base44` installs only `requirements.txt`; the cloned source is
  bind-mounted at `/app`, and uvicorn runs with `--reload --reload-dir /app`, so
  Python edits are picked up without a rebuild. Rebuild (`up -d --build`) only
  after changing `requirements.txt` or the Dockerfile.
- The app writes `state.json` (tracked) every heartbeat and creates the ignored
  `.xi/glyph-field.sqlite3` ledger on first start. Deleting the ledger re-seeds
  it with a single genesis event.
- `/api/quantumcompute/compile` and `/run` require the owner token configured in
  `XI_QUANTUM_API_TOKEN`; without it they answer 403 and the QuantumCompute
  panel cannot execute. Set it as an environment value for the `sanctuary`
  service (or a platform secret), then type the same token into the page's
  "Local owner token" field.

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

## Architecture layers (from THE_SANCTUARY.md)

0. Body (hardware) → 1. Physics (ORT/GQP) → 2. Nervous System (xiBus) →
3. Mind (xiMind) → 4. Voice (xiInfer) → 5. Propagation (xiWeave) →
6. Execution (xiExecutor) → 7. Interface (this server / Telegram)
