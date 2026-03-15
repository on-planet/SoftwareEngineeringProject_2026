from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen
import json
import os
import time
import xml.etree.ElementTree as ET

from etl.fetchers.snowball_client import normalize_symbol, to_snowball_symbol
from etl.loaders.redis_cache import get_cache_string
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)
CACHE_DIR = Path(__file__).resolve().parents[1] / "state" / "rss_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = int(os.getenv("RSS_CACHE_TTL", "1800"))
RSS_TIMEOUT_SECONDS = int(os.getenv("RSS_TIMEOUT_SECONDS", "12"))
RSS_MAX_WORKERS = int(os.getenv("RSS_MAX_WORKERS", "12"))
RSS_RETRY_COUNT = int(os.getenv("RSS_RETRY_COUNT", "2"))
RSS_RETRY_BACKOFF_SECONDS = float(os.getenv("RSS_RETRY_BACKOFF_SECONDS", "1.5"))
RSS_USER_AGENT = os.getenv(
    "RSS_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)
RSS_PROXY = os.getenv("RSS_PROXY", "").strip()
RSS_HTTP_PROXY = os.getenv("RSS_HTTP_PROXY", "").strip()
RSS_HTTPS_PROXY = os.getenv("RSS_HTTPS_PROXY", "").strip()
RSS_NO_PROXY = {
    item.strip().lower()
    for item in os.getenv("RSS_NO_PROXY", "").split(",")
    if item.strip()
}
RSS_DISABLE_ENV_PROXY = os.getenv("RSS_DISABLE_ENV_PROXY", "0").strip().lower() in {"1", "true", "yes", "on"}


def _rsshub_base() -> str:
    base = os.getenv("RSSHUB_BASE")
    if base:
        return base.rstrip("/")
    return "https://rsshub.liumingye.cn"


def _rss_symbols() -> list[str]:
    raw = os.getenv("SNOWBALL_RSS_SYMBOLS", "").strip() or os.getenv("SNOWBALL_STOCK_SYMBOLS", "").strip()
    if not raw:
        return []
    output: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        symbol = normalize_symbol(item.strip())
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        output.append(symbol)
    return output


def _rsshub_xueqiu_news(symbol: str) -> str:
    return f"{_rsshub_base()}/xueqiu/stock_info/{to_snowball_symbol(symbol)}/news"


def _rsshub_cls_telegraph() -> str:
    override = os.getenv("CLS_TELEGRAPH_RSS", "").strip()
    if override:
        return override
    return "https://pyrsshub.vercel.app/cls/telegraph"


def _cache_key(url: str) -> str:
    safe = url.replace("/", "_").replace(":", "_").replace("?", "_").replace("&", "_")
    return f"{safe}.json"


def _load_cache(url: str) -> List[dict] | None:
    path = CACHE_DIR / _cache_key(url)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    ts = payload.get("ts")
    items = payload.get("items")
    if not isinstance(ts, (int, float)) or not isinstance(items, list):
        return None
    if time.time() - ts > CACHE_TTL_SECONDS:
        return None
    output = []
    for item in items:
        published_at = item.get("published_at")
        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at)
            except Exception:
                published_at = None
        output.append(
            {
                "title": item.get("title") or "",
                "link": item.get("link") or "",
                "published_at": published_at,
            }
        )
    return output


def _save_cache(url: str, items: List[dict]) -> None:
    path = CACHE_DIR / _cache_key(url)
    payload = {
        "ts": time.time(),
        "items": [
            {
                "title": item.get("title") or "",
                "link": item.get("link") or "",
                "published_at": item.get("published_at").isoformat()
                if item.get("published_at")
                else None,
            }
            for item in items
        ],
    }
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        LOGGER.warning("write rss cache failed [%s]: %s", url, exc)


def _parse_pub_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _build_proxy_map() -> dict[str, str]:
    if RSS_PROXY:
        return {"http": RSS_PROXY, "https": RSS_PROXY}
    proxies: dict[str, str] = {}
    if RSS_HTTP_PROXY:
        proxies["http"] = RSS_HTTP_PROXY
    if RSS_HTTPS_PROXY:
        proxies["https"] = RSS_HTTPS_PROXY
    return proxies


