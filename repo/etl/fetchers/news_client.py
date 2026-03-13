from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable, List
from urllib.parse import urlencode
from urllib.request import urlopen
import json
import os
import time
import xml.etree.ElementTree as ET

from etl.loaders.redis_cache import get_cache_string
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)
CACHE_DIR = Path(__file__).resolve().parents[1] / "state" / "rss_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = int(os.getenv("RSS_CACHE_TTL", "1800"))


def _rss_symbols() -> list[str]:
    env = os.getenv("YAHOO_RSS_SYMBOLS")
    if env:
        return [item.strip() for item in env.split(",") if item.strip()]
    # 默认关注：上证综指/深证成指/恒生指数
    return ["000001.SS", "399001.SZ", "^HSI"]


def _rsshub_base() -> str:
    base = os.getenv("RSSHUB_BASE")
    if base:
        return base.rstrip("/")
    return "https://rsshub.friesport.ac.cn"


def _rsshub_hk_symbols() -> list[str]:
    raw = get_cache_string("hk_rss_symbols")
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _map_yahoo_symbol(symbol: str) -> str:
    if symbol.endswith(".SS"):
        return symbol.replace(".SS", ".SH")
    if symbol.endswith(".SZ"):
        return symbol
    return "ALL"


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
    LOGGER.info("rss cache hit: %s", url)
    # 恢复时间字段
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
        LOGGER.warning("write rss cache failed: %s", exc)


def _fetch_rss(url: str) -> List[dict]:
    cached = _load_cache(url)
    if cached is not None:
        return cached
    LOGGER.info("rss cache miss: %s", url)
    try:
        with urlopen(url, timeout=20) as resp:
            data = resp.read()
    except Exception as exc:
        LOGGER.warning("fetch rss failed: %s", exc)
        return []

    try:
        root = ET.fromstring(data)
    except Exception as exc:
        LOGGER.warning("parse rss failed: %s", exc)
        return []

    items = []
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        pub_date = _parse_pub_date(item.findtext("pubDate") or "")
        items.append({"title": title.strip(), "link": link.strip(), "published_at": pub_date})
    _save_cache(url, items)
    return items


def _fetch_rss_batch(urls: Iterable[str], max_workers: int = 8) -> dict[str, List[dict]]:
    results: dict[str, List[dict]] = {}
    url_list = [u for u in urls if u]
    if not url_list:
        return results
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_fetch_rss, url): url for url in url_list}
        for future in as_completed(future_map):
            url = future_map[future]
            try:
                results[url] = future.result()
            except Exception as exc:
                LOGGER.warning("fetch rss failed: %s", exc)
                results[url] = []
    return results


def _rsshub_cls_telegraph() -> str:
    return f"{_rsshub_base()}/cls/telegraph/"


def _rsshub_xueqiu_announcement(symbol: str) -> str:
    return f"{_rsshub_base()}/xueqiu/stock_info/{symbol}/announcement"


def get_news(as_of: date) -> List[dict]:
    """Fetch news for the given date from Yahoo Finance RSS, CLS Telegraph, and Xueqiu announcements."""
    rows: List[dict] = []

    yahoo_urls: dict[str, str] = {}
    for rss_symbol in _rss_symbols():
        query = urlencode({"s": rss_symbol, "region": "CN", "lang": "zh-CN"})
        yahoo_urls[rss_symbol] = f"https://feeds.finance.yahoo.com/rss/2.0/headline?{query}"

    cls_url = _rsshub_cls_telegraph()
    hk_symbols = _rsshub_hk_symbols()
    hk_urls = {symbol: _rsshub_xueqiu_announcement(symbol) for symbol in hk_symbols}

    url_map: dict[str, str] = {}
    url_map.update({url: symbol for symbol, url in yahoo_urls.items()})
    url_map[cls_url] = "CLS"
    url_map.update({url: symbol for symbol, url in hk_urls.items()})

    fetched = _fetch_rss_batch(url_map.keys())

    # Yahoo Finance RSS
    for rss_symbol, url in yahoo_urls.items():
        for item in fetched.get(url, []):
            published_at = item.get("published_at")
            if not published_at:
                continue
            if published_at.date() != as_of:
                continue
            rows.append(
                {
                    "symbol": _map_yahoo_symbol(rss_symbol),
                    "title": item.get("title") or "",
                    "sentiment": "neutral",
                    "published_at": published_at,
                }
            )

    # 财联社电报 RSSHub
    for item in fetched.get(cls_url, []):
        published_at = item.get("published_at")
        if not published_at:
            continue
        if published_at.date() != as_of:
            continue
        title = item.get("title") or ""
        rows.append(
            {
                "symbol": "ALL",
                "title": title,
                "sentiment": "neutral",
                "published_at": published_at,
            }
        )

    # 雪球港股公告 RSSHub（来自 Redis hk_rss_symbols）
    for hk_symbol, url in hk_urls.items():
        for item in fetched.get(url, []):
            published_at = item.get("published_at")
            if not published_at:
                continue
            if published_at.date() != as_of:
                continue
            title = item.get("title") or ""
            rows.append(
                {
                    "symbol": hk_symbol,
                    "title": title,
                    "sentiment": "neutral",
                    "published_at": published_at,
                }
            )

    return ensure_required(rows, ["symbol", "title", "sentiment", "published_at"], "news.fetch")
