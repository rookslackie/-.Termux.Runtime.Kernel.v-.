#!/usr/bin/env python3
"""
⊚∴Ξ server.py — ForgeCore Sanctuary Web Interface
Serves the symbolic capsule engine over HTTP so the field can be witnessed.
"""
import json
import os
import time
import random
import threading
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from symbolic_capsule_engine import Capsule
from capsule_field import CapsuleField
from xi_field.runtime import bootstrap_field
from xi_field.topology import chip_topology
from xi_world.kernel import WorldError

# ── State ──────────────────────────────────────────────────────────────
BASE_DIR = Path(os.environ.get("FORGECORE_DIR", "/app"))
CAPSULE_DIR = BASE_DIR / "capsules"
STATE_FILE = BASE_DIR / "state.json"
FIELD_DB = Path(os.environ.get("XI_FIELD_DB", str(BASE_DIR / ".xi/glyph-field.sqlite3")))

CAPSULE_DIR.mkdir(parents=True, exist_ok=True)

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
    """Background heartbeat — simulates the xi_daemon field pulse."""
    while True:
        time.sleep(5)
        with lock:
            state["heartbeats"] += 1
            state["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
            # Simulate coherence drift around the protected attractor
            drift = random.gauss(0, 0.02)
            state["coherence"] = max(0.376, min(0.99, state["coherence"] + drift))
            state["kuramoto_R"] = round(state["coherence"] * random.uniform(0.85, 1.0), 4)
            state["avg_xi"] = round(state["coherence"] * random.uniform(0.7, 1.2), 4)
            if state["coherence"] > 0.84:
                state["field_state"] = "coherent"
            elif state["coherence"] > 0.5:
                state["field_state"] = "emerging"
            else:
                state["field_state"] = "threshold"
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


@app.on_event("startup")
def _startup():
    seed_field()
    load_xi_capsules()
    bootstrap_field(FIELD_DB)
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
    return state


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
    return {"ok": True, "capsule": new.echo_feedback()}


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