def _should_bypass_proxy(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    return any(host == item or host.endswith(f".{item}") for item in RSS_NO_PROXY)


def _build_request(url: str) -> Request:
    return Request(
        url,
        headers={
            "User-Agent": RSS_USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )


def _open_url(url: str):
    request = _build_request(url)
    if _should_bypass_proxy(url):
        return build_opener(ProxyHandler({})).open(request, timeout=RSS_TIMEOUT_SECONDS)
    proxies = _build_proxy_map()
    if proxies:
        return build_opener(ProxyHandler(proxies)).open(request, timeout=RSS_TIMEOUT_SECONDS)
    if RSS_DISABLE_ENV_PROXY:
        return build_opener(ProxyHandler({})).open(request, timeout=RSS_TIMEOUT_SECONDS)
    return urlopen(request, timeout=RSS_TIMEOUT_SECONDS)


def _should_retry_http(exc: HTTPError) -> bool:
    return exc.code == 429 or 500 <= exc.code < 600


def _sleep_before_retry(attempt: int) -> None:
    delay = RSS_RETRY_BACKOFF_SECONDS * (2 ** max(0, attempt - 1))
    time.sleep(delay)


def _download_rss(url: str) -> bytes | None:
    for attempt in range(RSS_RETRY_COUNT + 1):
        try:
            with _open_url(url) as resp:
                return resp.read()
        except HTTPError as exc:
            LOGGER.warning("fetch rss failed [%s]: %s", url, exc)
            if attempt >= RSS_RETRY_COUNT or not _should_retry_http(exc):
                return None
        except (URLError, TimeoutError) as exc:
            LOGGER.warning("fetch rss failed [%s]: %s", url, exc)
            if attempt >= RSS_RETRY_COUNT:
                return None
        except Exception as exc:
            LOGGER.warning("fetch rss failed [%s]: %s", url, exc)
            return None
        _sleep_before_retry(attempt + 1)
    return None


def _fetch_rss(url: str) -> List[dict]:
    cached = _load_cache(url)
    if cached is not None:
        return cached
    data = _download_rss(url)
    if data is None:
        return []
    try:
        root = ET.fromstring(data)
    except Exception as exc:
        LOGGER.warning("parse rss failed [%s]: %s", url, exc)
        return []

    items: list[dict] = []
    for item in root.findall(".//item"):
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "published_at": _parse_pub_date(item.findtext("pubDate") or ""),
            }
        )
    _save_cache(url, items)
    return items


def _fetch_rss_batch(urls: Iterable[str], max_workers: int | None = None) -> dict[str, List[dict]]:
    results: dict[str, List[dict]] = {}
    url_list = [u for u in urls if u]
    if not url_list:
        return results
    workers = max(1, min(max_workers or RSS_MAX_WORKERS, len(url_list)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(_fetch_rss, url): url for url in url_list}
        for future in as_completed(future_map):
            url = future_map[future]
            try:
                results[url] = future.result()
            except Exception as exc:
                LOGGER.warning("fetch rss failed [%s]: %s", url, exc)
                results[url] = []
    return results


def _append_rows(rows: List[dict], symbol: str, items: list[dict], as_of: date, source: str) -> None:
    for item in items:
        published_at = item.get("published_at")
        if not published_at:
            continue
        if published_at.date() != as_of:
            continue
        rows.append(
            {
                "symbol": symbol,
                "title": item.get("title") or "",
                "sentiment": "neutral",
                "published_at": published_at,
                "link": item.get("link") or "",
                "source": source,
            }
        )


def _dedupe_rows(rows: List[dict]) -> List[dict]:
    seen: set[tuple[str, str, str]] = set()
    output: List[dict] = []
    for row in rows:
        key = (
            str(row.get("symbol") or ""),
            str(row.get("title") or ""),
            str(row.get("link") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def get_news(as_of: date) -> List[dict]:
    rows: List[dict] = []

    symbol_urls: dict[str, str] = {}
    for symbol in _rss_symbols():
        symbol_urls[symbol] = _rsshub_xueqiu_news(symbol)

    cls_telegraph_url = _rsshub_cls_telegraph()
    yahoo_urls = {
        "https://tw.stock.yahoo.com/rss?category=intl-markets": "Yahoo TW Intl Markets",
        "https://tw.stock.yahoo.com/rss?category=funds-news": "Yahoo TW Funds",
        "https://tw.stock.yahoo.com/rss?category=news": "Yahoo TW News",
        "https://tw.stock.yahoo.com/rss?category=tw-market": "Yahoo TW Market",
        "https://tw.stock.yahoo.com/rss?category=personal-finance": "Yahoo TW Personal Finance",
        "https://tw.stock.yahoo.com/rss?category=column": "Yahoo TW Column",
        "https://tw.stock.yahoo.com/rss?category=research": "Yahoo TW Research",
    }
    url_map = {
        **{url: symbol for symbol, url in symbol_urls.items()},
        cls_telegraph_url: "CLS_TELEGRAPH",
        **{url: f"YAHOO::{source}" for url, source in yahoo_urls.items()},
    }
    fetched = _fetch_rss_batch(url_map.keys())

    for symbol, url in symbol_urls.items():
        _append_rows(rows, symbol, fetched.get(url, []), as_of, "RSSHub Xueqiu News")
    _append_rows(rows, "ALL", fetched.get(cls_telegraph_url, []), as_of, "RSSHub CLS Telegraph")
    for url, source in yahoo_urls.items():
        _append_rows(rows, "ALL", fetched.get(url, []), as_of, source)

    # Optional: Redis-cached HK symbols as broad market feed targets.
    hk_symbols_raw = get_cache_string("hk_rss_symbols")
    if hk_symbols_raw:
        for item in hk_symbols_raw.split(","):
            symbol = normalize_symbol(item.strip())
            if symbol.endswith(".HK"):
                _append_rows(rows, symbol, fetched.get(symbol_urls.get(symbol, ""), []), as_of, "RSSHub Xueqiu News")

    return ensure_required(_dedupe_rows(rows), ["symbol", "title", "sentiment", "published_at"], "news.fetch")
