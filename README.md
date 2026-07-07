# AIOI Prep-Camp Contest Chat

A lightweight, **browser-only** LLM chat for an AI-olympiad training camp. It simulates the
official contest restriction: one model (**Gemma 3 27B**), a hard **1000 output-token** cap,
per-participant rate limits and quotas, and full server-side logging.

Students install nothing — they open a URL in any modern browser (Chrome, Edge, Firefox,
Safari) on Windows/macOS/Linux and log in with a code the organizers hand out.

## Features

- Login by organizer-issued code; participants can **set their own private code** ("Change code").
- Chat with **Gemma 3 27B**, answers capped at **1000 tokens** (all generation settings fixed server-side).
- **Markdown rendering** with copy-able code blocks (works over plain HTTP too).
- **Edit any of your messages and re-run** the model from that point.
- **Recent 2 chats saved server-side** per participant — visible from any device after login.
- **Admin dashboard** at `/admin`: per-participant cost/tokens/limits, chat histories,
  who still uses the default code, quota reset (keeps stats), enable/disable.
- Per-participant rate limits (RPM/RPH) and a total contest quota.

## Quick start (TL;DR)

```bash
bash setup.sh     # one-time: prerequisites, .env (auto JWT + admin password), deps, build
./run.sh          # serve on this machine + LAN  (http://localhost:8000)
# or
./run-public.sh   # same, plus a public Cloudflare tunnel URL to share
```

## Architecture

```
Browser (React SPA)  ->  Backend (FastAPI)  ->  OpenRouter  ->  google/gemma-3-27b-it
```

The **backend is the security boundary**. The browser sends only conversation messages; the
backend builds the real provider request with fixed model / max_tokens / generation settings.
The OpenRouter API key lives **only** in a server environment variable and is never sent to,
stored in, or referenced by the browser.

- Frontend: React + Vite, built to static files and served by the backend (single origin).
- Persistence: SQLite (participants + chat logs).
- Rate limits: in-memory per participant (single worker); total quota persisted in SQLite.
- Chat: non-streaming (backend awaits the full response, returns JSON).

## Repository layout

```
olymp-chat/
  docker-compose.yml       # single backend service, ./data volume for SQLite
  .env.example
  backend/                 # FastAPI app, admin CLI, tests
    app/…  manage.py  Dockerfile  requirements.txt
  frontend/                # React + Vite SPA
    src/…  package.json  vite.config.ts
```

---

## 1. Create your `.env`

**Easiest:** run `bash setup.sh` — it creates `.env`, auto-generates `JWT_SECRET` and
`ADMIN_TOKEN`, prompts for your OpenRouter key, installs dependencies, builds the frontend,
and can generate participant codes. Then just `./run.sh`.

**Manual:**

```bash
cp .env.example .env
```

Fill in:

- `OPENROUTER_API_KEY` — your single OpenRouter key (server-side only).
- `JWT_SECRET` — a long random string: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `ADMIN_TOKEN` — a random string used for the `/api/admin/*` endpoints and the `/admin` dashboard.

Everything else has safe defaults (Gemma 3, 1000 tokens, RPM 5, RPH 100, quota 300).

## 2. Run with Docker (recommended)

```bash
docker compose up --build
```

The app is served at **http://localhost:8000** (backend serves the built SPA). The SQLite DB
persists in `./data`.

## 3. Generate participant codes

Run the admin CLI inside the container (or locally, see below):

```bash
docker compose exec backend python manage.py generate-participants --count 50 --team-prefix team
```

This prints CSV (`participant_id,display_name,team_id,login_code`). Hand each `login_code`
to a student. You can also list them later:

```bash
docker compose exec backend python manage.py list-participants
```

## 4. Start the app / hand out codes

Students open `http://<server-host>:8000`, enter their `login_code`, and chat. The UI shows
the fixed note **"Model: Gemma 3. Max answer length: 1000 output tokens."** and exposes no
model / temperature / token / tools / upload controls.

---

## Local development (without Docker)

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env in repo root is read automatically; or export the vars
uvicorn app.main:app --reload --port 8000
```

**Frontend (dev server with API proxy):**

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api -> :8000
```

For a production-style single-origin run, `npm run build` then start the backend — it
auto-detects `frontend/dist`.

---

## Admin operations

### Dashboard (visual)

Open **`http://localhost:8000/admin`**, paste your `ADMIN_TOKEN`, and you get: per-participant
cost/tokens/requests, current limit (left/total), who still uses the default code, each
participant's chat history, plus buttons to reset a limit (keeps usage stats), reset all
limits, and enable/disable. Prefer opening it via `localhost` rather than a public tunnel.

