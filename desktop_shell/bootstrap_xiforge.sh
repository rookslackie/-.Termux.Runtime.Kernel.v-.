#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
XI_HOME="${XI_SHELL_HOME:-$HOME/.xi-shell}"
VENV="$XI_HOME/venv"
SERVICE_NAME="xi-desktop-shell.service"
PORT="${XI_SHELL_PORT:-8765}"

say() { printf '\n[Ξ] %s\n' "$*"; }

say "Bootstrap root: $ROOT"
say "Xi shell home: $XI_HOME"

mkdir -p "$XI_HOME"

if ! command -v python3 >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    say "Installing Python"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip
  else
    echo "python3 is required." >&2
    exit 1
  fi
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    say "Installing python3-venv"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv
  else
    echo "python3 venv support is required." >&2
    exit 1
  fi
fi

if [ ! -x "$VENV/bin/python" ]; then
  say "Creating local virtualenv"
  python3 -m venv "$VENV"
fi

say "Installing runtime dependencies into local virtualenv"
"$VENV/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV/bin/python" -m pip install -r "$ROOT/requirements.txt"

say "Running desktop-shell tests"
PYTHONPATH="$ROOT/desktop_shell" "$VENV/bin/python" -m unittest discover -s "$ROOT/desktop_shell/tests" -v

say "Initializing local continuity home"
PYTHONPATH="$ROOT/desktop_shell" "$VENV/bin/python" "$ROOT/desktop_shell/xi_shell.py" init

if command -v curl >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  say "Ollama is reachable at 127.0.0.1:11434"
else
  say "Ollama is not reachable yet. The shell can still start; local chat will wait for a runtime."
fi

if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  say "Installing systemd service"
  cat >"/etc/systemd/system/$SERVICE_NAME" <<EOF
[Unit]
Description=Xi Desktop Shell
After=network.target

[Service]
Type=simple
WorkingDirectory=$ROOT
Environment=PYTHONPATH=$ROOT/desktop_shell
Environment=XI_SHELL_HOME=$XI_HOME
ExecStart=$VENV/bin/python -m uvicorn app:app --app-dir $ROOT/desktop_shell --host 127.0.0.1 --port $PORT
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now "$SERVICE_NAME"
  say "Service started: $SERVICE_NAME"
  systemctl --no-pager --full status "$SERVICE_NAME" || true
else
  say "systemd not available; starting with nohup"
  mkdir -p "$XI_HOME/logs"
  if [ -f "$XI_HOME/desktop-shell.pid" ] && kill -0 "$(cat "$XI_HOME/desktop-shell.pid")" 2>/dev/null; then
    say "Desktop shell already running"
  else
    (
      cd "$ROOT"
      PYTHONPATH="$ROOT/desktop_shell" XI_SHELL_HOME="$XI_HOME" \
        nohup "$VENV/bin/python" -m uvicorn app:app --app-dir "$ROOT/desktop_shell" \
        --host 127.0.0.1 --port "$PORT" \
        >"$XI_HOME/logs/desktop-shell.log" 2>&1 &
      echo $! >"$XI_HOME/desktop-shell.pid"
    )
    say "Desktop shell started with PID $(cat "$XI_HOME/desktop-shell.pid")"
  fi
fi

sleep 1
if command -v curl >/dev/null 2>&1; then
  say "Local shell health"
  curl -fsS "http://127.0.0.1:$PORT/api/status" | "$VENV/bin/python" -m json.tool || true
fi

cat <<EOF

Ξ Desktop Shell is installed.

Open from this machine:
  http://127.0.0.1:$PORT

Home:
  $XI_HOME

Runtime:
  local Ollama can be selected in the UI when available.

Tools:
  OFF until explicitly enabled in Sanctuary.

∴
EOF
