from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None or not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except Exception:
        return default


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key, "")
    if not val:
        return default
    return val.strip().lower() not in {"0", "false", "no", "", "off"}


class DataSourceConfig:
    """集中管理所有外部数据源配置。

    优先级：环境变量 > .env.local > settings.yml > 代码默认值
    """

    _instance: DataSourceConfig | None = None

    def __new__(cls) -> DataSourceConfig:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        root = _project_root()
        self._settings = _load_yaml(root / "repo" / "etl" / "config" / "settings.yml")
        self._load_env_file(root / ".env.local")

    def _load_env_file(self, path: Path) -> None:
        if not path.exists():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and value and key not in os.environ:
                os.environ[key] = value
        # Snowball token 别名同步
        if "XUEQIUTOKEN" not in os.environ and "SNOWBALL_TOKEN" in os.environ:
            os.environ["XUEQIUTOKEN"] = os.environ["SNOWBALL_TOKEN"]
        if "SNOWBALL_TOKEN" not in os.environ and "XUEQIUTOKEN" in os.environ:
            os.environ["SNOWBALL_TOKEN"] = os.environ["XUEQIUTOKEN"]

    # ---------- 数据库 / 缓存 ----------
    @property
    def database_url(self) -> str:
        postgres = self._settings.get("postgres") or {}
        return _env("DATABASE_URL", postgres.get("url", "postgresql+psycopg2://user:pass@localhost:5432/quantpulse"))

    @property
    def redis_url(self) -> str:
        redis = self._settings.get("redis") or {}
        return _env("REDIS_URL", redis.get("url", "redis://localhost:6379/0"))

    @property
    def db_pool_size(self) -> int:
        postgres = self._settings.get("postgres") or {}
        return _env_int("DB_POOL_SIZE", int(postgres.get("pool_size", 5)))

    @property
    def db_max_overflow(self) -> int:
        postgres = self._settings.get("postgres") or {}
        return _env_int("DB_MAX_OVERFLOW", int(postgres.get("max_overflow", 5)))

    # ---------- Snowball ----------
    @property
    def snowball_token(self) -> str:
        for key in ("XUEQIUTOKEN", "SNOWBALL_TOKEN", "XQ_A_TOKEN", "SNOWBALL_A_TOKEN"):
            val = _env(key, "")
            if val:
                return val
        return ""

    @property
    def snowball_user_id(self) -> str:
        for key in ("XUEQIU_U", "XUEQIU_UID", "SNOWBALL_U"):
            val = _env(key, "")
            if val:
                return val
        return ""

    @property
    def snowball_enabled(self) -> bool:
        return bool(self.snowball_token)

    # ---------- LLM ----------
    @property
    def llm_enabled(self) -> bool:
        return _env_bool("LLM_ENABLED", False)

    @property
    def llm_provider(self) -> str:
        return _env("LLM_PROVIDER", "openai")

    @property
    def llm_model(self) -> str:
        return _env("LLM_MODEL", "gpt-4o-mini")

    @property
    def llm_api_key(self) -> str | None:
        return _env("LLM_API_KEY", "") or None

    @property
    def llm_base_url(self) -> str | None:
        return _env("LLM_BASE_URL", "") or None

    @property
    def llm_timeout_seconds(self) -> int:
        return _env_int("LLM_TIMEOUT_SECONDS", 20)

    # ---------- RSS / News ----------
    @property
    def rss_timeout_seconds(self) -> int:
        return _env_int("RSS_TIMEOUT_SECONDS", 12)

    @property
    def rss_max_workers(self) -> int:
        return _env_int("RSS_MAX_WORKERS", 12)

    @property
    def rss_retry_count(self) -> int:
        return _env_int("RSS_RETRY_COUNT", 2)

    @property
    def rss_retry_backoff_seconds(self) -> float:
        return _env_float("RSS_RETRY_BACKOFF_SECONDS", 1.5)

    @property
    def rss_user_agent(self) -> str:
        return _env(
            "RSS_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )

    @property
    def rss_proxy(self) -> str:
        return _env("RSS_PROXY", "")

    @property
    def rss_http_proxy(self) -> str:
        return _env("RSS_HTTP_PROXY", "")

    @property
    def rss_https_proxy(self) -> str:
        return _env("RSS_HTTPS_PROXY", "")

    @property
    def rss_cache_ttl_seconds(self) -> int:
        return _env_int("RSS_CACHE_TTL", 1800)

    # ---------- SHFE ----------
    @property
    def shfe_base_url(self) -> str:
        return _env("SHFE_BASE_URL", "https://www.shfe.com.cn").rstrip("/")

    @property
    def shfe_timeout_seconds(self) -> int:
        return _env_int("SHFE_TIMEOUT_SECONDS", 20)

    @property
    def shfe_user_agent(self) -> str:
        return _env(
            "SHFE_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )

    # ---------- BaoStock ----------
    @property
    def baostock_industry_cooldown_seconds(self) -> int:
        return _env_int("BAOSTOCK_INDUSTRY_FAILURE_COOLDOWN_SECONDS", 900)

    # ---------- AkShare ----------
    @property
    def akshare_hk_spot_cache_seconds(self) -> int:
        return max(3, _env_int("AKSHARE_HK_SPOT_CACHE_SECONDS", 60))

    @property
    def akshare_a_margin_cache_seconds(self) -> int:
        return max(60, _env_int("AKSHARE_A_MARGIN_CACHE_SECONDS", 3600))

    @property
    def akshare_a_margin_lookback_days(self) -> int:
        return max(0, _env_int("AKSHARE_A_MARGIN_LOOKBACK_DAYS", 10))

    # ---------- HK Kline ----------
    @property
    def hk_kline_curl_fallback_enabled(self) -> bool:
        return _env_bool("HK_KLINE_CURL_FALLBACK_ENABLED", True)

    @property
    def hk_kline_curl_timeout_seconds(self) -> int:
        return max(5, _env_int("HK_KLINE_CURL_TIMEOUT_SECONDS", 20))

    # ---------- 全局 HTTP ----------
    @property
    def http_timeout_seconds(self) -> int:
        return _env_int("HTTP_TIMEOUT_SECONDS", 20)

    @property
    def http_retry_count(self) -> int:
        return _env_int("HTTP_RETRY_COUNT", 3)

    @property
    def http_retry_backoff_seconds(self) -> float:
        return _env_float("HTTP_RETRY_BACKOFF_SECONDS", 1.5)

    @property
    def http_user_agent(self) -> str:
        return _env(
            "HTTP_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )


# 全局单例
datasource_config = DataSourceConfig()