### CLI

All admin CLI commands (run locally in `backend/` or via `docker compose exec backend`):

```bash
python manage.py generate-participants --count 50 --team-prefix team
python manage.py list-participants
python manage.py set-name p017 "Jane Doe"      # set display name (by id or code)
python manage.py disable-participant p017      # revoke access
python manage.py reset-quota p017              # restore contest quota (keeps stats)
python manage.py clear-logs p017               # delete a participant's chat logs
python manage.py export-logs --output logs.jsonl   # or logs.csv
python manage.py usage-summary                 # per-participant + total tokens
python manage.py clear-sessions                # invalidate all issued tokens
```

Equivalent HTTP admin endpoints (send header `X-Admin-Token: <ADMIN_TOKEN>`):

```
GET  /api/admin/usage
GET  /api/admin/export-logs
POST /api/admin/participants                       {"count": 10, "team_prefix": "team"}
POST /api/admin/participants/{id}/disable
```

### Export logs

```bash
python manage.py export-logs --output logs.jsonl
```

Each row includes `request_id`, `timestamp`, `participant_id`, `team_id`, `model_used`,
`enforced_max_tokens`, `input_character_count`, the prompt messages, response text,
provider status/error, duration, and token counts. Logs are never exposed to participants.

### Reset / disable a participant

```bash
python manage.py disable-participant p017   # blocks login + in-flight sessions (403)
python manage.py reset-quota p017           # resets the per-contest request count
```

---

## API reference

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET  | `/api/health` | — | Health check `{"status":"ok"}` |
| POST | `/api/login`  | — | `{login_code}` → `{token, participant_id, display_name}` |
| POST | `/api/chat`   | Bearer | `{messages:[{role,content}]}` → `{message, usage, limits}` |
| GET  | `/api/me`     | Bearer | Participant info + `remaining_requests` |
| POST | `/api/change-code` | Bearer | `{new_code}` → set your own private login code |
| GET/PUT | `/api/chats` | Bearer | Fetch/save the last 2 chats (server-side, cross-device) |
| GET  | `/admin`      | — (token in page) | Admin dashboard UI |

---

## Verifying the security guarantees

### Test OpenRouter connectivity

```bash
curl http://localhost:8000/api/health           # {"status":"ok"}

# Log in with a generated code, then send a chat:
TOKEN=$(curl -s http://localhost:8000/api/login \
  -H 'Content-Type: application/json' \
  -d '{"login_code":"ABCD-2345"}' | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')

curl -s http://localhost:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Explain logistic regression."}]}'
```

### Verify `max_tokens=1000` is enforced

The backend ignores any client-supplied `max_tokens`/`model`/`tools`. This is proven by the
test suite — a fake provider transport captures the exact outbound payload:

```bash
cd backend && source .venv/bin/activate
pytest -q app/tests/test_enforcement.py     # cases A (max_tokens), B (model), C (tools), F, H
```

You can also confirm at runtime: every `/api/chat` response returns
`"limits": {"max_output_tokens": 1000}`, and each logged row has `enforced_max_tokens=1000`
(`python manage.py export-logs --output logs.jsonl`).

### Verify the OpenRouter key is not exposed to the browser

```bash
# No key or env var name in the built bundle:
grep -r "OPENROUTER" frontend/dist            # (no matches)

# No key in any API response (checked automatically):
pytest -q app/tests/test_enforcement.py -k key
```

The key is read only from `OPENROUTER_API_KEY` on the server, attached solely to the outbound
OpenRouter request, and never returned in responses or headers.

---

## Running the tests

```bash
cd backend && source .venv/bin/activate
pytest -q
```

Covers the enforcement invariants (client-supplied model/max_tokens/tools are overridden),
auth (401 unauthenticated, 403 disabled), rate limiting (429 over RPM, 403 over quota), and
key non-exposure.

## Security notes

- No API keys in the frontend; no client-trusted limits; no arbitrary passthrough to OpenRouter.
- Model output is rendered as **sanitized Markdown** (react-markdown, no raw HTML) to avoid XSS;
  user messages are shown as plain text.
- Request body size is capped; oversized input returns 413.
- Set `CORS_ORIGINS` and terminate TLS (HTTPS) at your reverse proxy for a public deployment.
- No file uploads, web browsing, tools, plugins, or multi-model selection.

## Non-goals

GAITE, Jupyter integration, task submission, scoreboard, file uploads, web browsing, RAG,
multi-model selection, user-provided keys, desktop app, browser extension, local inference.
