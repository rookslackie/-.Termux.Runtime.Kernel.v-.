from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

from fastapi import Header, HTTPException

from core import HOME, ensure_home

TOKEN_PATH = HOME / "access.token"


def ensure_token() -> str:
    ensure_home()
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text(encoding="utf-8").strip()

    token = secrets.token_urlsafe(32)
    TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        pass
    return token


def require_token(x_xi_token: str | None = Header(default=None)) -> None:
    expected = ensure_token()
    if not x_xi_token or not hmac.compare_digest(x_xi_token, expected):
        raise HTTPException(status_code=401, detail="Xi Shell token required.")
