"""Server-side request logging and admin exports."""
import csv
import json
from typing import TextIO

from . import database
from .config import get_settings

_EXPORT_FIELDS = [
    "request_id", "timestamp", "participant_id", "team_id", "model_used",
    "enforced_max_tokens", "input_character_count", "messages_json",
    "response_text", "provider_status_code", "provider_error", "duration_ms",
    "prompt_tokens", "completion_tokens", "total_tokens",
]


def log_request(row: dict) -> None:
    database.insert_log(row)


def export_jsonl(fp: TextIO) -> int:
    n = 0
    for row in database.iter_logs():
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")
        n += 1
    return n


def export_csv(fp: TextIO) -> int:
    writer = csv.DictWriter(fp, fieldnames=_EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    n = 0
    for row in database.iter_logs():
        writer.writerow(row)
        n += 1
    return n


def usage_summary() -> dict:
    """Per-participant usage merged with names, computed cost, and remaining quota.

    Includes participants with zero usage. Sorted by cost, highest first.
    """
    s = get_settings()
    usage = {r["participant_id"]: r for r in database.usage_rows()}
    per_participant: list[dict] = []
    totals = {
        "requests": 0, "prompt_tokens": 0, "completion_tokens": 0,
        "total_tokens": 0, "cost": 0.0,
    }

    for p in database.list_participants():
        pid = p["participant_id"]
        u = usage.get(pid, {"requests": 0, "prompt_tokens": 0,
                            "completion_tokens": 0, "total_tokens": 0})
        cost = (u["prompt_tokens"] / 1e6 * s.PRICE_PROMPT_PER_1M
                + u["completion_tokens"] / 1e6 * s.PRICE_COMPLETION_PER_1M)
        # Lifetime stats (requests/tokens/cost) count ALL logs and are preserved
        # across a quota reset. quota_used counts only the current quota window.
        quota_limit = s.TOTAL_REQUESTS_PER_PARTICIPANT
        quota_used = database.count_requests(pid)
        remaining = max(0, quota_limit - quota_used)
        per_participant.append({
            "participant_id": pid,
            "display_name": p["display_name"],
            "team_id": p["team_id"],
            "login_code": p["login_code"],
            "is_active": bool(p["is_active"]),
            "code_changed": bool(p["code_changed"]),
            "requests": u["requests"],
            "prompt_tokens": u["prompt_tokens"],
            "completion_tokens": u["completion_tokens"],
            "total_tokens": u["total_tokens"],
            "cost": round(cost, 6),
            "quota_used": quota_used,
            "quota_limit": quota_limit,
            "remaining_requests": remaining,
        })
        for k in ("requests", "prompt_tokens", "completion_tokens", "total_tokens"):
            totals[k] += u[k]
        totals["cost"] += cost

    totals["cost"] = round(totals["cost"], 6)
    per_participant.sort(key=lambda r: r["cost"], reverse=True)
    return {
        "per_participant": per_participant,
        "totals": totals,
        "prices": {
            "prompt_per_1m": s.PRICE_PROMPT_PER_1M,
            "completion_per_1m": s.PRICE_COMPLETION_PER_1M,
        },
        "model": s.OPENROUTER_MODEL,
    }
