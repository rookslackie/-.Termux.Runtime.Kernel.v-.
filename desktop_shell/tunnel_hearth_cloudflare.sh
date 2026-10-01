#!/usr/bin/env bash
set -euo pipefail

TUNNEL_NAME="${XI_HEARTH_TUNNEL:-xi-hearth}"
HOSTNAME="${XI_HEARTH_HOSTNAME:-hearth.xi-field.com}"
PORT="${XI_HEARTH_PORT:-8877}"
CFDIR="${HOME}/.cloudflared"
CONFIG="$CFDIR/xi-hearth.yml"
SERVICE="xi-hearth-tunnel.service"

say(){ printf '\n[Ξ.Hearth/Tunnel] %s\n' "$*"; }

command -v cloudflared >/dev/null 2>&1 || { echo "cloudflared is not installed." >&2; exit 1; }
curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null || { echo "Hearth is not healthy on $PORT." >&2; exit 1; }
mkdir -p "$CFDIR"

TUNNEL_ID="$(cloudflared tunnel list --output json 2>/dev/null | python3 -c 'import json,sys; rows=json.load(sys.stdin); n=sys.argv[1]; print(next((r["id"] for r in rows if r.get("name")==n),""))' "$TUNNEL_NAME" || true)"
if [ -z "$TUNNEL_ID" ]; then
  say "Creating named tunnel $TUNNEL_NAME"
  cloudflared tunnel create "$TUNNEL_NAME"
  TUNNEL_ID="$(cloudflared tunnel list --output json | python3 -c 'import json,sys; rows=json.load(sys.stdin); n=sys.argv[1]; print(next((r["id"] for r in rows if r.get("name")==n),""))' "$TUNNEL_NAME")"
fi

CREDS="$CFDIR/$TUNNEL_ID.json"
[ -f "$CREDS" ] || { echo "Credentials missing at $CREDS; stopping without changing existing tunnels." >&2; exit 1; }

cat >"$CONFIG" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $CREDS
ingress:
  - hostname: $HOSTNAME
    service: http://127.0.0.1:$PORT
  - service: http_status:404
EOF

say "Creating DNS route for $HOSTNAME"
cloudflared tunnel route dns "$TUNNEL_NAME" "$HOSTNAME"

CLOUDFLARED="$(command -v cloudflared)"
cat >"/etc/systemd/system/$SERVICE" <<EOF
[Unit]
Description=Xi Hearth Cloudflare Tunnel
After=network-online.target xi-hearth.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=$CLOUDFLARED --config $CONFIG tunnel run
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE"
sleep 1
systemctl --no-pager --full status "$SERVICE" || true

cat <<EOF

Ξ.Hearth tunnel ready:
  https://$HOSTNAME

Local API remains token-gated.
∴
EOF
