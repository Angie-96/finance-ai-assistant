import pytest
from pydantic import ValidationError

from finance_api.config import Settings


def test_missing_api_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY")

    with pytest.raises(ValidationError, match="alpha_vantage_api_key"):
        Settings(_env_file=None)


def test_secrets_are_hidden_in_repr() -> None:
    settings = Settings(_env_file=None)

    assert "test-av-key" not in repr(settings)
    assert settings.alpha_vantage_api_key.get_secret_value() == "test-av-key"
