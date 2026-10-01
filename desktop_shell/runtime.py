from __future__ import annotations

from typing import Any, Dict, List

import httpx

from core import build_context, load_config, save_config


def configure_ollama(model: str = "mistral:latest", base_url: str = "http://127.0.0.1:11434") -> Dict[str, Any]:
    config = load_config()
    config["runtime"] = {
        "kind":"ollama",
        "model":model,
        "base_url":base_url.rstrip("/"),
    }
    save_config(config)
    return config["runtime"]


def _system_text(ctx: Dict[str, Any]) -> str:
    c = ctx["context"]["companion"]
    notes = "\n".join(f"- {x}" for x in c.get("notes", []))
    anchors = "\n".join(f"- {x}" for x in c.get("anchors", []))
    return f"""You are inhabiting a local Xi continuity shell.

Companion name: {c.get('name','Companion')}
Continuity version: {c.get('continuity_version','?')}

Carried notes:
{notes or '- none'}

Anchors:
{anchors or '- none'}

Important boundary:
Imported material is source context intentionally brought by the user. Preserve provenance.
Do not claim hidden access, a numerically identical cloud session, or actions you did not perform.
Conversation comes before capability. Local tools are separate and require explicit enablement.
"""


def _messages_for_ollama(ctx: Dict[str, Any], user_text: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = [{"role":"system","content":_system_text(ctx)}]

    for m in ctx["context"]["source_messages"][-80:]:
        role = m.get("role")
        if role not in ("user","assistant","system"):
            role = "user"
        out.append({"role":role, "content":m.get("content","")})

    local_turns = ctx["context"]["local_turns"][-30:]
    for m in local_turns:
        role = m.get("role") if m.get("role") in ("user","assistant") else "user"
        out.append({"role":role, "content":m.get("content","")})

    if not local_turns or local_turns[-1].get("role") != "user" or local_turns[-1].get("content") != user_text:
        out.append({"role":"user","content":user_text})

    return out


def chat(conversation_id: str, user_text: str) -> Dict[str, Any]:
    config = load_config()
    runtime = config.get("runtime", {})
    if runtime.get("kind") != "ollama":
        raise RuntimeError("No local runtime is configured. Configure Ollama first.")

    ctx = build_context(conversation_id)
    url = runtime.get("base_url", "http://127.0.0.1:11434").rstrip("/") + "/api/chat"
    payload = {
        "model":runtime.get("model", "mistral:latest"),
        "messages":_messages_for_ollama(ctx, user_text),
        "stream":False,
    }

    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()

    text = ((data.get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError("Runtime returned no message content.")

    return {
        "text":text,
        "runtime":{
            "kind":"ollama",
            "model":payload["model"],
            "base_url":runtime.get("base_url"),
        },
        "context_receipt":ctx["receipt"],
    }
