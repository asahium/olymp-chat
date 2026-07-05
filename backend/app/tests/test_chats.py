"""Server-side saved chats (cross-device history)."""
from .conftest import auth_headers


def test_chats_require_auth(client):
    assert client.get("/api/chats").status_code == 401
    assert client.put("/api/chats", json={"chats": []}).status_code == 401


def test_save_and_fetch_chats(client, token):
    payload = {"chats": [
        {"id": "c1", "updated_at": 100,
         "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]},
        {"id": "c2", "updated_at": 200,
         "messages": [{"role": "user", "content": "second"}]},
    ]}
    assert client.put("/api/chats", headers=auth_headers(token), json=payload).status_code == 200

    # A "different device" (same participant) fetches the same chats, newest first.
    got = client.get("/api/chats", headers=auth_headers(token)).json()["chats"]
    assert [c["id"] for c in got] == ["c2", "c1"]
    assert got[1]["messages"][1]["content"] == "hello"


def test_only_last_two_chats_kept(client, token):
    payload = {"chats": [
        {"id": "a", "updated_at": 1, "messages": []},
        {"id": "b", "updated_at": 2, "messages": []},
        {"id": "c", "updated_at": 3, "messages": []},
    ]}
    client.put("/api/chats", headers=auth_headers(token), json=payload)
    got = client.get("/api/chats", headers=auth_headers(token)).json()["chats"]
    assert [c["id"] for c in got] == ["c", "b"]


def test_chats_are_per_participant(client, token):
    # Save under the first participant (bound to `token`).
    client.put("/api/chats", headers=auth_headers(token),
               json={"chats": [{"id": "mine", "updated_at": 5, "messages": []}]})
    # A genuinely different participant sees none of them.
    from app import provisioning
    second = provisioning.generate_participants(1)[0]
    other = client.post("/api/login", json={"login_code": second["login_code"]}).json()
    got = client.get("/api/chats", headers=auth_headers(other["token"])).json()["chats"]
    assert got == []