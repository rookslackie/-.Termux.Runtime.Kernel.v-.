from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import httpx

from core import HOME, RECEIPT_DIR, build_context, now_iso, sha256_json
from runtime import _messages_for_ollama, list_ollama_models


def compare_apertures(
    conversation_id: str,
    prompt: str,
    *,
    models: List[str] | None = None,
    base_url: str = "http://127.0.0.1:11434",
) -> Dict[str, Any]:
    """
    Run the same Hearth context + prompt through multiple local Ollama models.

    This is an observation pass, not a conversation turn:
    - it does not append user/assistant turns;
    - it does not change the active runtime;
    - it preserves one context hash shared by every aperture;
    - each model result is attributed and receipted.
    """
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("Experiment prompt is empty.")

    available = list_ollama_models(base_url)
    available_names = [m["name"] for m in available]

    if models:
        selected = [m for m in models if m in available_names]
    else:
        selected = available_names

    if not selected:
        raise ValueError("No requested local models are available.")

    ctx = build_context(conversation_id)
    context_hash = ctx["receipt"]["context_sha256"]
    messages = _messages_for_ollama(ctx, prompt)

    results: List[Dict[str, Any]] = []
    endpoint = base_url.rstrip("/") + "/api/chat"

    # Sequential on purpose: one local GPU/CPU aperture at a time.
    with httpx.Client(timeout=300.0) as client:
        for model in selected:
            started = time.perf_counter()
            item: Dict[str, Any] = {
                "model": model,
                "started_at": now_iso(),
                "context_sha256": context_hash,
            }
            try:
                response = client.post(
                    endpoint,
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        # Aperture Garden is intentionally one-model-at-a-time.
                        # Unload each model after its response so a comparison
                        # cannot accumulate several resident models and exhaust
                        # XIFORGE RAM/VRAM.
                        "keep_alive": 0,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                text = ((payload.get("message") or {}).get("content") or "").strip()
                item.update({
                    "ok": True,
                    "text": text,
                    "eval_count": payload.get("eval_count"),
                    "prompt_eval_count": payload.get("prompt_eval_count"),
                    "total_duration": payload.get("total_duration"),
                    "load_duration": payload.get("load_duration"),
                })
            except Exception as exc:
                item.update({"ok": False, "error": str(exc)})
            item["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            results.append(item)

    receipt = {
        "kind": "aperture_compare",
        "created_at": now_iso(),
        "conversation_id": conversation_id,
        "prompt": prompt,
        "context_receipt": ctx["receipt"],
        "models": selected,
        "results": results,
        "mutation": "none",
        "note": (
            "Observation only. No conversation turns appended and active runtime unchanged."
        ),
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = RECEIPT_DIR / f"aperture_{receipt['receipt_sha256'][:20]}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    receipt["receipt_path"] = str(path)
    return receipt


JOB_DIR = HOME / "aperture_jobs"


def _job_path(job_id: str) -> Path:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    return JOB_DIR / f"{job_id}.json"


def _write_job(job_id: str, body: Dict[str, Any]) -> None:
    path = _job_path(job_id)
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")


def read_aperture_job(job_id: str) -> Dict[str, Any]:
    path = _job_path(job_id)
    if not path.exists():
        raise KeyError(job_id)
    return json.loads(path.read_text(encoding="utf-8"))


def create_aperture_job(
    conversation_id: str,
    prompt: str,
    *,
    models: List[str] | None = None,
    base_url: str = "http://127.0.0.1:11434",
) -> Dict[str, Any]:
    job_id = "ap_" + uuid.uuid4().hex[:20]
    body = {
        "job_id": job_id,
        "status": "queued",
        "created_at": now_iso(),
        "conversation_id": conversation_id,
        "prompt": prompt,
        "models": models or [],
        "base_url": base_url,
    }
    _write_job(job_id, body)
    return body


def run_aperture_job(job_id: str) -> None:
    job = read_aperture_job(job_id)
    job["status"] = "running"
    job["started_at"] = now_iso()
    _write_job(job_id, job)

    try:
        receipt = compare_apertures(
            job["conversation_id"],
            job["prompt"],
            models=job.get("models") or None,
            base_url=job.get("base_url") or "http://127.0.0.1:11434",
        )
        job.update({
            "status": "completed",
            "finished_at": now_iso(),
            "receipt": receipt,
        })
    except Exception as exc:
        job.update({
            "status": "failed",
            "finished_at": now_iso(),
            "error": str(exc),
        })
    _write_job(job_id, job)
