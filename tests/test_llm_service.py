import os
import pytest


def test_llm_unavailable_error_importable():
    from core.llm_service import LLMUnavailableError
    assert issubclass(LLMUnavailableError, Exception)


def test_estimate_cost_free_model():
    from core.llm_service import estimate_cost
    cost = estimate_cost("meta-llama/llama-3.1-8b-instruct:free", 1000, 500)
    assert cost == 0.0


def test_estimate_cost_paid_model():
    from core.llm_service import estimate_cost
    cost = estimate_cost("openai/gpt-4o-mini", 1_000_000, 0)
    assert cost == pytest.approx(0.15, rel=0.01)


def test_get_client_not_none():
    from core.llm_service import get_openrouter_client
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    client = get_openrouter_client()
    assert client is not None
