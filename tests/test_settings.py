# tests/test_settings.py
from config.settings import get_settings


def test_llm_timeout_default():
    get_settings.cache_clear()
    s = get_settings()
    assert s.llm_timeout_seconds == 60
    assert s.llm_max_retries == 3
    assert s.llm_retry_base_delay == 1.0
    assert s.conversation_history_turns == 6
