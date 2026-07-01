"""Rate-limit invariant G: RPM -> 429, and contest quota -> 403."""
from app import database

from .conftest import auth_headers


def test_case_g_rpm_429(client, token):
    """G: the 6th request within a minute (RPM=5) returns 429."""
    payload = {"messages": [{"role": "user", "content": "hi"}]}
    for _ in range(5):
        r = client.post("/api/chat", headers=auth_headers(token), json=payload)
        assert r.status_code == 200
    r = client.post("/api/chat", headers=auth_headers(token), json=payload)
    assert r.status_code == 429
    assert "error" in r.json() or "detail" in r.json()


def test_quota_exhausted_403(client, token, new_participant):
    """Once TOTAL_REQUESTS_PER_PARTICIPANT logged rows exist, chat returns 403."""
    pid = new_participant["participant_id"]
    total = 300
    for i in range(total):
        database.insert_log({
            "request_id": f"{pid}-{i}",
            "timestamp": database.utcnow_iso(),
            "participant_id": pid,
            "team_id": new_participant["team_id"],
            "model_used": "google/gemma-3-27b-it",
            "enforced_max_tokens": 1000,
            "input_character_count": 2,
            "messages_json": "[]",
            "response_text": "ok",
            "provider_status_code": 200,
            "provider_error": None,
            "duration_ms": 1,
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
        })
    r = client.post(
        "/api/chat", headers=auth_headers(token),
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403


def test_reset_quota_restores_access(client, token, new_participant):
    """reset-quota moves the counting window so prior requests stop counting."""
    pid = new_participant["participant_id"]
    for i in range(300):
        database.insert_log({
            "request_id": f"{pid}-r-{i}", "timestamp": database.utcnow_iso(),
            "participant_id": pid, "team_id": None,
            "model_used": "m", "enforced_max_tokens": 1000, "input_character_count": 1,
            "messages_json": "[]", "response_text": None, "provider_status_code": 200,
            "provider_error": None, "duration_ms": 1, "prompt_tokens": None,
            "completion_tokens": None, "total_tokens": None,
        })
    assert database.count_requests(pid) == 300
    database.reset_quota(pid)
    assert database.count_requests(pid) == 0
