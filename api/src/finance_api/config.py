"""Application settings, loaded from environment variables (and `api/.env` in local dev)."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed config. Each field maps to an env var of the same name, case-insensitive.

    Fields without a default are required: the app refuses to start if they're missing,
    instead of failing later in the middle of a chat request.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SecretStr hides the value in reprs and logs ("**********"). Call
    # .get_secret_value() only at the point where the key is actually sent.
    google_generative_ai_api_key: SecretStr
    alpha_vantage_api_key: SecretStr

    # Matches the redis service in docker-compose.yml.
    redis_url: str = "redis://localhost:6379/0"

    gemini_model: str = "gemini-3.6-flash"
    # Max model calls per chat request (tool rounds + the final answer), the same cap as
    # the web app's `stopWhen: isStepCount(5)`. Keeps a looping model from burning
    # Alpha Vantage's daily quota.
    max_steps: int = 5
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Build Settings once and reuse them. Tests clear the cache to swap in new values."""
    return Settings()
