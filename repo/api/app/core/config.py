from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "KiloQuant API"
    database_url: str = "postgresql+psycopg2://user:pass@localhost:5432/kiloquant"
    redis_url: str = "redis://localhost:6379/0"
    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
