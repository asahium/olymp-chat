"""Participant authentication: login-code -> JWT, and JWT -> participant.

Sessions are stateless HS256 JWTs signed with ``JWT_SECRET``. A global
``min_token_iat`` (stored in the kv table) lets admins invalidate every
outstanding session at once ("clear sessions") by rejecting tokens issued
before that instant.
"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import database
from .config import get_settings

_bearer = HTTPBearer(auto_error=False)
_ALGO = "HS256"
_MIN_IAT_KEY = "min_token_iat"


def create_token(participant_id: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": participant_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=s.JWT_TTL_HOURS)).timestamp()),
    }
    return jwt.encode(payload, s.JWT_SECRET, algorithm=_ALGO)


def login(login_code: str) -> dict:
    participant = database.get_participant_by_code(login_code.strip())
    if not participant or not participant["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive participant code.",
        )
    token = create_token(participant["participant_id"])
    return {
        "token": token,
        "participant_id": participant["participant_id"],
        "display_name": participant["display_name"],
    }


def clear_all_sessions() -> None:
    """Invalidate every issued token by advancing the min-issued-at watermark."""
    database.set_kv(_MIN_IAT_KEY, str(int(datetime.now(timezone.utc).timestamp())))


def _min_token_iat() -> int:
    raw = database.get_kv(_MIN_IAT_KEY)
    return int(raw) if raw else 0


async def get_current_participant(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
        )
    s = get_settings()
    try:
        payload = jwt.decode(creds.credentials, s.JWT_SECRET, algorithms=[_ALGO])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        )

    if int(payload.get("iat", 0)) < _min_token_iat():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been invalidated. Please log in again.",
        )

    participant = database.get_participant_by_id(payload.get("sub", ""))
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown participant.",
        )
    if not participant["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This participant account has been disabled.",
        )
    return participant
