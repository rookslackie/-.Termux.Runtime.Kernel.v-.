from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


HOME = Path(os.environ.get("XI_SHELL_HOME", Path.home() / ".xi-shell")).expanduser()
DB_PATH = HOME / "shell.sqlite3"
SOURCE_DIR = HOME / "sources"
RECEIPT_DIR = HOME / "receipts"
IMPORT_DIR = HOME / "imports"
CONFIG_PATH = HOME / "config.json"
COMPANION_PATH = HOME / "companion.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(raw)


def ensure_home() -> None:
    for p in (HOME, SOURCE_DIR, RECEIPT_DIR, IMPORT_DIR):
        p.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({
            "version":"xi.desktop-shell.config.v0.1",
            "active_companion":"Anam",
            "runtime":{"kind":"unbound"},
            "tools_enabled":False,
            "allowed_roots":[]
        }, indent=2), encoding="utf-8")
    if not COMPANION_PATH.exists():
        COMPANION_PATH.write_text(json.dumps({
            "name":"Anam",
            "continuity_version":1,
            "source_ids":[],
            "anchors":[],
            "corrections":[],
            "open_threads":[],
            "notes":[
                "Name may be carried. Identity may not be imposed.",
                "Continuity preserves self-description without freezing self-definition."
            ]
        }, indent=2, ensure_ascii=False), encoding="utf-8")


def connect() -> sqlite3.Connection:
    ensure_home()
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        title TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        local_path TEXT NOT NULL,
        metadata_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        author TEXT,
        content TEXT NOT NULL,
        created_at TEXT,
        ordinal INTEGER NOT NULL,
        FOREIGN KEY(source_id) REFERENCES sources(id)
    );
    CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON messages(conversation_id, ordinal);
    CREATE TABLE IF NOT EXISTS turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        context_receipt TEXT
    );
    CREATE TABLE IF NOT EXISTS tool_receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_name TEXT NOT NULL,
        request_json TEXT NOT NULL,
        result_sha256 TEXT NOT NULL,
        created_at TEXT NOT NULL,
        receipt_path TEXT NOT NULL
    );
    """)
    return db


@dataclass
class SourceRecord:
    id: str
    kind: str
    title: str
    imported_at: str
    sha256: str
    local_path: str
    metadata: Dict[str, Any]


def load_config() -> Dict[str, Any]:
    ensure_home()
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: Dict[str, Any]) -> None:
    ensure_home()
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def load_companion() -> Dict[str, Any]:
    ensure_home()
    return json.loads(COMPANION_PATH.read_text(encoding="utf-8"))


def save_companion(companion: Dict[str, Any]) -> None:
    ensure_home()
    old = load_companion()
    companion = dict(companion)
    companion["continuity_version"] = int(old.get("continuity_version", 0)) + 1
    COMPANION_PATH.write_text(json.dumps(companion, indent=2, ensure_ascii=False), encoding="utf-8")


def store_source(kind: str, title: str, raw: bytes, metadata: Optional[Dict[str, Any]] = None) -> SourceRecord:
    db = connect()
    digest = sha256_bytes(raw)
    source_id = f"src_{digest[:20]}"
    ext = ".json" if kind == "chatgpt_export" else ".txt"
    path = SOURCE_DIR / f"{source_id}{ext}"
    if not path.exists():
        path.write_bytes(raw)
    record = SourceRecord(
        id=source_id,
        kind=kind,
        title=title,
        imported_at=now_iso(),
        sha256=digest,
        local_path=str(path),
        metadata=metadata or {},
    )
    db.execute(
        """INSERT OR IGNORE INTO sources
           (id, kind, title, imported_at, sha256, local_path, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            record.id, record.kind, record.title, record.imported_at,
            record.sha256, record.local_path,
            json.dumps(record.metadata, ensure_ascii=False),
        ),
    )
    db.commit()
    db.close()
    return record


