#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
XI_HOME="${ANAM_SHELL_HOME:-$HOME/.anam-shell}"
VENV="$XI_HOME/venv"
SERVICE_NAME="anam-shell.service"
PORT="${ANAM_SHELL_PORT:-8877}"

say() { printf '\n[Anam] %s\n' "$*"; }

mkdir -p "$XI_HOME"

if ! command -v python3 >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip
fi
if ! python3 -m venv --help >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv
fi

if [ ! -x "$VENV/bin/python" ]; then
  say "Creating dedicated virtualenv at $VENV"
  python3 -m venv "$VENV"
fi

say "Installing dedicated shell dependencies"
"$VENV/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV/bin/python" -m pip install -r "$ROOT/desktop_shell/requirements.txt"

say "Running tests"
XI_SHELL_HOME="$XI_HOME" PYTHONPATH="$ROOT/desktop_shell" "$VENV/bin/python" -m unittest discover -s "$ROOT/desktop_shell/tests" -v

say "Initializing dedicated Home"
XI_SHELL_HOME="$XI_HOME" PYTHONPATH="$ROOT/desktop_shell" "$VENV/bin/python" "$ROOT/desktop_shell/xi_shell.py" init

say "Ensuring access token"
TOKEN=$(XI_SHELL_HOME="$XI_HOME" PYTHONPATH="$ROOT/desktop_shell" "$VENV/bin/python" -c "from auth import ensure_token; print(ensure_token())")

cat >"/etc/systemd/system/$SERVICE_NAME" <<EOF
[Unit]
Description=Anam Xi Desktop Shell
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
sleep 1

say "Dedicated service status"
systemctl --no-pager --full status "$SERVICE_NAME" || true

say "Health"
curl -fsS "http://127.0.0.1:$PORT/health" || true
printf "\n"

cat <<EOF

Anam shell is ready.

Local URL:
  http://127.0.0.1:$PORT

Dedicated Home:
  $XI_HOME

Dedicated service:
  $SERVICE_NAME

Access token:
  $TOKEN

Keep that token private. The browser will ask for it once and store it locally.

∴
EOF
