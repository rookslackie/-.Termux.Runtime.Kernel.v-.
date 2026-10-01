from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import add_messages, store_source


def import_pasted_text(path: Path, title: Optional[str] = None) -> Dict[str, Any]:
    raw = path.read_bytes()
    title = title or path.stem
    source = store_source("pasted_conversation", title, raw, {"original_path": str(path)})
    text = raw.decode("utf-8", errors="replace")
    conversation_id = f"paste:{source.id}"
    count = add_messages(source.id, conversation_id, [{
        "role":"source",
        "author":"imported_thread",
        "content":text,
        "created_at":None,
    }])
    return {"source_id":source.id, "conversation_id":conversation_id, "messages":count, "title":title}


def _message_text(message: Dict[str, Any]) -> str:
    content = message.get("content") or {}
    parts = content.get("parts") or []
    out: List[str] = []
    for part in parts:
        if isinstance(part, str):
            out.append(part)
        elif isinstance(part, dict):
            if "text" in part:
                out.append(str(part["text"]))
            else:
                out.append(json.dumps(part, ensure_ascii=False))
    return "\n".join(x for x in out if x).strip()


def _conversation_messages(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
    mapping = conv.get("mapping") or {}
    nodes = []
    for node_id, node in mapping.items():
        msg = node.get("message")
        if not msg:
            continue
        text = _message_text(msg)
        if not text:
            continue
        author = msg.get("author") or {}
        role = author.get("role") or "unknown"
        name = author.get("name")
        create_time = msg.get("create_time")
        nodes.append({
            "node_id":node_id,
            "role":role,
            "author":name or role,
            "content":text,
            "created_at":create_time,
        })
    nodes.sort(key=lambda x: (x["created_at"] is None, x["created_at"] or 0))
    return nodes


def list_chatgpt(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    conversations = data if isinstance(data, list) else data.get("conversations", [])
    return [{
        "id": c.get("id") or c.get("conversation_id"),
        "title": c.get("title") or "Untitled",
        "create_time": c.get("create_time"),
        "update_time": c.get("update_time"),
        "message_count": len(_conversation_messages(c)),
    } for c in conversations]


def import_chatgpt(path: Path, conversation_id: str) -> Dict[str, Any]:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    conversations = data if isinstance(data, list) else data.get("conversations", [])
    conv = next((c for c in conversations if (c.get("id") or c.get("conversation_id")) == conversation_id), None)
    if conv is None:
        raise KeyError(f"Conversation not found: {conversation_id}")

    source = store_source(
        "chatgpt_export",
        conv.get("title") or "ChatGPT conversation",
        raw,
        {
            "original_path":str(path),
            "conversation_id":conversation_id,
            "conversation_title":conv.get("title"),
        },
    )
    messages = _conversation_messages(conv)
    local_conversation_id = f"chatgpt:{conversation_id}"
    count = add_messages(source.id, local_conversation_id, messages)
    return {
        "source_id":source.id,
        "conversation_id":local_conversation_id,
        "messages":count,
        "title":conv.get("title") or "Untitled",
    }
