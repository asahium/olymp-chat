"""Server-side request logging and admin exports."""
import csv
import json
from typing import TextIO

from . import database

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
    per_participant = database.usage_rows()
    totals = {
        "requests": sum(r["requests"] for r in per_participant),
        "prompt_tokens": sum(r["prompt_tokens"] for r in per_participant),
        "completion_tokens": sum(r["completion_tokens"] for r in per_participant),
        "total_tokens": sum(r["total_tokens"] for r in per_participant),
    }
    return {"per_participant": per_participant, "totals": totals}
