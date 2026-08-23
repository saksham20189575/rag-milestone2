"""Thin wrapper around the Groq SDK for LLM calls."""

from __future__ import annotations

import re
import time

from groq import Groq, NotFoundError, RateLimitError

from src.config.settings import Settings, get_settings
from src.generation.rate_limiter import (
    GroqRateLimitExceeded,
    estimate_tokens,
    get_primary_rate_limiter,
)

_REASONING_BLOCK = re.compile(
    r"<think(?:ing)?>.*?</think(?:ing)?>"
    r"|<think>.*?</think>",
    re.DOTALL | re.IGNORECASE,
)
_GPT_OSS_MIN_TOKENS = 64
_QWEN_MIN_TOKENS = 512


def clean_model_output(text: str) -> str:
    """Strip reasoning/thinking blocks returned by Groq reasoning models."""
    cleaned = _REASONING_BLOCK.sub("", text)
    return cleaned.strip()


def effective_max_tokens(model: str, max_tokens: int) -> int:
    """Reasoning models need higher limits so visible output is not truncated."""
    lowered = model.lower()
    if "qwen" in lowered:
        return max(max_tokens, _QWEN_MIN_TOKENS)
    if "gpt-oss" in lowered:
        return max(max_tokens, _GPT_OSS_MIN_TOKENS)
    return max_tokens


def is_primary_model(model: str, settings: Settings) -> bool:
    return model == settings.groq_model


class GroqClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Groq | None = None

    @property
    def client(self) -> Groq:
        if self._client is None:
            if not self.settings.groq_api_key:
                raise ValueError("GROQ_API_KEY is not set")
            self._client = Groq(api_key=self.settings.groq_api_key)
        return self._client

    def _create_completion(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, int]:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except NotFoundError as exc:
            raise ValueError(
                f"Groq model '{model}' is unavailable. "
                f"Check GROQ_MODEL / GROQ_MODEL_FAST in .env against "
                f"https://console.groq.com/docs/models"
            ) from exc

        raw = response.choices[0].message.content or ""
        usage = response.usage
        total_tokens = usage.total_tokens if usage else estimate_tokens(
            system, user, max_output_tokens=max_tokens
        )
        return clean_model_output(raw), total_tokens

    def chat(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        resolved_model = model or self.settings.groq_model
        resolved_temperature = (
            temperature if temperature is not None else self.settings.groq_temperature
        )
        resolved_max_tokens = effective_max_tokens(
            resolved_model,
            max_tokens or self.settings.groq_max_tokens,
        )
        primary_call = is_primary_model(resolved_model, self.settings)
        limiter = get_primary_rate_limiter(self.settings) if primary_call else None

        token_estimate = estimate_tokens(system, user, max_output_tokens=resolved_max_tokens)
        if limiter is not None:
            limiter.wait_for_capacity(token_estimate)

        try:
            text, total_tokens = self._create_completion(
                system=system,
                user=user,
                model=resolved_model,
                temperature=resolved_temperature,
                max_tokens=resolved_max_tokens,
            )
        except RateLimitError:
            retry_after = 2.0
            if primary_call and limiter is not None:
                limiter.wait_for_capacity(token_estimate)
            else:
                time.sleep(retry_after)
            try:
                text, total_tokens = self._create_completion(
                    system=system,
                    user=user,
                    model=resolved_model,
                    temperature=resolved_temperature,
                    max_tokens=resolved_max_tokens,
                )
            except RateLimitError as retry_exc:
                raise GroqRateLimitExceeded(
                    "Groq rate limit reached after retry.",
                    retry_after=retry_after,
                ) from retry_exc
        else:
            if limiter is not None:
                limiter.record(total_tokens)
            return text

        if limiter is not None:
            limiter.record(total_tokens)
        return text

    def check_connectivity(self) -> bool:
        """Verify Groq API connectivity with a minimal request."""
        try:
            reply = self.chat(
                system="You are a connectivity check.",
                user="Reply with OK.",
                model=self.settings.groq_model_fast,
                max_tokens=32,
            )
            return bool(reply)
        except Exception:
            return False

    def primary_usage_snapshot(self) -> dict[str, int]:
        return get_primary_rate_limiter(self.settings).snapshot()
