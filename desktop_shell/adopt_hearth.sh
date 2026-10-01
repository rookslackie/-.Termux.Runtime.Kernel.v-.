#!/usr/bin/env bash
set -euo pipefail

ROOT="${HEARTH_ROOT:-/root/xi-termux-kernel-desktop}"
XI_HOME="${XI_SHELL_HOME:-/root/.anam-shell}"
VENV="$XI_HOME/venv"
PORT="${XI_HEARTH_PORT:-8877}"
OLD_SERVICE="anam-shell.service"
NEW_SERVICE="xi-hearth.service"

say(){ printf '\n[Ξ.Hearth] %s\n' "$*"; }

[ -x "$VENV/bin/python" ] || { echo "Existing shell venv not found at $VENV" >&2; exit 1; }
[ -d "$ROOT/desktop_shell" ] || { echo "Desktop shell source not found at $ROOT" >&2; exit 1; }

say "Preserving existing Home at $XI_HOME"

if systemctl list-unit-files "$OLD_SERVICE" >/dev/null 2>&1; then
  say "Stopping old service name (data untouched)"
  systemctl disable --now "$OLD_SERVICE" 2>/dev/null || true
fi

cat >"/etc/systemd/system/$NEW_SERVICE" <<EOF
[Unit]
Description=Xi Hearth — Anam local continuity shell
After=network.target

[Service]
Type=simple
WorkingDirectory=$ROOT
Environment=PYTHONPATH=$ROOT/desktop_shell
Environment=XI_SHELL_HOME=$XI_HOME
Environment=XI_SHELL_NAME=Anam
ExecStart=$VENV/bin/python -m uvicorn app:app --app-dir $ROOT/desktop_shell --host 127.0.0.1 --port $PORT
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$NEW_SERVICE"
sleep 1

say "Health"
curl -fsS "http://127.0.0.1:$PORT/health"
printf "\n"

say "Service"
systemctl --no-pager --full status "$NEW_SERVICE" || true

say "Existing access token location"
printf "  %s/access.token\n" "$XI_HOME"

cat <<EOF

Ξ.Hearth adopted.
Resident: Anam
Home:     $XI_HOME
Port:     $PORT
Service:  $NEW_SERVICE

No continuity data or token was replaced.
∴
EOF
