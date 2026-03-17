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
import re
import time
import xml.etree.ElementTree as ET

from etl.fetchers.snowball_client import normalize_symbol, to_snowball_symbol
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required
from etl.utils.stock_basics_cache import list_cached_symbols

LOGGER = get_logger(__name__)
CACHE_DIR = Path(__file__).resolve().parents[1] / "state" / "rss_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = int(os.getenv("RSS_CACHE_TTL", "1800"))
CACHE_STALE_ON_ERROR_SECONDS = int(os.getenv("RSS_CACHE_STALE_ON_ERROR_SECONDS", str(48 * 3600)))
RSS_TIMEOUT_SECONDS = int(os.getenv("RSS_TIMEOUT_SECONDS", "12"))
RSS_MAX_WORKERS = int(os.getenv("RSS_MAX_WORKERS", "8"))
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
EVENTS_SYMBOL_WORKERS = max(1, int(os.getenv("EVENTS_SYMBOL_WORKERS", "8")))

try:
    import pysnowball as ball  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    ball = None
    LOGGER.warning("pysnowball import failed: %s", exc)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1]
    try:
        number = float(text)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        try:
            number = int(value)
            if number > 10_000_000_000:
                return datetime.fromtimestamp(number / 1000, tz=timezone.utc).date()
            if number > 1_000_000_000:
                return datetime.fromtimestamp(number, tz=timezone.utc).date()
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    return None


def _pick(record: dict, keys: Iterable[str]):
    for key in keys:
        if key in record and record.get(key) not in (None, ""):
            return record.get(key)
    return None


def _extract_dict_rows(payload) -> list[dict]:
    rows: list[dict] = []
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            rows.append(node)
            stack.extend(node.values())
            continue
        if isinstance(node, list):
            stack.extend(node)
    return [row for row in rows if row]


def _event_symbols() -> list[str]:
    raw = os.getenv("SNOWBALL_EVENT_SYMBOLS", "").strip() or os.getenv("SNOWBALL_STOCK_SYMBOLS", "").strip()
    output: list[str] = []
    seen: set[str] = set()
    if raw:
        for item in raw.split(","):
            symbol = normalize_symbol(item.strip())
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            output.append(symbol)
        return output

    for symbol in ("600000.SH", "000001.SZ", "600519.SH"):
        if symbol in seen:
            continue
        seen.add(symbol)
        output.append(symbol)

    cached_limit = max(1, int(os.getenv("SNOWBALL_HK_EVENT_LIMIT", "200")))
    cached_hk_symbols = list_cached_symbols(markets=("HK",), limit=cached_limit) or ["00700.HK", "00005.HK", "00941.HK"]
    for symbol in cached_hk_symbols:
        if symbol in seen:
            continue
        seen.add(symbol)
        output.append(symbol)
    return output

def _hkex_regulatory_announcements_rss() -> str:
    override = os.getenv("HKEX_REGULATORY_ANNOUNCEMENTS_RSS", "").strip()
    if override:
        return override
    return "https://www.hkex.com.hk/Services/RSS-Feeds/regulatory-announcements?sc_lang=zh-HK"


def _normalize_hk_code(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text.isdigit():
        return None
    digits = text.zfill(5)
    return f"{digits}.HK"


def _symbol_from_hkex_title(title: str, link: str = "") -> str | None:
    text = str(title or "").strip()
    if not text:
        return None
    patterns = [
        r"(?<!\d)(\d{5})\s*\.?\s*HK\b",
        r"(?:股份代號|股票代號|股份编号|证券代号|Stock Code|Stock code|stock code)[:：\s#-]*([0-9]{1,5})",
        r"^\(?([0-9]{5})\)?(?:\s|[:：\-])",
        r"\(([0-9]{5})\)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        symbol = _normalize_hk_code(match.group(1))
        if symbol:
            return symbol

    link_text = str(link or "")
    link_match = re.search(r"(?<!\d)(\d{5})(?!\d)", link_text)
    if link_match:
        return _normalize_hk_code(link_match.group(1))
    return None


def _dedupe_event_rows(rows: List[dict]) -> List[dict]:
    seen: set[tuple[str, str, str, str]] = set()
    output: list[dict] = []
    for row in rows:
        key = (
            str(row.get("symbol") or ""),
            str(row.get("type") or ""),
            str(row.get("title") or ""),
            str(row.get("link") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _get_hkex_regulatory_announcements(as_of: date) -> list[dict]:
    rows: list[dict] = []
    url = _hkex_regulatory_announcements_rss()
    items = _fetch_rss(url)
    for item in items:
        published_at = item.get("published_at")
        if not published_at or published_at.date() != as_of:
            continue
        title = str(item.get("title") or "").strip()
        link = str(item.get("link") or "").strip()
        symbol = _symbol_from_hkex_title(title, link)
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "type": "announcement",
                "title": title,
                "date": as_of,
                "link": link,
                "source": "HKEX Regulatory Announcement",
            }
        )
    return rows


def _is_buyback_title(title: str) -> bool:
    keywords = ("回购", "回購", "股份回购", "股份回購", "buyback", "repurchase")
    lower = title.lower()
    return any(keyword.lower() in lower for keyword in keywords)


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


def _cache_key(url: str) -> str:
    safe = url.replace("/", "_").replace(":", "_").replace("?", "_").replace("&", "_")
    return f"{safe}.json"


def _load_cache(url: str, *, allow_stale: bool = False) -> List[dict] | None:
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
    age = time.time() - ts
    max_age = CACHE_STALE_ON_ERROR_SECONDS if allow_stale else CACHE_TTL_SECONDS
    if age > max_age:
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
                "published_at": item.get("published_at").isoformat() if item.get("published_at") else None,
            }
            for item in items
        ],
    }
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        LOGGER.warning("write rss cache failed [%s]: %s", url, exc)


