"""Test fixtures: temp DB, dummy secrets, and a fake OpenRouter transport.

Environment is set *before* importing the app so ``get_settings()`` picks it up.
The fake ``_http_post`` records every outbound payload, letting the enforcement
tests assert on exactly what the backend would send to the provider.
"""
import os
import tempfile
import uuid

# Sentinel key: must never appear in any API response or the frontend bundle.
SECRET_KEY = "sk-or-test-SECRETKEY-DONOTLEAK-0123456789"

_tmpdir = tempfile.mkdtemp(prefix="aioi-test-")
os.environ["OPENROUTER_API_KEY"] = SECRET_KEY
os.environ["JWT_SECRET"] = "test-jwt-secret"
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ["CORS_ORIGINS"] = ""
os.environ["RPM_PER_PARTICIPANT"] = "5"
os.environ["RPH_PER_PARTICIPANT"] = "100"
os.environ["TOTAL_REQUESTS_PER_PARTICIPANT"] = "300"

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import database, openrouter, provisioning  # noqa: E402
from app.main import app  # noqa: E402

# Captured outbound provider payloads (most recent last).
SENT_PAYLOADS: list[dict] = []


def _fake_response(payload: dict) -> httpx.Response:
    body = {
        "choices": [{"message": {"role": "assistant", "content": "canned reply"}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
    }
    return httpx.Response(200, json=body, request=httpx.Request("POST", "http://fake"))


async def _fake_http_post(url, headers, payload, timeout):
    SENT_PAYLOADS.append(payload)
    return _fake_response(payload)


@pytest.fixture(autouse=True)
def _patch_provider(monkeypatch):
    SENT_PAYLOADS.clear()
    monkeypatch.setattr(openrouter, "_http_post", _fake_http_post)
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def new_participant():
    """Create a fresh active participant and return its dict (unique per call)."""
    database.init_db()
    code = f"TEST-{uuid.uuid4().hex[:8].upper()}"
    idx = database.next_participant_index()
    pid = f"p{idx:03d}"
    return database.create_participant(pid, f"Participant {idx:03d}", "team-test", code)


@pytest.fixture
def token(client, new_participant):
    resp = client.post("/api/login", json={"login_code": new_participant["login_code"]})
    assert resp.status_code == 200
    return resp.json()["token"]


def auth_headers(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}
