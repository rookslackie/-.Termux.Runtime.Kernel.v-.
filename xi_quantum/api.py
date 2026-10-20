"""Owner-token API for the existing local Vessel server."""
from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from . import __version__
from .common import Profile, PROFILES
from .glyphsafe import SUITE
from .runtime import Runtime, ExecutionGrant
from .tessera import compile_program, DIALECT


router = APIRouter(prefix="/api/quantumcompute", tags=["QuantumCompute"])


class ProgramRequest(BaseModel):
    source: str
    stop_after: int | None = None


def _owner(token):
    expected = os.environ.get("XI_QUANTUM_API_TOKEN", "")
    if not expected or not token or not hmac.compare_digest(expected, token):
        raise HTTPException(403, "A locally configured QuantumCompute owner token is required")


@router.get("")
def capabilities():
    return {"version": __version__, "dialect": DIALECT, "operators": ["Grover", "Shor", "JacobianFlow", "PhaseCodeBenchmark", "ObserverBenchmark"],
            "glyphsafe_suite": SUITE, "profiles": {name: profile.__dict__ for name, profile in PROFILES.items()},
            "return_operator": "⟁∴Ω"}


@router.get("/example")
def example(name: str = "fullcycle"):
    files = {"fullcycle": "Ξ.QuantumCompute.yaml", "observer": "examples/QuantumCompute.Observer.v1.xi"}
    if name not in files:
        raise HTTPException(400, "Unknown QuantumCompute example")
    return {"source": (Path(__file__).resolve().parents[1] / files[name]).read_text(encoding="utf-8")}


@router.post("/compile")
def compile_request(request: ProgramRequest, x_xi_quantum_token: str | None = Header(default=None)):
    _owner(x_xi_quantum_token)
    try:
        return compile_program(request.source.encode("utf-8")).as_dict()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/run")
def run_request(request: ProgramRequest, x_xi_quantum_token: str | None = Header(default=None)):
    _owner(x_xi_quantum_token)
    try:
        source = request.source.encode("utf-8")
        plan = compile_program(source)
        base = PROFILES[os.environ.get("XI_QUANTUM_PROFILE", "mobile")]
        profile = Profile(base.name, int(os.environ.get("XI_QUANTUM_MEMORY_MIB", base.memory_mib)), base.max_iterations)
        home = os.environ.get("XI_QUANTUM_HOME", ".xi/quantumcompute")
        grant = ExecutionGrant(plan.program_sha256, frozenset(s["operator"] for s in plan.steps))
        return Runtime(home, profile=profile).run(source, grant=grant, stop_after=request.stop_after)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc
