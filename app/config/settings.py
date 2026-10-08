"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    ai_provider: str = "gemini"

    request_timeout_seconds: float = 30.0
    max_question_chars: int = 4000
    max_history_turns: int = 10
    max_history_text_chars: int = 2000

    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def has_api_key(self) -> bool:
        key = self.gemini_api_key.get_secret_value() if self.gemini_api_key else ""
        return bool(key.strip()) and key.strip() != "your_key_here"


@lru_cache
def get_settings() -> Settings:
    return Settings()