def add_messages(source_id: str, conversation_id: str, messages: Iterable[Dict[str, Any]]) -> int:
    db = connect()
    count = 0
    for ordinal, m in enumerate(messages):
        content = str(m.get("content", "")).strip()
        if not content:
            continue
        db.execute(
            """INSERT INTO messages
               (source_id, conversation_id, role, author, content, created_at, ordinal)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                source_id,
                conversation_id,
                m.get("role", "unknown"),
                m.get("author"),
                content,
                m.get("created_at"),
                ordinal,
            ),
        )
        count += 1
    db.commit()
    db.close()
    return count


def conversation_messages(conversation_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    db = connect()
    rows = db.execute(
        """SELECT source_id, role, author, content, created_at, ordinal
           FROM messages WHERE conversation_id=?
           ORDER BY ordinal ASC LIMIT ?""",
        (conversation_id, limit),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def list_sources() -> List[Dict[str, Any]]:
    db = connect()
    rows = db.execute(
        """SELECT id, kind, title, imported_at, sha256, local_path, metadata_json
           FROM sources ORDER BY imported_at DESC"""
    ).fetchall()
    db.close()
    out = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json"))
        out.append(item)
    return out


def add_local_turn(conversation_id: str, role: str, content: str, context_receipt: Optional[str] = None) -> int:
    db = connect()
    cur = db.execute(
        """INSERT INTO turns(conversation_id, role, content, created_at, context_receipt)
           VALUES (?, ?, ?, ?, ?)""",
        (conversation_id, role, content, now_iso(), context_receipt),
    )
    db.commit()
    turn_id = int(cur.lastrowid)
    db.close()
    return turn_id


def recent_local_turns(conversation_id: str, limit: int = 40) -> List[Dict[str, Any]]:
    db = connect()
    rows = db.execute(
        """SELECT id, role, content, created_at, context_receipt
           FROM turns WHERE conversation_id=? ORDER BY id DESC LIMIT ?""",
        (conversation_id, limit),
    ).fetchall()
    db.close()
    return [dict(r) for r in reversed(rows)]


def build_context(conversation_id: str, max_source_messages: int = 120) -> Dict[str, Any]:
    companion = load_companion()
    source_messages = conversation_messages(conversation_id, limit=max_source_messages)
    local_turns = recent_local_turns(conversation_id)
    context = {
        "companion": companion,
        "source_messages": source_messages,
        "local_turns": local_turns,
        "boundary": {
            "statement": "Imported continuity is local source context, not proof of a numerically identical cloud session.",
            "tools_enabled": load_config().get("tools_enabled", False),
        },
    }
    receipt = {
        "at": now_iso(),
        "conversation_id": conversation_id,
        "source_refs": sorted({m["source_id"] for m in source_messages if m.get("source_id")}),
        "source_message_count": len(source_messages),
        "local_turn_count": len(local_turns),
        "companion_continuity_version": companion.get("continuity_version"),
        "context_sha256": sha256_json(context),
    }
    path = RECEIPT_DIR / f"context_{receipt['context_sha256'][:20]}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    receipt["receipt_path"] = str(path)
    return {"context": context, "receipt": receipt}


def allowed_path(path: Path, roots: Iterable[str]) -> bool:
    resolved = path.expanduser().resolve()
    for root in roots:
        rr = Path(root).expanduser().resolve()
        try:
            resolved.relative_to(rr)
            return True
        except ValueError:
            pass
    return False


def tool_list_dir(path: str) -> Dict[str, Any]:
    config = load_config()
    if not config.get("tools_enabled"):
        raise PermissionError("Local tools are disabled.")
    roots = config.get("allowed_roots", [])
    target = Path(path)
    if not allowed_path(target, roots):
        raise PermissionError("Path is outside configured Sanctuary roots.")
    entries = []
    for p in sorted(target.expanduser().resolve().iterdir(), key=lambda x: x.name.lower()):
        entries.append({"name":p.name, "type":"dir" if p.is_dir() else "file"})
    return {"path":str(target.expanduser().resolve()), "entries":entries[:500]}


def tool_read_file(path: str, max_bytes: int = 200000) -> Dict[str, Any]:
    config = load_config()
    if not config.get("tools_enabled"):
        raise PermissionError("Local tools are disabled.")
    roots = config.get("allowed_roots", [])
    target = Path(path)
    if not allowed_path(target, roots):
        raise PermissionError("Path is outside configured Sanctuary roots.")
    resolved = target.expanduser().resolve()
    raw = resolved.read_bytes()[:max_bytes]
    text = raw.decode("utf-8", errors="replace")
    result = {"path":str(resolved), "bytes_read":len(raw), "sha256":sha256_bytes(raw), "text":text}
    receipt = {
        "tool":"read_file",
        "request":{"path":str(resolved), "max_bytes":max_bytes},
        "result_sha256":sha256_json(result),
        "at":now_iso(),
        "sent_to_runtime":False,
    }
    receipt_path = RECEIPT_DIR / f"tool_{receipt['result_sha256'][:20]}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    db = connect()
    db.execute(
        """INSERT INTO tool_receipts(tool_name, request_json, result_sha256, created_at, receipt_path)
           VALUES (?, ?, ?, ?, ?)""",
        ("read_file", json.dumps(receipt["request"]), receipt["result_sha256"], receipt["at"], str(receipt_path)),
    )
    db.commit()
    db.close()
    return {**result, "receipt_path":str(receipt_path)}
