"""
LLM service: OpenRouter client, streaming, retry+backoff, token capture.
"""
from __future__ import annotations

import random
import time
from typing import Generator, Optional

import openai

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

# Cost per 1M tokens (prompt + completion combined)
MODEL_PRICES = {
    "meta-llama/llama-3.2-3b-instruct:free": 0.0,
    "meta-llama/llama-3.3-70b-instruct:free": 0.0,
    "meta-llama/llama-3.1-8b-instruct:free": 0.0,
    "mistralai/mistral-7b-instruct:free": 0.0,
    "google/gemma-2-9b-it:free": 0.0,
    "google/gemini-2.0-flash-exp:free": 0.0,
    "google/gemini-2.0-flash": 0.10,
    "openai/gpt-4o-mini": 0.15,
    "openai/gpt-4o": 5.00,
}


class LLMUnavailableError(Exception):
    """Raised when all retry attempts and fallback tiers are exhausted."""


def estimate_cost(model_id: str, tokens_in: int, tokens_out: int) -> float:
    price_per_1m = MODEL_PRICES.get(model_id, 0.50)
    return (tokens_in + tokens_out) * price_per_1m / 1_000_000


def get_openrouter_client() -> openai.OpenAI:
    s = get_settings()
    return openai.OpenAI(
        base_url=s.openrouter_base_url,
        api_key=s.openrouter_api_key,
        default_headers={
            "HTTP-Referer": s.openrouter_http_referer,
            "X-Title": s.openrouter_x_title,
        },
        timeout=s.llm_timeout_seconds,
    )


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, openai.APIStatusError):
        # 429 = rate limited (retry with backoff), 5xx = server error (retry)
        return exc.status_code == 429 or exc.status_code >= 500
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
        return True
    return False


def call_llm(
    messages: list,
    model_id: str,
) -> tuple:
    """
    Non-streaming LLM call with retry + backoff.
    Returns (answer, tokens_in, tokens_out, cost_usd).
    Raises LLMUnavailableError after all retries exhausted.
    """
    s = get_settings()
    client = get_openrouter_client()
    last_exc = None

    for attempt in range(s.llm_max_retries):
        if attempt > 0:
            delay = s.llm_retry_base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.warning("llm_retry", attempt=attempt, model=model_id, delay=round(delay, 2))
            time.sleep(delay)
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                stream=False,
            )
            answer = response.choices[0].message.content or ""
            tokens_in = response.usage.prompt_tokens if response.usage else 0
            tokens_out = response.usage.completion_tokens if response.usage else 0
            cost = estimate_cost(model_id, tokens_in, tokens_out)
            logger.info("llm_success", model=model_id, tokens_in=tokens_in, tokens_out=tokens_out)
            return answer, tokens_in, tokens_out, cost
        except Exception as exc:
            last_exc = exc
            if not _should_retry(exc):
                break
            logger.warning("llm_attempt_failed", attempt=attempt, model=model_id, error=str(exc))

    raise LLMUnavailableError(f"LLM call failed after {s.llm_max_retries} attempts: {last_exc}") from last_exc


def stream_llm(
    messages: list,
    model_id: str,
) -> Generator:
    """
    Streaming LLM call. Yields token strings one at a time.
    """
    s = get_settings()
    client = get_openrouter_client()
    last_exc = None

    for attempt in range(s.llm_max_retries):
        if attempt > 0:
            delay = s.llm_retry_base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)
        try:
            with client.chat.completions.create(
                model=model_id,
                messages=messages,
                stream=True,
            ) as stream:
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    yield delta
                return
        except Exception as exc:
            last_exc = exc
            if not _should_retry(exc):
                break

    raise LLMUnavailableError(f"Streaming LLM failed: {last_exc}") from last_exc