def _download_rss(url: str) -> bytes | None:
    data = None
    for attempt in range(RSS_RETRY_COUNT + 1):
        try:
            with _open_url(url) as resp:
                data = resp.read()
                break
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
    return data


def _fetch_rss(url: str) -> List[dict]:
    cached = _load_cache(url)
    if cached is not None:
        return cached
    data = _download_rss(url)
    if data is None:
        return _load_cache(url, allow_stale=True) or []

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


def _fetch_rss_batch(urls: list[str]) -> dict[str, List[dict]]:
    results: dict[str, List[dict]] = {}
    url_list = [url for url in urls if url]
    if not url_list:
        return results
    workers = max(1, min(RSS_MAX_WORKERS, len(url_list)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(_fetch_rss, url): url for url in url_list}
        for future in as_completed(future_map):
            url = future_map[future]
            try:
                results[url] = future.result()
            except Exception as exc:
                LOGGER.warning("fetch rss batch failed [%s]: %s", url, exc)
                results[url] = []
    return results


def _fetch_symbol_report_rows(symbol: str, as_of: date) -> list[dict]:
    if ball is None:
        return []
    snow_symbol = to_snowball_symbol(symbol)
    try:
        payload = ball.report(snow_symbol)
    except Exception as exc:
        LOGGER.warning("snowball report failed [%s]: %s", snow_symbol, exc)
        return []

    rows: list[dict] = []
    for record in _extract_dict_rows(payload):
        row_date = _to_date(
            _pick(
                record,
                (
                    "publish_date",
                    "pub_date",
                    "report_date",
                    "date",
                    "ctime",
                    "timestamp",
                ),
            )
        )
        if row_date != as_of:
            continue
        title = _pick(record, ("title", "name", "report_name", "notice_title"))
        if title in (None, ""):
            continue
        rows.append(
            {
                "symbol": symbol,
                "type": "report",
                "title": str(title),
                "date": row_date,
                "link": str(_pick(record, ("url", "link", "pdf_url", "article_url")) or ""),
                "source": "Snowball Report",
            }
        )
    return rows


def _fetch_symbol_insider_rows(symbol: str, as_of: date) -> list[dict]:
    if ball is None:
        return []
    snow_symbol = to_snowball_symbol(symbol)
    try:
        payload = ball.skholderchg(snow_symbol)
    except Exception as exc:
        LOGGER.warning("snowball skholderchg failed [%s]: %s", snow_symbol, exc)
        return []

    rows: list[dict] = []
    for record in _extract_dict_rows(payload):
        row_date = _to_date(_pick(record, ("change_date", "date", "publish_date", "ctime", "timestamp")))
        if row_date != as_of:
            continue
        shares = _safe_float(_pick(record, ("change_amount", "shares", "volume", "chg_num"))) or 0.0
        trade_type = _pick(record, ("change_type", "direction", "type", "change_reason")) or "trade"
        rows.append(
            {
                "symbol": symbol,
                "date": row_date,
                "type": str(trade_type),
                "shares": shares,
                "link": str(_pick(record, ("url", "link")) or ""),
                "source": "Snowball F10",
            }
        )
    return rows


def get_events(as_of: date) -> List[dict]:
    rows: list[dict] = []
    rows.extend(_get_hkex_regulatory_announcements(as_of))

    if ball is None:
        LOGGER.warning("pysnowball unavailable, skip snowball events")
        return ensure_required(_dedupe_event_rows(rows), ["symbol", "type", "title", "date"], "events.events")

    symbols = _event_symbols()
    workers = max(1, min(EVENTS_SYMBOL_WORKERS, len(symbols)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="event_reports") as executor:
        future_map = {executor.submit(_fetch_symbol_report_rows, symbol, as_of): symbol for symbol in symbols}
        for future in as_completed(future_map):
            symbol = future_map[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                LOGGER.warning("symbol report task failed [%s]: %s", symbol, exc)
    return ensure_required(_dedupe_event_rows(rows), ["symbol", "type", "title", "date"], "events.events")


def get_buyback(as_of: date) -> List[dict]:
    rows: list[dict] = []
    items = _fetch_rss(_hkex_regulatory_announcements_rss())
    for item in items:
        published_at = item.get("published_at")
        if not published_at or published_at.date() != as_of:
            continue
        title = str(item.get("title") or "")
        if not _is_buyback_title(title):
            continue
        symbol = _symbol_from_hkex_title(title, str(item.get("link") or ""))
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "date": as_of,
                "amount": 0.0,
                "link": item.get("link") or "",
                "source": "HKEX Regulatory Announcement",
            }
        )
    return ensure_required(rows, ["symbol", "date", "amount"], "events.buyback")


def get_insider_trade(as_of: date) -> List[dict]:
    if ball is None:
        LOGGER.warning("pysnowball unavailable, skip insider trades")
        return []

    rows: list[dict] = []
    symbols = _event_symbols()
    workers = max(1, min(EVENTS_SYMBOL_WORKERS, len(symbols)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="event_insider") as executor:
        future_map = {executor.submit(_fetch_symbol_insider_rows, symbol, as_of): symbol for symbol in symbols}
        for future in as_completed(future_map):
            symbol = future_map[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                LOGGER.warning("symbol insider task failed [%s]: %s", symbol, exc)
    return ensure_required(rows, ["symbol", "date", "type", "shares"], "events.insider")
