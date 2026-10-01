#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/desktop_shell${PYTHONPATH:+:$PYTHONPATH}"
exec python -m uvicorn app:app --app-dir desktop_shell --host 127.0.0.1 --port 8765
