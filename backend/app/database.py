"""SQLite persistence: participants, chat logs, and a small key-value table.

Plain stdlib ``sqlite3`` to stay dependency-light. A new connection is opened
per operation, which is more than fast enough for a single-worker camp
deployment. The DB file lives in a mounted volume (see docker-compose).
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .config import get_settings


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    url = get_settings().DATABASE_URL
    if url.startswith("sqlite:///"):
        raw = url[len("sqlite:///"):]
    elif url.startswith("sqlite://"):
        raw = url[len("sqlite://"):]
    else:
        raw = url  # treat as a bare path
    return Path(raw).expanduser()


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS participants (
                participant_id TEXT PRIMARY KEY,
                display_name   TEXT NOT NULL,
                team_id        TEXT,
                login_code     TEXT NOT NULL UNIQUE,
                is_active      INTEGER NOT NULL DEFAULT 1,
                created_at     TEXT NOT NULL,
                reset_at       TEXT,
                code_changed   INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chat_logs (
                request_id            TEXT PRIMARY KEY,
                timestamp             TEXT NOT NULL,
                participant_id        TEXT NOT NULL,
                team_id               TEXT,
                model_used            TEXT NOT NULL,
                enforced_max_tokens   INTEGER NOT NULL,
                input_character_count INTEGER NOT NULL,
                messages_json         TEXT NOT NULL,
                response_text         TEXT,
                provider_status_code  INTEGER,
                provider_error        TEXT,
                duration_ms           INTEGER,
                prompt_tokens         INTEGER,
                completion_tokens     INTEGER,
                total_tokens          INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_logs_participant
                ON chat_logs (participant_id);

            CREATE TABLE IF NOT EXISTS kv (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            -- Server-side saved chats so a participant sees recent chats from
            -- any device after login. Kept to the last few per participant.
            CREATE TABLE IF NOT EXISTS chat_sessions (
                participant_id TEXT NOT NULL,
                chat_id        TEXT NOT NULL,
                messages_json  TEXT NOT NULL,
                updated_at     INTEGER NOT NULL,
                PRIMARY KEY (participant_id, chat_id)
            );
            """
        )
        # Migration for pre-existing databases: add code_changed if missing.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(participants)")]
        if "code_changed" not in cols:
            conn.execute(
                "ALTER TABLE participants ADD COLUMN code_changed INTEGER NOT NULL DEFAULT 0"
            )


# --- key/value ---------------------------------------------------------------

MAX_SAVED_CHATS = 2


def get_saved_chats(participant_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT chat_id, messages_json, updated_at FROM chat_sessions "
            "WHERE participant_id = ? ORDER BY updated_at DESC LIMIT ?",
            (participant_id, MAX_SAVED_CHATS),
        ).fetchall()
    out = []
    for r in rows:
        try:
            messages = json.loads(r["messages_json"])
        except ValueError:
            messages = []
        out.append({"id": r["chat_id"], "messages": messages, "updated_at": r["updated_at"]})
    return out


def save_saved_chats(participant_id: str, chats: list[dict]) -> None:
    """Replace a participant's saved chats with the given list (newest kept)."""
    ordered = sorted(chats, key=lambda c: c.get("updated_at", 0), reverse=True)[:MAX_SAVED_CHATS]
    with _connect() as conn:
        conn.execute("DELETE FROM chat_sessions WHERE participant_id = ?", (participant_id,))
        for c in ordered:
            conn.execute(
                "INSERT INTO chat_sessions (participant_id, chat_id, messages_json, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (participant_id, c["id"], json.dumps(c["messages"], ensure_ascii=False),
                 int(c.get("updated_at", 0))),
            )


def get_kv(key: str) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_kv(key: str, value: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# --- participants ------------------------------------------------------------

def get_participant_by_code(login_code: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM participants WHERE login_code = ?", (login_code,)
        ).fetchone()
        return dict(row) if row else None


def get_participant_by_id(participant_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM participants WHERE participant_id = ?", (participant_id,)
        ).fetchone()
        return dict(row) if row else None


def create_participant(
    participant_id: str, display_name: str, team_id: Optional[str], login_code: str
) -> dict:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO participants "
            "(participant_id, display_name, team_id, login_code, is_active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (participant_id, display_name, team_id, login_code, utcnow_iso()),
        )
    return get_participant_by_id(participant_id)  # type: ignore[return-value]


