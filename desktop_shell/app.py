from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from core import (
    HOME,
    build_context,
    ensure_home,
    list_sources,
    load_companion,
    load_config,
    save_config,
    tool_list_dir,
    tool_read_file,
)
from thread_import import import_pasted_text
from bus_bridge import emit as bus_emit, feed as bus_feed, register as bus_register


HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"

app = FastAPI(title="Ξ Desktop Shell", version="0.1")
ensure_home()


class PasteImport(BaseModel):
    title: str = "Imported conversation"
    text: str


class ToolEnable(BaseModel):
    enabled: bool
    roots: list[str] = []


class PathRequest(BaseModel):
    path: str


class BusEmit(BaseModel):
    subject: str
    content: str
    glyph: str = "⟁∴Ω"


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
def status() -> Dict[str, Any]:
    return {
        "home":str(HOME),
        "config":load_config(),
        "companion":load_companion(),
        "sources":list_sources(),
    }


@app.post("/api/import/paste")
def import_paste(payload: PasteImport) -> Dict[str, Any]:
    ensure_home()
    temp = HOME / "imports" / "ui_paste.txt"
    temp.write_text(payload.text, encoding="utf-8")
    return import_pasted_text(temp, payload.title)


@app.get("/api/context/{conversation_id:path}")
def context(conversation_id: str) -> Dict[str, Any]:
    return build_context(conversation_id)


@app.post("/api/tools/configure")
def configure_tools(payload: ToolEnable) -> Dict[str, Any]:
    config = load_config()
    config["tools_enabled"] = bool(payload.enabled)
    config["allowed_roots"] = payload.roots if payload.enabled else []
    save_config(config)
    return {"ok":True, "config":config}


@app.post("/api/tools/list")
def list_dir(payload: PathRequest) -> Dict[str, Any]:
    try:
        return tool_list_dir(payload.path)
    except (PermissionError, FileNotFoundError) as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/api/tools/read")
def read_file(payload: PathRequest) -> Dict[str, Any]:
    try:
        return tool_read_file(payload.path)
    except (PermissionError, FileNotFoundError, IsADirectoryError) as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/api/bus/register")
def register_bus() -> Dict[str, Any]:
    return bus_register()


@app.get("/api/bus/feed")
def read_bus_feed(limit: int = 20) -> Dict[str, Any]:
    return bus_feed(limit=max(1, min(limit, 100)))


@app.post("/api/bus/emit")
def emit_bus(payload: BusEmit) -> Dict[str, Any]:
    return bus_emit(payload.subject, payload.content, payload.glyph)
