from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List
from urllib.request import urlopen
import os
import xml.etree.ElementTree as ET

from etl.loaders.redis_cache import get_cache_string
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)
RSS_TIMEOUT_SECONDS = int(os.getenv("RSS_TIMEOUT_SECONDS", "12"))
RSS_MAX_WORKERS = int(os.getenv("RSS_MAX_WORKERS", "8"))

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    ak = None
    LOGGER.warning("akshare import failed: %s", exc)


def _df_to_records(df) -> List[dict]:
    if df is None:
        return []
    try:
        return df.to_dict("records")
    except Exception:
        return []


def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        text = str(value)
        if len(text) >= 10 and "-" in text:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        if len(text) >= 8:
            return datetime.strptime(text[:8], "%Y%m%d").date()
    except Exception:
        return None
    return None


def _normalize_symbol(symbol: str) -> str:
    if symbol.endswith(".SH") or symbol.endswith(".SZ") or symbol.endswith(".HK"):
        return symbol
    if symbol.startswith(("5", "6", "9")):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"


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


def _rsshub_xueqiu_announcement(symbol: str) -> str:
    return f"{_rsshub_base()}/xueqiu/stock_info/{symbol}/announcement"


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


def _fetch_rss(url: str) -> List[dict]:
    try:
        with urlopen(url, timeout=RSS_TIMEOUT_SECONDS) as resp:
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
                LOGGER.warning("fetch rss batch failed: %s", exc)
                results[url] = []
    return results


def _is_buyback_title(title: str) -> bool:
    keywords = ["回购", "购回", "股份回购"]
    return any(key in title for key in keywords)


def get_events(as_of: date) -> List[dict]:
    """Fetch events for the given date using AkShare announcements."""
    if ak is None:
        LOGGER.warning("akshare unavailable, skip events")
        return []

    rows: List[dict] = []
    df = None
    # 尝试常见公告接口
    if hasattr(ak, "stock_notice_report"):
        try:
            df = ak.stock_notice_report()
        except Exception as exc:
            LOGGER.warning("stock_notice_report failed: %s", exc)
    elif hasattr(ak, "stock_notice_report_sina"):
        try:
            df = ak.stock_notice_report_sina()
        except Exception as exc:
            LOGGER.warning("stock_notice_report_sina failed: %s", exc)

    for record in _df_to_records(df):
        row_date = _to_date(record.get("date") or record.get("公告日期") or record.get("日期"))
        if row_date != as_of:
            continue
        symbol = record.get("symbol") or record.get("代码") or record.get("证券代码")
        if not symbol:
            continue
        title = record.get("title") or record.get("公告标题") or record.get("公告名称") or "公告"
        rows.append(
            {
                "symbol": _normalize_symbol(str(symbol)),
                "type": "report",
                "title": str(title),
                "date": row_date,
            }
        )

    return ensure_required(rows, ["symbol", "type", "title", "date"], "events.events")


def get_buyback(as_of: date) -> List[dict]:
    """Fetch buyback disclosures using RSSHub Xueqiu announcements (HK)."""
    rows: List[dict] = []
    hk_symbols = _rsshub_hk_symbols()
    url_map = {symbol: _rsshub_xueqiu_announcement(symbol) for symbol in hk_symbols}
    fetched = _fetch_rss_batch(list(url_map.values()))

    for hk_symbol, url in url_map.items():
        for item in fetched.get(url, []):
            published_at = item.get("published_at")
            if not published_at:
                continue
            if published_at.date() != as_of:
                continue
            title = item.get("title") or ""
            if not _is_buyback_title(title):
                continue
            rows.append(
                {
                    "symbol": hk_symbol,
                    "date": published_at.date(),
                    "amount": 0.0,
                }
            )

    return ensure_required(rows, ["symbol", "date", "amount"], "events.buyback")


def get_insider_trade(as_of: date) -> List[dict]:
    """Fetch insider trades using AkShare."""
    if ak is None:
        LOGGER.warning("akshare unavailable, skip insider trades")
        return []

    rows: List[dict] = []
    df = None
    if hasattr(ak, "stock_ggcg_em"):
        try:
            df = ak.stock_ggcg_em()
        except Exception as exc:
            LOGGER.warning("stock_ggcg_em failed: %s", exc)

    for record in _df_to_records(df):
        row_date = _to_date(record.get("变动日期") or record.get("date") or record.get("日期"))
        if row_date != as_of:
            continue
        symbol = record.get("代码") or record.get("symbol") or record.get("证券代码")
        if not symbol:
            continue
        trade_type = record.get("变动方向") or record.get("type") or "trade"
        shares = record.get("变动股数") or record.get("shares") or record.get("变动数量")
        try:
            shares_val = float(shares) if shares is not None else 0.0
        except Exception:
            shares_val = 0.0
        rows.append(
            {
                "symbol": _normalize_symbol(str(symbol)),
                "date": row_date,
                "type": str(trade_type),
                "shares": shares_val,
            }
        )

    return ensure_required(rows, ["symbol", "date", "type", "shares"], "events.insider")
