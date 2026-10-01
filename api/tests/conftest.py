from collections.abc import Iterator

import pytest

from finance_api.config import get_settings


@pytest.fixture(autouse=True)
def settings_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Give every test fake API keys, so no test can reach a real API with real ones.

    `monkeypatch` undoes the env changes after each test, and clearing the cache makes
    get_settings() re-read them.
    """
    monkeypatch.setenv("GOOGLE_GENERATIVE_AI_API_KEY", "test-google-key")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-av-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
