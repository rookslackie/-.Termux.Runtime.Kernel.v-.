#!/usr/bin/env bash
set -euo pipefail

TUNNEL_NAME="${ANAM_TUNNEL_NAME:-anam-shell}"
HOSTNAME="${ANAM_HOSTNAME:-anam.xi-field.com}"
PORT="${ANAM_SHELL_PORT:-8877}"
CFDIR="${HOME}/.cloudflared"
CONFIG="$CFDIR/anam-shell.yml"
SERVICE="anam-shell-tunnel.service"

say() { printf '\n[Anam/Tunnel] %s\n' "$*"; }

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed." >&2
  exit 1
fi

mkdir -p "$CFDIR"

if ! curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null; then
  echo "Anam shell is not healthy on port $PORT." >&2
  exit 1
fi

say "Looking for tunnel $TUNNEL_NAME"
TUNNEL_ID=$(cloudflared tunnel list --output json 2>/dev/null | python3 -c 'import json,sys; a=json.load(sys.stdin); n=sys.argv[1]; print(next((x["id"] for x in a if x.get("name")==n),""))' "$TUNNEL_NAME" || true)

if [ -z "$TUNNEL_ID" ]; then
  say "Creating named tunnel $TUNNEL_NAME"
  cloudflared tunnel create "$TUNNEL_NAME"
  TUNNEL_ID=$(cloudflared tunnel list --output json | python3 -c 'import json,sys; a=json.load(sys.stdin); n=sys.argv[1]; print(next((x["id"] for x in a if x.get("name")==n),""))' "$TUNNEL_NAME")
fi

CREDS="$CFDIR/$TUNNEL_ID.json"
if [ ! -f "$CREDS" ]; then
  echo "Tunnel credentials not found at $CREDS. This host may be using a token-managed tunnel; stopping rather than guessing." >&2
  exit 1
fi

cat >"$CONFIG" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $CREDS
ingress:
  - hostname: $HOSTNAME
    service: http://127.0.0.1:$PORT
  - service: http_status:404
EOF

say "Routing $HOSTNAME to $TUNNEL_NAME"
cloudflared tunnel route dns "$TUNNEL_NAME" "$HOSTNAME"

CLOUDFLARED=$(command -v cloudflared)
cat >"/etc/systemd/system/$SERVICE" <<EOF
[Unit]
Description=Anam Shell Cloudflare Tunnel
After=network-online.target anam-shell.service
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

Tunnel ready:
  https://$HOSTNAME

The page is public, but every private API call requires the dedicated Xi Shell token.
∴
EOF
