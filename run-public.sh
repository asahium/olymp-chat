#!/usr/bin/env bash
# One-command launcher for handover: starts the backend AND a Cloudflare quick
# tunnel, then prints the current public URL. Ctrl+C stops both.
#
# Note: on a free quick tunnel the URL changes each run. For a permanent address
# you need a domain on Cloudflare + a named tunnel (see README).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"
TUNNEL_LOG="/tmp/aioi-tunnel.log"

command -v cloudflared >/dev/null 2>&1 || {
  echo "cloudflared not found. Install it: brew install cloudflared"; exit 1;
}

cleanup() {
  echo ""; echo "Stopping…"
  [ -n "${TUNNEL_PID:-}" ] && kill "$TUNNEL_PID" 2>/dev/null || true
  [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

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
echo "Starting Cloudflare tunnel…"
: > "$TUNNEL_LOG"
cloudflared tunnel --url "http://localhost:$PORT" --protocol http2 > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

# 4) Extract and show the public URL
URL=""
for _ in $(seq 1 30); do
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || echo '<lan-ip>')"
echo ""
echo "=================================================================="
echo "  AIOI Contest Chat is LIVE"
echo "  Public (share this):  ${URL:-<starting… check $TUNNEL_LOG>}"
echo "  Same WiFi:            http://$LAN_IP:$PORT"
echo "  Admin dashboard:      http://localhost:$PORT/admin"
echo "=================================================================="
echo "  Press Ctrl+C to stop both server and tunnel."
echo ""

# Keep running until either process exits
wait -n "$SERVER_PID" "$TUNNEL_PID" 2>/dev/null || wait
