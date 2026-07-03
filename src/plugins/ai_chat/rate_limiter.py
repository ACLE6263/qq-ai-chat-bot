"""Token-bucket rate limiter — per-user and per-group limits."""

import time
from collections import defaultdict

from src.config import config


class RateLimiter:
    """Simple sliding-window rate limiter.

    Tracks timestamps of requests per identifier (user or group).
    Requests are allowed only if fewer than `limit` requests have
    been made in the last `window` seconds.
    """

    def __init__(self) -> None:
        # identifier -> list of timestamps
        self._user_records: defaultdict = defaultdict(list)
        self._group_records: defaultdict = defaultdict(list)

        self.user_limit: int = config.rate_limit_per_user
        self.group_limit: int = config.rate_limit_per_group
        self.window: int = config.rate_limit_window

    def check(self, identifier: str, *, is_group: bool = False) -> bool:
        """Check if a request is allowed. Returns True if allowed."""
        now = time.time()
        window_start = now - self.window

        records = (
            self._group_records[identifier]
            if is_group
            else self._user_records[identifier]
        )
        limit = self.group_limit if is_group else self.user_limit

        # Prune expired timestamps
        while records and records[0] < window_start:
            records.pop(0)

        if len(records) >= limit:
            return False

        records.append(now)
        return True

    def get_remaining(self, identifier: str, *, is_group: bool = False) -> int:
        """Return remaining requests allowed in the current window."""
        now = time.time()
        window_start = now - self.window

        records = (
            self._group_records[identifier]
            if is_group
            else self._user_records[identifier]
        )
        limit = self.group_limit if is_group else self.user_limit

        while records and records[0] < window_start:
            records.pop(0)

        return max(0, limit - len(records))

    def reset(self, identifier: str) -> None:
        """Clear rate limit records for an identifier."""
        self._user_records.pop(identifier, None)
        self._group_records.pop(identifier, None)


# Module-level singleton
rate_limiter = RateLimiter()
