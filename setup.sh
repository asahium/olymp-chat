#!/usr/bin/env bash
# One-time setup: checks prerequisites, creates .env (auto-generating JWT_SECRET
# and ADMIN_TOKEN, prompting for the OpenRouter key), installs backend + frontend
# dependencies, and builds the frontend.
#
# After this finishes, just run:   ./run.sh          (LAN)
#                            or:   ./run-public.sh   (LAN + public tunnel)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT/.env"

say() { printf "\n\033[1m%s\033[0m\n" "$1"; }

# --- 1. Prerequisites --------------------------------------------------------
say "1/5  Checking prerequisites…"
missing=0
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ✗ python3 not found  (macOS: brew install python  |  Ubuntu: sudo apt install python3 python3-venv)"
  missing=1
else
  echo "  ✓ python3 $(python3 -c 'import platform;print(platform.python_version())')"
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "  ✗ node/npm not found  (macOS: brew install node  |  Ubuntu: sudo apt install nodejs npm)"
  missing=1
else
  echo "  ✓ node $(node --version)  npm $(npm --version)"
fi
[ "$missing" -eq 0 ] || { echo "Install the missing tools above and re-run ./setup.sh"; exit 1; }

# --- 2. .env -----------------------------------------------------------------
set_env() {  # set_env KEY VALUE  (updates or appends in .env)
  python3 - "$ENV_FILE" "$1" "$2" <<'PY'
import re, sys
path, key, val = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(path).read().splitlines()
out, found = [], False
for l in lines:
    if re.match(rf'^{re.escape(key)}=', l):
        out.append(f'{key}={val}'); found = True
    else:
        out.append(l)
if not found:
    out.append(f'{key}={val}')
open(path, 'w').write('\n'.join(out) + '\n')
PY
}

say "2/5  Setting up .env…"
if [ -f "$ENV_FILE" ]; then
  echo "  .env already exists — leaving it as is (delete it and re-run to regenerate)."
else
  cp "$ROOT/.env.example" "$ENV_FILE"

  # Generate secrets
  JWT="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  ADMIN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  set_env JWT_SECRET "$JWT"
  set_env ADMIN_TOKEN "$ADMIN"
  echo "  ✓ Generated JWT_SECRET and ADMIN_TOKEN"

  # OpenRouter key: from env var if present, else prompt
  KEY="${OPENROUTER_API_KEY:-}"
  if [ -z "$KEY" ]; then
    printf "  Enter your OpenRouter API key (or leave empty to fill later): "
    read -r KEY
  fi
  [ -n "$KEY" ] && set_env OPENROUTER_API_KEY "$KEY" && echo "  ✓ Saved OpenRouter API key" \
    || echo "  ! No key entered — edit OPENROUTER_API_KEY in .env before running."

  echo ""
  echo "  ==> Admin dashboard password (ADMIN_TOKEN):  $ADMIN"
  echo "      (also stored in .env; used at /admin)"
fi

# --- 3. Backend deps ---------------------------------------------------------
say "3/5  Installing backend dependencies…"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt
echo "  ✓ Python venv ready"

# --- 4. Frontend deps + build ------------------------------------------------
say "4/5  Installing frontend dependencies and building…"
cd "$ROOT/frontend"
npm install --silent
npm run build
echo "  ✓ Frontend built"

# --- 5. Optional: participant codes -----------------------------------------
say "5/5  Participants (optional)…"
printf "  How many participant codes to generate now? (number, or Enter to skip): "
read -r COUNT || COUNT=""
if [ -n "${COUNT:-}" ] && [ "$COUNT" -eq "$COUNT" ] 2>/dev/null && [ "$COUNT" -gt 0 ]; then
  cd "$ROOT/backend"
  # shellcheck disable=SC1090
  set -a; . "$ENV_FILE"; set +a
  export DATABASE_URL="sqlite:///$ROOT/data/app.db"
  ./.venv/bin/python manage.py generate-participants --count "$COUNT"
  echo "  ✓ Codes above also saved in the DB (list later: python manage.py list-participants)"
else
  echo "  Skipped. Generate later with:"
  echo "    cd backend && source .venv/bin/activate && python manage.py generate-participants --count 20"
fi

say "Done! Next:"
echo "  ./run.sh          # serve on this machine + LAN (http://localhost:8000)"
echo "  ./run-public.sh   # same, plus a public Cloudflare tunnel URL"
echo ""