def set_active(participant_id: str, active: bool) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE participants SET is_active = ? WHERE participant_id = ?",
            (1 if active else 0, participant_id),
        )
        return cur.rowcount > 0


def reset_quota(participant_id: str) -> bool:
    """Mark 'now' as the quota reset point; requests before it stop counting."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE participants SET reset_at = ? WHERE participant_id = ?",
            (utcnow_iso(), participant_id),
        )
        return cur.rowcount > 0


def set_login_code(participant_id: str, code: str) -> bool:
    """Set a participant's login code and mark that they changed it themselves."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE participants SET login_code = ?, code_changed = 1 "
            "WHERE participant_id = ?",
            (code, participant_id),
        )
        return cur.rowcount > 0


def set_display_name(participant_id: str, name: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE participants SET display_name = ? WHERE participant_id = ?",
            (name, participant_id),
        )
        return cur.rowcount > 0


def reset_all_quotas() -> int:
    """Reset the contest quota window for every participant."""
    with _connect() as conn:
        cur = conn.execute("UPDATE participants SET reset_at = ?", (utcnow_iso(),))
        return cur.rowcount


def list_participants() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM participants ORDER BY participant_id"
        ).fetchall()
        return [dict(r) for r in rows]


def next_participant_index() -> int:
    """Highest numeric suffix of existing pNNN ids, plus one (1-based)."""
    with _connect() as conn:
        rows = conn.execute("SELECT participant_id FROM participants").fetchall()
    best = 0
    for r in rows:
        pid = r["participant_id"]
        if pid.startswith("p") and pid[1:].isdigit():
            best = max(best, int(pid[1:]))
    return best + 1


# --- chat logs ---------------------------------------------------------------

def insert_log(row: dict) -> None:
    cols = (
        "request_id", "timestamp", "participant_id", "team_id", "model_used",
        "enforced_max_tokens", "input_character_count", "messages_json",
        "response_text", "provider_status_code", "provider_error", "duration_ms",
        "prompt_tokens", "completion_tokens", "total_tokens",
    )
    placeholders = ", ".join("?" for _ in cols)
    with _connect() as conn:
        conn.execute(
            f"INSERT INTO chat_logs ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(row.get(c) for c in cols),
        )


def delete_logs_for(participant_id: str) -> int:
    """Permanently remove all chat logs for a participant (clears their stats)."""
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM chat_logs WHERE participant_id = ?", (participant_id,)
        )
        return cur.rowcount


def count_requests(participant_id: str) -> int:
    """Requests counted against the contest quota (after any reset point)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM chat_logs c "
            "JOIN participants p ON p.participant_id = c.participant_id "
            "WHERE c.participant_id = ? "
            "AND (p.reset_at IS NULL OR c.timestamp >= p.reset_at)",
            (participant_id,),
        ).fetchone()
        return int(row["n"])


def iter_logs() -> Iterator[dict]:
    with _connect() as conn:
        for row in conn.execute("SELECT * FROM chat_logs ORDER BY timestamp"):
            yield dict(row)


def get_logs_for(participant_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT request_id, timestamp, messages_json, response_text, "
            "provider_status_code, provider_error, duration_ms, "
            "prompt_tokens, completion_tokens, total_tokens "
            "FROM chat_logs WHERE participant_id = ? ORDER BY timestamp",
            (participant_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def usage_rows() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT participant_id, "
            "COUNT(*) AS requests, "
            "COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens, "
            "COALESCE(SUM(completion_tokens), 0) AS completion_tokens, "
            "COALESCE(SUM(total_tokens), 0) AS total_tokens "
            "FROM chat_logs GROUP BY participant_id ORDER BY participant_id"
        ).fetchall()
        return [dict(r) for r in rows]
