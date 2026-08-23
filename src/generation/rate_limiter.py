"""Client-side rate limiting for Groq openai/gpt-oss-120b quotas."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from src.config.settings import Settings, get_settings


@dataclass(frozen=True)
class ModelRateLimits:
    rpm: int
    rpd: int
    tpm: int
    tpd: int


class GroqRateLimitExceeded(Exception):
    """Raised when a Groq call would exceed configured quotas."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def estimate_tokens(*parts: str, max_output_tokens: int) -> int:
    """Conservative token estimate when usage metadata is unavailable pre-call."""
    prompt_chars = sum(len(part) for part in parts)
    prompt_tokens = max(1, prompt_chars // 4)
    return prompt_tokens + max_output_tokens


class GroqRateLimiter:
    """Sliding-window limiter for requests and tokens (per minute + per day)."""

    def __init__(self, limits: ModelRateLimits, *, max_wait_seconds: float = 65.0) -> None:
        self.limits = limits
        self.max_wait_seconds = max_wait_seconds
        self._lock = threading.Lock()
        self._minute_requests: deque[float] = deque()
        self._minute_tokens: deque[tuple[float, int]] = deque()
        self._day_requests: deque[float] = deque()
        self._day_tokens: deque[tuple[float, int]] = deque()

    def _purge(self, now: float) -> None:
        minute_cutoff = now - 60.0
        day_cutoff = now - 86_400.0

        while self._minute_requests and self._minute_requests[0] <= minute_cutoff:
            self._minute_requests.popleft()
        while self._minute_tokens and self._minute_tokens[0][0] <= minute_cutoff:
            self._minute_tokens.popleft()
        while self._day_requests and self._day_requests[0] <= day_cutoff:
            self._day_requests.popleft()
        while self._day_tokens and self._day_tokens[0][0] <= day_cutoff:
            self._day_tokens.popleft()

    def _minute_token_total(self) -> int:
        return sum(tokens for _, tokens in self._minute_tokens)

    def _day_token_total(self) -> int:
        return sum(tokens for _, tokens in self._day_tokens)

    def _seconds_until_minute_capacity(self, estimated_tokens: int, now: float) -> float:
        waits: list[float] = [0.0]

        if len(self._minute_requests) >= self.limits.rpm:
            waits.append(max(0.0, 60.0 - (now - self._minute_requests[0])))

        minute_tokens = self._minute_token_total()
        if minute_tokens + estimated_tokens > self.limits.tpm and self._minute_tokens:
            waits.append(max(0.0, 60.0 - (now - self._minute_tokens[0][0])))

        return max(waits)

    def _daily_capacity_available(self, estimated_tokens: int) -> bool:
        if len(self._day_requests) + 1 > self.limits.rpd:
            return False
        if self._day_token_total() + estimated_tokens > self.limits.tpd:
            return False
        return True

    def wait_for_capacity(self, estimated_tokens: int) -> None:
        """Block until the next call fits minute quotas; raise when daily quota is exhausted."""
        deadline = time.monotonic() + self.max_wait_seconds

        while True:
            with self._lock:
                now = time.time()
                self._purge(now)

                if not self._daily_capacity_available(estimated_tokens):
                    raise GroqRateLimitExceeded(
                        "Daily Groq quota exhausted for the primary model. "
                        "Try again tomorrow or use the linked Groww scheme page."
                    )

                wait_seconds = self._seconds_until_minute_capacity(estimated_tokens, now)
                if wait_seconds <= 0:
                    return

            if time.monotonic() + wait_seconds > deadline:
                raise GroqRateLimitExceeded(
                    "Groq per-minute quota is saturated for the primary model.",
                    retry_after=wait_seconds,
                )

            time.sleep(min(wait_seconds, 1.0))

    def record(self, tokens: int) -> None:
        now = time.time()
        with self._lock:
            self._purge(now)
            self._minute_requests.append(now)
            self._minute_tokens.append((now, tokens))
            self._day_requests.append(now)
            self._day_tokens.append((now, tokens))

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            now = time.time()
            self._purge(now)
            return {
                "requests_last_minute": len(self._minute_requests),
                "tokens_last_minute": self._minute_token_total(),
                "requests_last_day": len(self._day_requests),
                "tokens_last_day": self._day_token_total(),
            }


_limiter: GroqRateLimiter | None = None
_limiter_lock = threading.Lock()


def get_primary_rate_limiter(settings: Settings | None = None) -> GroqRateLimiter:
    global _limiter
    settings = settings or get_settings()
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                _limiter = GroqRateLimiter(
                    ModelRateLimits(
                        rpm=settings.groq_rpm,
                        rpd=settings.groq_rpd,
                        tpm=settings.groq_tpm,
                        tpd=settings.groq_tpd,
                    ),
                    max_wait_seconds=settings.groq_rate_limit_max_wait,
                )
    return _limiter


def reset_primary_rate_limiter() -> None:
    """Reset the process-wide limiter (for tests)."""
    global _limiter
    with _limiter_lock:
        _limiter = None
