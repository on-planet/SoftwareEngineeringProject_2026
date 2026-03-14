from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def _load_etl_defaults() -> dict:
    if yaml is None:
        return {}
    config_path = Path(__file__).resolve().parents[3] / "etl" / "config" / "settings.yml"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}
    except Exception:
        return {}


_ETL_DEFAULTS = _load_etl_defaults()


def _default_database_url() -> str:
    postgres = _ETL_DEFAULTS.get("postgres") or {}
    return postgres.get("url") or "postgresql+psycopg2://user:pass@localhost:5432/kiloquant"


def _default_redis_url() -> str:
    redis = _ETL_DEFAULTS.get("redis") or {}
    return redis.get("url") or "redis://localhost:6379/0"


def _default_pool_size() -> int:
    postgres = _ETL_DEFAULTS.get("postgres") or {}
    return int(postgres.get("pool_size") or 5)


def _default_max_overflow() -> int:
    postgres = _ETL_DEFAULTS.get("postgres") or {}
    return int(postgres.get("max_overflow") or 5)


class Settings(BaseSettings):
    app_name: str = "KiloQuant API"
    database_url: str = _default_database_url()
    redis_url: str = _default_redis_url()
    db_pool_size: int = _default_pool_size()
    db_max_overflow: int = _default_max_overflow()
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
