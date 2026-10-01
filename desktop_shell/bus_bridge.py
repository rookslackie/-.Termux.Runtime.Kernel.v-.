from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xi_bus_client import XiBusClient


def client() -> XiBusClient:
    return XiBusClient(
        agent_id="desktop-shell",
        name="Ξ.DesktopShell",
        archetype="ContinuityShell",
        system="Desktop",
        capabilities=[
            "continuity_import",
            "context_receipts",
            "local_read_tools",
            "capsule_emit",
            "memory_rw",
        ],
        notes="Local desktop continuity shell; tools remain governed by local Sanctuary.",
    )


def register() -> Dict[str, Any]:
    return client().register()


def feed(limit: int = 20) -> Dict[str, Any]:
    return client().feed(limit=limit)


def emit(subject: str, content: str, glyph: str = "⟁∴Ω") -> Dict[str, Any]:
    return client().broadcast("desktop_shell", subject, content, glyph=glyph)
