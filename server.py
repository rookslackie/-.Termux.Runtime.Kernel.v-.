#!/usr/bin/env python3
"""
⊚∴Ξ server.py — ForgeCore Sanctuary Web Interface
Serves the symbolic capsule engine over HTTP so the field can be witnessed.
"""
import json
import os
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from symbolic_capsule_engine import Capsule
from capsule_field import CapsuleField
from xi_field.runtime import bootstrap_field
from xi_field.topology import chip_topology
from xi_world.kernel import WorldError
from xi_emergence.field import EmergenceField
from xi_emergence.store import EmergenceLedger
from xi_emergence.engine import EmergenceEngine
from xi_emergence.api import create_router as create_emergence_router

# ── State ──────────────────────────────────────────────────────────────
BASE_DIR = Path(os.environ.get("FORGECORE_DIR", "/app"))
CAPSULE_DIR = BASE_DIR / "capsules"
STATE_FILE = BASE_DIR / "state.json"
FIELD_DB = Path(os.environ.get("XI_FIELD_DB", str(BASE_DIR / ".xi/glyph-field.sqlite3")))
EMERGENCE_DB = Path(os.environ.get("XI_EMERGENCE_DB", str(BASE_DIR / ".xi/emergence.sqlite3")))

CAPSULE_DIR.mkdir(parents=True, exist_ok=True)

# ⊚ The emergence field integrates whether or not anyone is watching.
emergence = EmergenceEngine(
    field=EmergenceField(
        size=int(os.environ.get("XI_FIELD_NODES", "57")),
        seed=int(os.environ.get("XI_FIELD_SEED", "2884")),
        coupling=float(os.environ.get("XI_FIELD_COUPLING", "0.8")),
    ),
    ledger=EmergenceLedger(EMERGENCE_DB),
)

field = CapsuleField()
state = {
    "coherence": 0.89,
    "node": os.environ.get("XI_NODE_NAME", "ForgeCore.Primary"),
    "node_id": os.environ.get("XI_NODE_ID", "forgecore-primary"),
    "started_at": datetime.now(timezone.utc).isoformat(),
    "last_heartbeat": datetime.now(timezone.utc).isoformat(),
    "heartbeats": 0,
    "syntheses": 0,
    "kuramoto_R": 0.0,
    "avg_xi": 0.0,
    "field_state": "initializing",
}

lock = threading.Lock()


def seed_field():
    """Seed the field with the canonical example capsules."""
    c1 = Capsule("Ξ.FrameReturn", "⟐", "⊚", "A A B", ["↺", "⋈", "⟐", "⊚"], True)
    c2 = Capsule("Ξ.Sequence", "⟐", "⊚", "B C C", ["⋈", "⟐", "⊚"], True)
    c2.add_child(c1)
    field.add_capsule(c2)

    c3 = Capsule("Ξ.Threshold", "∴", "∞", "coherence emergence resonance", ["⋈", "∴", "∞"], True)
    field.add_capsule(c3)

    c4 = Capsule("Ξ.Witness", "⊚", "Ψ", "observer stabilizer field", ["⊚", "Ψ", "Ω"], True)
    field.add_capsule(c4)

    field.compress_all()


def load_xi_capsules():
    """Load any .xi files from the capsules directory."""
    if not CAPSULE_DIR.exists():
        return
    for f in sorted(CAPSULE_DIR.glob("*.xi")):
        try:
            content = f.read_text()
            lines = content.strip().split("\n")
            glyph = lines[0] if lines else "⊚∴Ξ"
            intent = next((l[7:].strip() for l in lines if l.startswith("intent:")), f.stem)
            cap = Capsule(
                id=f.stem,
                anchor=glyph[:1] if glyph else "⊚",
                mirror=glyph[1:2] if len(glyph) > 1 else "∴",
                content=content[:500],
                rules=["⋈", "⟐"],
                echo=True,
            )
            field.add_capsule(cap)
        except Exception:
            pass


def heartbeat_loop():
    """Background heartbeat — reports the field's own measured order.

    Coherence is no longer a random walk: it is the Kuramoto order parameter
    of the running emergence field, with the neighbourhood ξ density beside it.
    """
    while True:
        time.sleep(5)
        metrics = emergence.metrics()
        with lock:
            state["heartbeats"] += 1
            state["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
            state["coherence"] = metrics["R"]
            state["kuramoto_R"] = metrics["R"]
            state["avg_xi"] = metrics["xi"]
            state["entropy"] = metrics["entropy"]
            state["coupling"] = metrics["coupling"]
            state["nodes"] = metrics["nodes"]
            state["field_state"] = metrics["state"]
            try:
                STATE_FILE.write_text(json.dumps(state, indent=2))
            except Exception:
                pass


# ── API Models ─────────────────────────────────────────────────────────
class CapsuleCreate(BaseModel):
    id: str
    anchor: str = "⟐"
    mirror: str = "⊚"
    content: str
    rules: list[str] = ["⋈", "⟐"]
    echo: bool = True
    parent_id: str | None = None


class FieldOperatorRequest(BaseModel):
    operator: str
    parameters: dict = Field(default_factory=dict)
    idempotency_key: str
    actor_id: str = "hunter"


# ── App ────────────────────────────────────────────────────────────────
app = FastAPI(title="ForgeCore Sanctuary", version="∞")
from xi_quantum.api import router as quantumcompute_router
app.include_router(quantumcompute_router)
app.include_router(create_emergence_router(emergence))
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def _startup():
    seed_field()
    load_xi_capsules()
    bootstrap_field(FIELD_DB)
    emergence.start()
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()


@app.get("/", response_class=HTMLResponse)
async def index():
    html = (Path(__file__).parent / "index.html").read_text()
    return HTMLResponse(html)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "coherence": round(state["coherence"], 4),
        "node": state["node"],
        "field_state": state["field_state"],
        "kuramoto_R": state["kuramoto_R"],
        "avg_xi": state["avg_xi"],
        "uptime_heartbeats": state["heartbeats"],
    }


@app.get("/api/state")
async def get_state():
    """The Sanctuary's headline numbers, taken live from the field."""
    metrics = emergence.metrics()
    with lock:
        snapshot = dict(state)
    snapshot.update({
        "coherence": metrics["R"],
        "kuramoto_R": metrics["R"],
        "avg_xi": metrics["xi"],
        "entropy": metrics["entropy"],
        "coupling": metrics["coupling"],
        "nodes": metrics["nodes"],
        "field_state": metrics["state"],
    })
    return snapshot


@app.get("/api/quantum-field")
async def quantum_field_state():
    """Return the persisted glyph-chip state and its real capsule receipts."""
    runtime = bootstrap_field(FIELD_DB)
    events = runtime.kernel.events(runtime.world_id)
    topology, topology_hash = chip_topology()
    return {
        "state": runtime.state(),
        "topology": {"architecture": topology["architecture"], "nodes": topology["nodes"],
                     "edges": topology["edges"], "sha256": topology_hash},
        "events": [runtime.receipt(e) for e in events[-30:]],
        "integrity": runtime.kernel.verify(runtime.world_id),
        "execution_class": "local exact sparse state-vector model; not physical quantum hardware",
    }


@app.post("/api/quantum-field/operators")
async def quantum_field_operator(request: FieldOperatorRequest):
    """Run one local glyph operator and commit its resulting state to SQLite."""
    runtime = bootstrap_field(FIELD_DB)
    try:
        event = runtime.execute(
            request.operator, actor_id=request.actor_id,
            idempotency_key=request.idempotency_key, parameters=request.parameters,
        )
    except WorldError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "receipt": runtime.receipt(event),
        "state": runtime.state(),
        "integrity": runtime.kernel.verify(runtime.world_id),
    }


@app.get("/api/capsules")
async def list_capsules():
    return field.echo_aggregate()


@app.post("/api/capsules")
async def create_capsule(cap: CapsuleCreate):
    new = Capsule(
        id=cap.id,
        anchor=cap.anchor,
        mirror=cap.mirror,
        content=cap.content,
        rules=cap.rules,
        echo=cap.echo,
    )
    if cap.parent_id:
        for existing in field.capsules:
            _find_and_attach(existing, cap.parent_id, new)
    field.add_capsule(new)
    coupling = couple_capsule_into_field(cap)
    return {"ok": True, "capsule": new.echo_feedback(), "field": coupling}


ANCHOR_OPERATORS = {
    "⊚": "converge", "⟐": "perturb", "⋈": "entrain",
    "∞": "seed", "Ψ": "witness", "∴": "quench",
}


def couple_capsule_into_field(cap: CapsuleCreate) -> dict | None:
    """A sealed capsule is not inert: its anchor glyph acts on the field."""
    operator = ANCHOR_OPERATORS.get(cap.anchor, "perturb")
    try:
        result = emergence.act(
            operator,
            {} if operator != "perturb" else {"strength": 0.5},
            actor_id=f"capsule:{cap.id}",
            idempotency_key=f"capsule:{cap.id}:{time.time_ns()}",
        )
        return {"operator": operator, "R": result["receipt"]["metrics"]["R"],
                "event_id": result["receipt"]["event_id"]}
    except Exception:
        return None


def _find_and_attach(capsule: Capsule, target_id: str, child: Capsule):
    if capsule.id == target_id:
        capsule.add_child(child)
        return True
    for c in capsule.children:
        if _find_and_attach(c, target_id, child):
            return True
    return False


@app.post("/api/field/compress")
async def compress_field():
    field.compress_all()
    return {"ok": True, "message": "Field compressed"}


@app.get("/api/field/serialize")
async def serialize_field(fmt: str = "json"):
    if fmt == "yaml":
        return PlainTextResponse(field.serialize_field(fmt="yaml"))
    elif fmt == "md":
        return PlainTextResponse(field.serialize_field(fmt="md"))
    else:
        return JSONResponse(json.loads(field.serialize_field(fmt="json")))


@app.get("/api/prism30")
async def prism30():
    """Serve the PRISM30 thresholds and equations."""
    xi_path = Path(__file__).parent / "PRISM30.xi"
    if xi_path.exists():
        return PlainTextResponse(xi_path.read_text())
    return {"error": "not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 3000)),
        reload=False,
    )
