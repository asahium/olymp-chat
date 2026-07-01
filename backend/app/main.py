"""FastAPI application: auth, chat proxy, admin, and static frontend serving.

This backend is the security boundary. The browser may send only conversation
messages; the real OpenRouter payload is constructed server-side with fixed
model / max_tokens / generation settings.
"""
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import auth, database, logging_service, openrouter, provisioning
from .config import get_settings
from .constants import SYSTEM_PROMPT  # noqa: F401 (documents where prompt lives)
from .models import (
    ChatLimits,
    ChatRequest,
    ChatResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
)
from .rate_limit import rate_limiter

# Generous cap on the raw request body (well above MAX_INPUT_CHARS + JSON overhead).
_MAX_BODY_BYTES = 256 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    missing = [name for name in ("OPENROUTER_API_KEY", "JWT_SECRET") if not getattr(s, name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    database.init_db()
    yield


app = FastAPI(title="AIOI Contest Chat", lifespan=lifespan)

_cors = [o.strip() for o in get_settings().CORS_ORIGINS.split(",") if o.strip()]
if _cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl is not None and cl.isdigit() and int(cl) > _MAX_BODY_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"error": "Request body too large."},
        )
    return await call_next(request)


# --- public API --------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/login", response_model=LoginResponse)
async def api_login(body: LoginRequest):
    return auth.login(body.login_code)


@app.get("/api/me", response_model=MeResponse)
async def api_me(participant: dict = Depends(auth.get_current_participant)):
    return MeResponse(
        participant_id=participant["participant_id"],
        display_name=participant["display_name"],
        team_id=participant["team_id"],
        remaining_requests=rate_limiter.remaining_quota(participant["participant_id"]),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(body: ChatRequest, participant: dict = Depends(auth.get_current_participant)):
    s = get_settings()
    pid = participant["participant_id"]

    if not body.messages:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No messages provided.")

    input_chars = sum(len(m.content) for m in body.messages)
    if input_chars > s.MAX_INPUT_CHARS:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Input too large. Limit is {s.MAX_INPUT_CHARS} characters.",
        )

    rate_limiter.check_quota(pid)   # 403 if contest quota exhausted
    rate_limiter.check_rate(pid)    # 429 if RPM/RPH exceeded

    payload = openrouter.build_payload(
        [m.model_dump() for m in body.messages], s
    )

    request_id = uuid.uuid4().hex
    started = time.monotonic()
    provider_status: int | None = None
    provider_error: str | None = None
    response_text = ""
    usage: dict = {}
    err: openrouter.ProviderError | None = None

    try:
        provider_body = await openrouter.call_openrouter(payload, s)
        provider_status = 200
        response_text = openrouter.extract_content(provider_body)
        usage = provider_body.get("usage") or {}
    except openrouter.ProviderError as e:
        err = e
        provider_status = e.provider_status
        provider_error = e.user_message

    duration_ms = int((time.monotonic() - started) * 1000)
    logging_service.log_request({
        "request_id": request_id,
        "timestamp": database.utcnow_iso(),
        "participant_id": pid,
        "team_id": participant["team_id"],
        "model_used": s.OPENROUTER_MODEL,
        "enforced_max_tokens": s.MAX_OUTPUT_TOKENS,
        "input_character_count": input_chars,
        "messages_json": _dump_messages(payload["messages"]),
        "response_text": response_text or None,
        "provider_status_code": provider_status,
        "provider_error": provider_error,
        "duration_ms": duration_ms,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    })

    if err is not None:
        raise HTTPException(status_code=err.http_status, detail=err.user_message)

    return ChatResponse(
        message={"role": "assistant", "content": response_text},
        usage={
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        limits=ChatLimits(max_output_tokens=s.MAX_OUTPUT_TOKENS),
    )


def _dump_messages(messages: list[dict]) -> str:
    import json
    return json.dumps(messages, ensure_ascii=False)


# --- admin API (guarded by ADMIN_TOKEN) --------------------------------------

def require_admin(x_admin_token: str | None = Header(default=None)):
    s = get_settings()
    if not s.ADMIN_TOKEN or x_admin_token != s.ADMIN_TOKEN:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin authentication required.")


@app.get("/api/admin/usage", dependencies=[Depends(require_admin)])
async def admin_usage():
    return logging_service.usage_summary()


@app.get("/api/admin/export-logs", dependencies=[Depends(require_admin)])
async def admin_export_logs():
    import io
    buf = io.StringIO()
    logging_service.export_jsonl(buf)
    return PlainTextResponse(buf.getvalue(), media_type="application/x-ndjson")


@app.post("/api/admin/participants", dependencies=[Depends(require_admin)])
async def admin_create_participants(body: dict):
    count = int(body.get("count", 1))
    team_prefix = str(body.get("team_prefix", "team"))
    created = provisioning.generate_participants(count, team_prefix)
    return {"participants": [
        {"participant_id": p["participant_id"], "display_name": p["display_name"],
         "team_id": p["team_id"], "login_code": p["login_code"]}
        for p in created
    ]}


@app.post("/api/admin/participants/{participant_id}/disable", dependencies=[Depends(require_admin)])
async def admin_disable_participant(participant_id: str):
    if not database.set_active(participant_id, False):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown participant.")
    return {"participant_id": participant_id, "is_active": False}


# --- static frontend (mounted last so /api/* wins) ---------------------------

def _frontend_dir() -> Path | None:
    override = get_settings().FRONTEND_DIST
    candidates = [Path(override)] if override else []
    candidates.append(Path(__file__).resolve().parents[2] / "frontend" / "dist")
    for c in candidates:
        if c.is_dir() and (c / "index.html").exists():
            return c
    return None


_dist = _frontend_dir()
if _dist is not None:
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
