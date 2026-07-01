"""Auth invariants D (401) and E (403)."""
from app import database

from .conftest import auth_headers


def test_case_d_unauthenticated_401(client):
    """D: request without a token is rejected with 401."""
    resp = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 401

    resp = client.get("/api/me")
    assert resp.status_code == 401

    resp = client.post(
        "/api/chat",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


def test_invalid_login_code_401(client):
    resp = client.post("/api/login", json={"login_code": "WRNG-0000"})
    assert resp.status_code == 401


def test_case_e_disabled_participant_403(client, token, new_participant):
    """E: a participant disabled after login is rejected with 403."""
    # Sanity: works while active.
    ok = client.get("/api/me", headers=auth_headers(token))
    assert ok.status_code == 200

    database.set_active(new_participant["participant_id"], False)

    resp = client.get("/api/me", headers=auth_headers(token))
    assert resp.status_code == 403

    resp = client.post(
        "/api/chat", headers=auth_headers(token),
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 403


def test_disabled_participant_cannot_login(client, new_participant):
    database.set_active(new_participant["participant_id"], False)
    resp = client.post("/api/login", json={"login_code": new_participant["login_code"]})
    assert resp.status_code == 401
