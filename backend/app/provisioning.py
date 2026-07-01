"""Shared participant-provisioning logic (used by the CLI and admin endpoint)."""
import secrets

from . import database

# Unambiguous alphabet (no O/0, I/1, etc.) for human-typed login codes.
_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_DIGITS = "23456789"


def generate_login_code() -> str:
    left = "".join(secrets.choice(_LETTERS) for _ in range(4))
    right = "".join(secrets.choice(_DIGITS) for _ in range(4))
    return f"{left}-{right}"


def generate_participants(count: int, team_prefix: str = "team") -> list[dict]:
    """Create ``count`` participants with sequential ids and random login codes."""
    start = database.next_participant_index()
    created = []
    for i in range(count):
        idx = start + i
        pid = f"p{idx:03d}"
        display_name = f"Participant {idx:03d}"
        team_id = team_prefix
        # Retry on the (extremely unlikely) code collision.
        for _ in range(10):
            code = generate_login_code()
            if database.get_participant_by_code(code) is None:
                break
        participant = database.create_participant(pid, display_name, team_id, code)
        created.append({**participant, "login_code": code})
    return created
