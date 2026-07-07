#!/usr/bin/env bash
# One-command launcher: starts the backend AND both public tunnels
# (Cloudflare + ngrok), then prints every address. Ctrl+C stops everything.
#
# Note: free quick tunnels get a NEW random URL each run. For a permanent ngrok
# address, reserve a static domain (dashboard.ngrok.com/domains) and set
# NGROK_DOMAIN below (or export it before running).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"
TUNNEL_LOG="/tmp/aioi-tunnel.log"
NGROK_LOG="/tmp/aioi-ngrok.log"
NGROK_DOMAIN="${NGROK_DOMAIN:-}"   # optional: your reserved *.ngrok-free.app domain

cleanup() {
  echo ""; echo "Stopping…"
  for pid in "${NG_PID:-}" "${CF_PID:-}" "${SERVER_PID:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

have_cf=1; command -v cloudflared >/dev/null 2>&1 || have_cf=0
have_ng=1; command -v ngrok       >/dev/null 2>&1 || have_ng=0

# 1) Backend (run.sh binds 0.0.0.0 and serves the built SPA)
echo "Starting backend…"
"$ROOT/run.sh" > /tmp/aioi-server.log 2>&1 &
SERVER_PID=$!

# 2) Wait for health
for _ in $(seq 1 30); do
  curl -s "http://localhost:$PORT/api/health" >/dev/null 2>&1 && break
  sleep 1
done

# 3) Cloudflare quick tunnel (http2 avoids QUIC/UDP being blocked on some nets)
CF_URL=""
if [ "$have_cf" -eq 1 ]; then
  echo "Starting Cloudflare tunnel…"
  : > "$TUNNEL_LOG"
  cloudflared tunnel --url "http://localhost:$PORT" --protocol http2 > "$TUNNEL_LOG" 2>&1 &
  CF_PID=$!
  for _ in $(seq 1 30); do
    CF_URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -1 || true)"
    [ -n "$CF_URL" ] && break
    sleep 1
  done
else
  echo "cloudflared not installed — skipping (brew install cloudflared)"
fi

# 4) ngrok tunnel (reads authtoken from ngrok config; static domain if set)
NG_URL=""
if [ "$have_ng" -eq 1 ]; then
  echo "Starting ngrok tunnel…"
  : > "$NGROK_LOG"
  if [ -n "$NGROK_DOMAIN" ]; then
    ngrok http "$PORT" --url="$NGROK_DOMAIN" --log stdout > "$NGROK_LOG" 2>&1 &
  else
    ngrok http "$PORT" --log stdout > "$NGROK_LOG" 2>&1 &
  fi
  NG_PID=$!
  for _ in $(seq 1 20); do
    NG_URL="$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
      | python3 -c 'import sys,json
try:
    d=json.load(sys.stdin); t=[x["public_url"] for x in d.get("tunnels",[]) if x["public_url"].startswith("https")]
    print(t[0] if t else "")
except Exception: print("")' 2>/dev/null || true)"
    [ -n "$NG_URL" ] && break
    sleep 1
  done
  [ -z "$NG_URL" ] && echo "  (ngrok didn't report a URL — is the authtoken set? 'ngrok config add-authtoken …')"
else
  echo "ngrok not installed — skipping (brew install ngrok)"
fi

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || echo '<lan-ip>')"
echo ""
echo "=================================================================="
echo "  AIOI Contest Chat is LIVE"
echo "  Cloudflare (share):   ${CF_URL:-<none>}"
echo "  ngrok (backup):       ${NG_URL:-<none>}"
echo "  Same WiFi:            http://$LAN_IP:$PORT"
echo "  Admin dashboard:      http://localhost:$PORT/admin"
echo "=================================================================="
echo "  Press Ctrl+C to stop the server and both tunnels."
echo ""

# Keep running until any managed process exits
wait -n "$SERVER_PID" ${CF_PID:+"$CF_PID"} ${NG_PID:+"$NG_PID"} 2>/dev/null || wait
