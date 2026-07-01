"""Per-participant rate limiting.

In-memory sliding windows for requests-per-minute and requests-per-hour (valid
for a single backend worker). The total per-contest quota is *persisted* — it is
derived from ``chat_logs`` so it survives restarts. Limits key on
``participant_id``, never IP, since students may share a network.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

from . import database
from .config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._rpm: dict[str, deque[float]] = defaultdict(deque)
        self._rph: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def _prune(window: deque[float], now: float, span: float) -> None:
        while window and now - window[0] > span:
            window.popleft()

    def check_quota(self, participant_id: str) -> None:
        """Raise 403 if the contest-wide request quota is exhausted."""
        limit = get_settings().TOTAL_REQUESTS_PER_PARTICIPANT
        if database.count_requests(participant_id) >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Contest request quota exhausted. Please contact an organizer.",
            )

    def check_rate(self, participant_id: str) -> None:
        """Raise 429 if RPH or RPM is exceeded; otherwise record the request."""
        s = get_settings()
        now = time.monotonic()

        rph = self._rph[participant_id]
        self._prune(rph, now, 3600)
        if len(rph) >= s.RPH_PER_PARTICIPANT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Hourly request limit reached. Please wait before sending more.",
            )

        rpm = self._rpm[participant_id]
        self._prune(rpm, now, 60)
        if len(rpm) >= s.RPM_PER_PARTICIPANT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait before sending another message.",
            )

        rph.append(now)
        rpm.append(now)

    def remaining_quota(self, participant_id: str) -> int:
        limit = get_settings().TOTAL_REQUESTS_PER_PARTICIPANT
        return max(0, limit - database.count_requests(participant_id))


rate_limiter = RateLimiter()
