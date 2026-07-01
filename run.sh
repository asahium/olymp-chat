#!/usr/bin/env bash
# Launch the AIOI contest chat on this laptop, reachable by everyone on the
# same WiFi network. Binds to 0.0.0.0 so other devices can connect via the
# laptop's LAN IP (e.g. http://192.168.0.179:8000).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/backend"

# Python venv
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# Build the frontend if the bundle is missing
if [ ! -f "$ROOT/frontend/dist/index.html" ]; then
  echo "Building frontend..."
  (cd "$ROOT/frontend" && npm install --silent && npm run build)
fi

# Load .env from repo root into the environment (env vars take precedence in config)
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
# Keep the SQLite DB at repo-root/data regardless of cwd
export DATABASE_URL="sqlite:///$ROOT/data/app.db"

PORT="${PORT:-8000}"
IP="$(ipconfig getifaddr en0 2>/dev/null || echo '<your-lan-ip>')"
echo ""
echo "=================================================================="
echo "  AIOI Contest Chat is starting"
echo "  This laptop:      http://localhost:$PORT"
echo "  Others on WiFi:   http://$IP:$PORT"
echo "=================================================================="
echo ""

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
