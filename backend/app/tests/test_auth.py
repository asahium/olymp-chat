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


def test_change_code_requires_auth(client):
    resp = client.post("/api/change-code", json={"new_code": "MYNEWCODE"})
    assert resp.status_code == 401


def test_change_code_updates_login(client, token, new_participant):
    old_code = new_participant["login_code"]
    new_code = "MyPrivate-9"
    resp = client.post("/api/change-code", headers=auth_headers(token), json={"new_code": new_code})
    assert resp.status_code == 200

    # Old code no longer works; new one does.
    assert client.post("/api/login", json={"login_code": old_code}).status_code == 401
    assert client.post("/api/login", json={"login_code": new_code}).status_code == 200


def test_change_code_rejects_short_and_duplicate(client, token, new_participant):
    assert client.post("/api/change-code", headers=auth_headers(token),
                       json={"new_code": "ab"}).status_code == 400
    # Duplicate of another existing participant's code.
    other = client.post("/api/login", json={"login_code": new_participant["login_code"]})
    # Create a second participant and try to steal its code.
    from app import provisioning
    second = provisioning.generate_participants(1)[0]
    resp = client.post("/api/change-code", headers=auth_headers(token),
                       json={"new_code": second["login_code"]})
    assert resp.status_code == 409
    assert other.status_code == 200
