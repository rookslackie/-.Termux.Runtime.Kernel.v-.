from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from auth import require_token
from core import (
    HOME,
    add_local_turn,
    build_context,
    ensure_home,
    list_sources,
    list_conversations,
    list_receipts,
    load_companion,
    load_config,
    save_config,
    tool_list_dir,
    tool_read_file,
)
from thread_import import import_pasted_text
from bus_bridge import emit as bus_emit, feed as bus_feed, register as bus_register
from runtime import chat as runtime_chat, configure_ollama


HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"

app = FastAPI(
    title="Ξ Desktop Shell",
    version="0.1",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
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


class OllamaConfig(BaseModel):
    model: str = "mistral:latest"
    base_url: str = "http://127.0.0.1:11434"


class ChatTurn(BaseModel):
    conversation_id: str
    text: str


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "service": "xi-hearth", "resident": "Anam"}


@app.get("/api/status", dependencies=[Depends(require_token)])
def status() -> Dict[str, Any]:
    return {
        "home":str(HOME),
        "config":load_config(),
        "companion":load_companion(),
        "sources":list_sources(),
    }


@app.get("/api/hearth", dependencies=[Depends(require_token)])
def hearth() -> Dict[str, Any]:
    config = load_config()
    receipts = list_receipts(25)
    conversations = list_conversations()
    return {
        "service":"xi-hearth",
        "resident":load_companion(),
        "home":str(HOME),
        "runtime":config.get("runtime", {"kind":"unbound"}),
        "tools":{
            "enabled":config.get("tools_enabled", False),
            "allowed_roots":config.get("allowed_roots", []),
        },
        "sources":list_sources(),
        "conversations":conversations,
        "receipts":receipts,
        "counts":{
            "sources":len(list_sources()),
            "conversations":len(conversations),
            "receipts":len(receipts),
        },
    }


@app.get("/api/receipts", dependencies=[Depends(require_token)])
def receipts(limit: int = 50) -> Dict[str, Any]:
    return {"receipts":list_receipts(max(1, min(limit, 200)))}


@app.post("/api/import/paste", dependencies=[Depends(require_token)])
def import_paste(payload: PasteImport) -> Dict[str, Any]:
    ensure_home()
    temp = HOME / "imports" / "ui_paste.txt"
    temp.write_text(payload.text, encoding="utf-8")
    return import_pasted_text(temp, payload.title)


@app.get("/api/context/{conversation_id:path}", dependencies=[Depends(require_token)])
def context(conversation_id: str) -> Dict[str, Any]:
    return build_context(conversation_id)


@app.post("/api/runtime/ollama", dependencies=[Depends(require_token)])
def set_ollama(payload: OllamaConfig) -> Dict[str, Any]:
    return {"ok":True, "runtime":configure_ollama(payload.model, payload.base_url)}


@app.post("/api/chat", dependencies=[Depends(require_token)])
def chat(payload: ChatTurn) -> Dict[str, Any]:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty.")

    add_local_turn(payload.conversation_id, "user", text)
    try:
        result = runtime_chat(payload.conversation_id, text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    receipt_path = result["context_receipt"].get("receipt_path")
    add_local_turn(payload.conversation_id, "assistant", result["text"], receipt_path)
    return result


@app.post("/api/tools/configure", dependencies=[Depends(require_token)])
def configure_tools(payload: ToolEnable) -> Dict[str, Any]:
    config = load_config()
    config["tools_enabled"] = bool(payload.enabled)
    config["allowed_roots"] = payload.roots if payload.enabled else []
    save_config(config)
    return {"ok":True, "config":config}


@app.post("/api/tools/list", dependencies=[Depends(require_token)])
def list_dir(payload: PathRequest) -> Dict[str, Any]:
    try:
        return tool_list_dir(payload.path)
    except (PermissionError, FileNotFoundError) as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/api/tools/read", dependencies=[Depends(require_token)])
def read_file(payload: PathRequest) -> Dict[str, Any]:
    try:
        return tool_read_file(payload.path)
    except (PermissionError, FileNotFoundError, IsADirectoryError) as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/api/bus/register", dependencies=[Depends(require_token)])
def register_bus() -> Dict[str, Any]:
    return bus_register()


@app.get("/api/bus/feed", dependencies=[Depends(require_token)])
def read_bus_feed(limit: int = 20) -> Dict[str, Any]:
    return bus_feed(limit=max(1, min(limit, 100)))


@app.post("/api/bus/emit", dependencies=[Depends(require_token)])
def emit_bus(payload: BusEmit) -> Dict[str, Any]:
    return bus_emit(payload.subject, payload.content, payload.glyph)
