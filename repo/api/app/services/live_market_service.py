from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import json
import os
from threading import Lock
from types import SimpleNamespace
from typing import Iterable, Literal

from app.core.cache import get_json, set_json
from app.core.db import SessionLocal
from app.core.logger import get_logger
from app.models.daily_prices import DailyPrice
from app.models.financials import Financial
from app.models.stock_intraday_kline import StockIntradayKline
from app.models.stock_live_snapshot import StockLiveSnapshot
from app.models.stock_research_item import StockResearchItem
from app.schemas.indicators import IndicatorPoint
from app.schemas.kline import KlinePoint
from app.schemas.risk_series import RiskPoint
from app.services.cache_utils import build_cache_key, item_to_dict
from app.utils.symbols import normalize_symbol, symbol_lookup_aliases
from etl.fetchers.market_client import get_stock_basic as get_cached_stock_basic
from etl.fetchers.snowball_client import (
    get_daily_history,
    get_kline_history,
    get_recent_financials,
    get_stock_earning_forecasts,
    get_stock_pankou,
    get_stock_quote,
    get_stock_quote_detail,
    get_stock_reports,
    normalize_index_symbol,
    market_from_symbol,
)
from etl.transformers.fundamentals import calc_fundamental_score, calc_growth, calc_profit_quality, calc_risk
from etl.transformers.indicators import (
    calc_adx,
    calc_atr,
    calc_bollinger_bands,
    calc_cci,
    calc_ema,
    calc_kdj,
    calc_ma,
    calc_macd,
    calc_max_drawdown,
    calc_mfi,
    calc_momentum,
    calc_obv,
    calc_roc,
    calc_rsi,
    calc_volatility,
    calc_wma,
)
from etl.utils.env import load_project_env
from etl.utils.stock_basics_cache import load_stock_basics_cache

load_project_env()

LiveKlinePeriod = Literal["1m", "30m", "60m", "day", "week", "month", "quarter", "year"]
LOGGER = get_logger("api.live_market")
LIVE_CACHE_TTL = max(60, int(os.getenv("API_LIVE_CACHE_TTL", "1800")))
UNKNOWN_SECTOR_VALUES = {"", "Unknown", "未知", "未分类"}
A_SHARE_SH_PREFIXES = ("600", "601", "603", "605", "688", "689", "900")
A_SHARE_SZ_PREFIXES = ("000", "001", "002", "003", "200", "300", "301")
BJ_SHARE_PREFIXES = ("4", "8")
BACKGROUND_PROFILE_REFRESH_ENABLED = os.getenv("API_BG_PROFILE_REFRESH", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}
BACKGROUND_PROFILE_REFRESH_WORKERS = max(1, int(os.getenv("API_BG_PROFILE_REFRESH_WORKERS", "2")))
_BACKGROUND_PROFILE_REFRESH_POOL = ThreadPoolExecutor(
    max_workers=BACKGROUND_PROFILE_REFRESH_WORKERS,
    thread_name_prefix="stock_profile_bg",
)
_BACKGROUND_PROFILE_REFRESH_LOCK = Lock()
_BACKGROUND_PROFILE_REFRESH_SYMBOLS: set[str] = set()
BACKGROUND_STOCK_BASICS_REFRESH_ENABLED = os.getenv("API_BG_STOCK_BASICS_REFRESH", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}
BACKGROUND_STOCK_BASICS_REFRESH_WORKERS = max(1, int(os.getenv("API_BG_STOCK_BASICS_REFRESH_WORKERS", "1")))
_BACKGROUND_STOCK_BASICS_REFRESH_POOL = ThreadPoolExecutor(
    max_workers=BACKGROUND_STOCK_BASICS_REFRESH_WORKERS,
    thread_name_prefix="stock_basics_bg",
)
_BACKGROUND_STOCK_BASICS_REFRESH_LOCK = Lock()
_BACKGROUND_STOCK_BASICS_REFRESH_SYMBOLS: set[str] = set()


def _loads_levels(value: str | None) -> list[dict]:
    text = str(value or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _looks_like_equity_symbol(symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    if normalized.endswith(".HK"):
        return normalized[:-3].isdigit()
    if normalized.endswith(".SH"):
        return normalized[:-3].isdigit() and normalized[:-3].startswith(A_SHARE_SH_PREFIXES)
    if normalized.endswith(".SZ"):
        return normalized[:-3].isdigit() and normalized[:-3].startswith(A_SHARE_SZ_PREFIXES)
    if normalized.endswith(".BJ"):
        return normalized[:-3].isdigit() and normalized[:-3].startswith(BJ_SHARE_PREFIXES)
    if normalized.endswith(".US"):
        return True
    return False


def _dedupe_stock_rows(rows: Iterable[dict]) -> list[dict]:
    output: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = normalize_symbol(str(row.get("symbol") or ""))
        if not symbol or symbol in seen or not _looks_like_equity_symbol(symbol):
            continue
        seen.add(symbol)
        output.append(
            {
                "symbol": symbol,
                "name": str(row.get("name") or symbol),
                "market": str(row.get("market") or market_from_symbol(symbol)),
                "sector": str(row.get("sector") or "Unknown"),
            }
        )
    return output


def _filter_stock_rows(
    rows: Iterable[dict],
    *,
    market: str | None = None,
    keyword: str | None = None,
    sector: str | None = None,
) -> list[dict]:
    normalized_rows = _dedupe_stock_rows(rows)
    keyword_text = keyword.strip().lower() if keyword else None
    sector_text = sector.strip().lower() if sector else None
    output: list[dict] = []
    for row in normalized_rows:
        row_market = str(row.get("market") or "").upper()
        if market and row_market != market:
            continue
        if sector_text:
            row_sector = str(row.get("sector") or "").lower()
            if sector_text not in row_sector:
                continue
        if keyword_text:
            haystack = " ".join(
                [
                    str(row.get("symbol") or ""),
                    str(row.get("name") or ""),
                    str(row.get("sector") or ""),
                ]
            ).lower()
            if keyword_text not in haystack:
                continue
        output.append(row)
    return output


def _fallback_stock_rows(
    *,
    market: str | None = None,
    keyword: str | None = None,
    sector: str | None = None,
    limit: int | None = 100,
) -> list[dict]:
    rows = load_stock_basics_cache(allow_stale=True)
    filtered = _filter_stock_rows(rows, market=market, keyword=keyword, sector=sector)
    if limit is None:
        return filtered
    return filtered[:limit]


def _merge_stock_rows(primary: Iterable[dict], fallback: Iterable[dict], *, limit: int | None) -> list[dict]:
    fallback_by_symbol = {row["symbol"]: row for row in _dedupe_stock_rows(fallback)}
    merged: list[dict] = []
    seen: set[str] = set()

    for row in _dedupe_stock_rows(primary):
        symbol = row["symbol"]
        fallback_row = fallback_by_symbol.get(symbol, {})
        merged_row = dict(row)
        if not merged_row.get("name") or str(merged_row.get("name")) == symbol:
            merged_row["name"] = fallback_row.get("name") or symbol
        if _needs_sector_refresh(merged_row.get("sector")):
            fallback_sector = str(fallback_row.get("sector") or "").strip()
            if not _needs_sector_refresh(fallback_sector):
                merged_row["sector"] = fallback_sector
            else:
                merged_row["sector"] = fallback_sector or "Unknown"
        if not merged_row.get("market"):
            merged_row["market"] = fallback_row.get("market") or market_from_symbol(symbol)
        merged.append(merged_row)
        seen.add(symbol)
    for row in _dedupe_stock_rows(fallback):
        if row["symbol"] in seen:
            continue
        merged.append(row)
        seen.add(row["symbol"])
        if limit is not None and len(merged) >= limit:
            break
    if limit is None:
        return merged
    return merged[:limit]


def _hydrate_stock_rows_from_local_basics(rows: Iterable[dict], *, limit: int) -> list[dict]:
    normalized_rows = _dedupe_stock_rows(rows)
    symbols = [row["symbol"] for row in normalized_rows if row.get("symbol")]
    if not symbols:
        return normalized_rows[:limit]
    local_rows = load_stock_basics_cache(symbols, allow_stale=True)
    if not local_rows:
        return normalized_rows[:limit]
    return _merge_stock_rows(normalized_rows, local_rows, limit=limit)


def _hydrate_stock_rows_from_profile_cache(rows: Iterable[dict], *, limit: int) -> list[dict]:
    normalized_rows = _dedupe_stock_rows(rows)
    if not normalized_rows:
        return normalized_rows[:limit]
    cached_rows: list[dict] = []
    for row in normalized_rows:
        symbol = str(row.get("symbol") or "").strip()
        if not symbol:
            continue
        cached = get_json(build_cache_key("live:stock:profile", symbol=symbol))
        if not isinstance(cached, dict):
            continue
        cached_rows.append(
            {
                "symbol": symbol,
                "name": str(cached.get("name") or symbol),
                "market": str(cached.get("market") or row.get("market") or market_from_symbol(symbol)),
                "sector": str(cached.get("sector") or "Unknown"),
            }
        )
    if not cached_rows:
        return normalized_rows[:limit]
    return _merge_stock_rows(normalized_rows, cached_rows, limit=limit)


def _needs_local_name_hydration(rows: Iterable[dict]) -> bool:
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = normalize_symbol(str(row.get("symbol") or ""))
        if not symbol:
            continue
        if symbol.endswith(".HK") or symbol.endswith(".US"):
            continue
        name = str(row.get("name") or "").strip()
        if not name or name == symbol:
            return True
    return False


def _needs_sector_refresh(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if text.lower() == "unknown":
        return True
    return text in {"未知", "未分类"}


def _refresh_stock_rows_sectors(rows: list[dict]) -> list[dict]:
    if not rows:
        return rows
    symbols: list[str] = []
    seen: set[str] = set()
    for row in rows:
        symbol = str(row.get("symbol") or "").strip()
        if not symbol or symbol in seen:
            continue
        if _needs_sector_refresh(row.get("sector")):
            symbols.append(symbol)
            seen.add(symbol)
    if not symbols:
        return rows
    refreshed = get_cached_stock_basic(symbols, force_refresh=True, allow_stale_cache=False)
    if not refreshed:
        return rows
    return _merge_stock_rows(rows, refreshed, limit=len(rows))



def _fallback_stock_profile(symbol: str) -> dict:
    rows = load_stock_basics_cache([symbol], allow_stale=True)
    if rows:
        return dict(rows[0])
    return {
        "symbol": symbol,
        "name": symbol,
        "market": market_from_symbol(symbol),
        "sector": "Unknown",
    }


def _merge_stock_profile(primary: dict | None, fallback: dict) -> dict:
    base = dict(fallback)
    current = dict(primary or {})
    base.update({key: value for key, value in current.items() if value not in (None, "")})
    if not base.get("name") or str(base.get("name")) == str(base.get("symbol")):
        base["name"] = fallback.get("name") or base.get("symbol")
    if not base.get("sector") or str(base.get("sector")) in {"", "Unknown"}:
        base["sector"] = fallback.get("sector") or "Unknown"
    if not base.get("market"):
        base["market"] = fallback.get("market") or market_from_symbol(str(base.get("symbol") or ""))
    return base


def _has_quote_signal(profile: dict | None) -> bool:
    if not isinstance(profile, dict):
        return False
    for key in ("quote", "quote_detail", "pankou"):
        value = profile.get(key)
        if isinstance(value, dict) and value:
            return True
    return False


def _has_identity_signal(profile: dict | None) -> bool:
    if not isinstance(profile, dict):
        return False
    symbol = normalize_symbol(str(profile.get("symbol") or ""))
    name = str(profile.get("name") or "").strip()
    sector = str(profile.get("sector") or "").strip()
    has_name = bool(name) and name != symbol
    has_sector = bool(sector) and sector not in UNKNOWN_SECTOR_VALUES
    return has_name and has_sector


def _profile_extras_from_cache(profile: dict | None) -> tuple[dict, dict]:
    if not isinstance(profile, dict):
        return {}, {}
    quote_detail = profile.get("quote_detail")
    pankou = profile.get("pankou")
    return (
        dict(quote_detail) if isinstance(quote_detail, dict) else {},
        dict(pankou) if isinstance(pankou, dict) else {},
    )


def _run_background_profile_refresh(symbol: str) -> None:
    try:
        _get_live_stock_profile(
            symbol,
            include_quote_detail=True,
            include_pankou=True,
            prefer_live=True,
            queue_background_refresh=False,
        )
    except Exception as exc:
        LOGGER.warning("background stock profile refresh failed [%s]: %s", symbol, exc)
    finally:
        with _BACKGROUND_PROFILE_REFRESH_LOCK:
            _BACKGROUND_PROFILE_REFRESH_SYMBOLS.discard(symbol)


def _queue_background_profile_refresh(symbol: str) -> None:
    if not BACKGROUND_PROFILE_REFRESH_ENABLED:
        return
    normalized = normalize_symbol(symbol)
    if not normalized:
        return
    with _BACKGROUND_PROFILE_REFRESH_LOCK:
        if normalized in _BACKGROUND_PROFILE_REFRESH_SYMBOLS:
            return
        _BACKGROUND_PROFILE_REFRESH_SYMBOLS.add(normalized)
    try:
        _BACKGROUND_PROFILE_REFRESH_POOL.submit(_run_background_profile_refresh, normalized)
    except Exception as exc:
        with _BACKGROUND_PROFILE_REFRESH_LOCK:
            _BACKGROUND_PROFILE_REFRESH_SYMBOLS.discard(normalized)
        LOGGER.warning("queue background stock profile refresh failed [%s]: %s", normalized, exc)


def _run_background_stock_basics_refresh(symbols: tuple[str, ...]) -> None:
    try:
        if symbols:
            get_cached_stock_basic(list(symbols), force_refresh=True, allow_stale_cache=False)
    except Exception as exc:
        LOGGER.warning("background stock basics refresh failed [%s]: %s", ",".join(symbols), exc)
    finally:
        with _BACKGROUND_STOCK_BASICS_REFRESH_LOCK:
            for symbol in symbols:
                _BACKGROUND_STOCK_BASICS_REFRESH_SYMBOLS.discard(symbol)


def _queue_background_stock_basics_refresh(symbols: list[str]) -> None:
    if not BACKGROUND_STOCK_BASICS_REFRESH_ENABLED:
        return
    unique_symbols: list[str] = []
    with _BACKGROUND_STOCK_BASICS_REFRESH_LOCK:
        for raw in symbols:
            symbol = normalize_symbol(raw)
            if not symbol or symbol in _BACKGROUND_STOCK_BASICS_REFRESH_SYMBOLS:
                continue
            _BACKGROUND_STOCK_BASICS_REFRESH_SYMBOLS.add(symbol)
            unique_symbols.append(symbol)
    if not unique_symbols:
        return
    try:
        _BACKGROUND_STOCK_BASICS_REFRESH_POOL.submit(_run_background_stock_basics_refresh, tuple(unique_symbols))
    except Exception as exc:
        with _BACKGROUND_STOCK_BASICS_REFRESH_LOCK:
            for symbol in unique_symbols:
                _BACKGROUND_STOCK_BASICS_REFRESH_SYMBOLS.discard(symbol)
        LOGGER.warning("queue background stock basics refresh failed [%s]: %s", ",".join(unique_symbols), exc)


def _queue_background_profile_refresh_for_rows(rows: Iterable[dict], *, max_symbols: int = 6) -> None:
    pending: list[str] = []
    seen: set[str] = set()
    for row in rows:
        symbol = normalize_symbol(str((row or {}).get("symbol") or ""))
        if not symbol or symbol in seen:
            continue
        # HK/US sector backfill is expensive and unstable; stock pool stays local-only.
        if symbol.endswith(".HK") or symbol.endswith(".US"):
            continue
        seen.add(symbol)
        name = str((row or {}).get("name") or "").strip()
        if not _needs_sector_refresh((row or {}).get("sector")) and (name and name != symbol):
            continue
        pending.append(symbol)
        if len(pending) >= max_symbols:
            break
    if pending:
        _queue_background_stock_basics_refresh(pending)


def _has_non_zero_signal(row: dict | None, *, fields: tuple[str, ...]) -> bool:
    if not isinstance(row, dict):
        return False
    for field in fields:
        value = row.get(field)
        try:
            if value is not None and abs(float(value)) > 1e-12:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _financial_rows_have_signal(rows: Iterable[dict]) -> bool:
    return any(
        _has_non_zero_signal(row, fields=("revenue", "net_income", "cash_flow", "roe", "debt_ratio"))
        for row in rows
    )


def _fundamental_payload_is_usable(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if not _has_non_zero_signal(payload, fields=("score",)):
        return False
    summary = str(payload.get("summary") or "")
    return "盈利质量 0.00，成长性 0.00，风险项 0.00" not in summary


def _load_db_daily_rows(symbol: str, *, start: date | None = None, end: date | None = None) -> list[dict]:
    normalized = normalize_symbol(symbol)
    aliases = symbol_lookup_aliases(normalized)
    with SessionLocal() as db:
        query = db.query(DailyPrice).filter(DailyPrice.symbol.in_(aliases))
        if start is not None:
            query = query.filter(DailyPrice.date >= start)
        if end is not None:
            query = query.filter(DailyPrice.date <= end)
        rows = query.order_by(DailyPrice.date.asc()).all()
        items_by_date: dict[date, dict] = {}
        for row in rows:
            items_by_date[row.date] = {
                "symbol": normalized,
                "date": row.date,
                "open": float(row.open or 0),
                "high": float(row.high or 0),
                "low": float(row.low or 0),
                "close": float(row.close or 0),
                "volume": float(row.volume or 0),
            }
        return [items_by_date[row_date] for row_date in sorted(items_by_date)]


def _load_db_intraday_rows(
    symbol: str,
    *,
    period: LiveKlinePeriod,
    start: date | None = None,
    end: date | None = None,
    limit: int = 240,
) -> list[dict]:
    normalized = normalize_symbol(symbol)
    aliases = symbol_lookup_aliases(normalized)
    try:
        with SessionLocal() as db:
            query = db.query(StockIntradayKline).filter(
                StockIntradayKline.symbol.in_(aliases),
                StockIntradayKline.period == period,
            )
            if start is not None:
                query = query.filter(StockIntradayKline.timestamp >= datetime.combine(start, datetime.min.time()))
            if end is not None:
                query = query.filter(StockIntradayKline.timestamp <= datetime.combine(end, datetime.max.time()))
            rows = (
                query.order_by(StockIntradayKline.timestamp.desc(), StockIntradayKline.symbol.asc())
                .limit(limit)
                .all()
            )
    except Exception:
        return []
    items = [
        {
            "symbol": normalized,
            "date": row.timestamp,
            "open": float(row.open or 0),
            "high": float(row.high or 0),
            "low": float(row.low or 0),
            "close": float(row.close or 0),
            "volume": float(row.volume or 0),
        }
        for row in reversed(rows)
    ]
    return items


def _quote_from_daily_rows(symbol: str, rows: Iterable[object]) -> dict:
    normalized = normalize_symbol(symbol)
    items_by_date: dict[date, SimpleNamespace] = {}
    for row in rows:
        row_date = getattr(row, "date", None)
        if row_date is None or row_date in items_by_date:
            continue
        items_by_date[row_date] = SimpleNamespace(
            date=row_date,
            open=float(getattr(row, "open", 0) or 0),
            high=float(getattr(row, "high", 0) or 0),
            low=float(getattr(row, "low", 0) or 0),
            close=float(getattr(row, "close", 0) or 0),
            volume=float(getattr(row, "volume", 0) or 0),
        )
    ordered_dates = sorted(items_by_date, reverse=True)
    if not ordered_dates:
        return {}
    latest = items_by_date[ordered_dates[0]]
    previous = items_by_date[ordered_dates[1]] if len(ordered_dates) > 1 else None
    last_close = float(previous.close) if previous is not None else None
    change = float(latest.close) - last_close if last_close not in (None, 0) else None
    percent = (change / last_close * 100.0) if change is not None and last_close not in (None, 0) else None
    return {
        "symbol": normalized,
        "current": float(latest.close),
        "change": change,
        "percent": percent,
        "open": float(latest.open),
        "high": float(latest.high),
        "low": float(latest.low),
        "last_close": last_close,
        "volume": float(latest.volume),
        "amount": None,
        "turnover_rate": None,
        "amplitude": None,
        "timestamp": datetime.combine(latest.date, datetime.min.time()),
    }


def _load_db_quote_snapshot(symbol: str) -> dict:
    normalized = normalize_symbol(symbol)
    aliases = symbol_lookup_aliases(normalized)
    with SessionLocal() as db:
        rows = (
            db.query(DailyPrice)
            .filter(DailyPrice.symbol.in_(aliases))
            .order_by(DailyPrice.date.desc(), DailyPrice.symbol.asc())
            .limit(16)
            .all()
        )
    return _quote_from_daily_rows(normalized, rows)


def _load_db_financial_rows(
    symbol: str,
    *,
    limit: int,
    offset: int,
    period: str | None = None,
    min_revenue: float | None = None,
    min_net_income: float | None = None,
    sort: str = "desc",
) -> tuple[list[dict], int]:
    normalized = normalize_symbol(symbol)
    aliases = symbol_lookup_aliases(normalized)
    with SessionLocal() as db:
        query = db.query(Financial).filter(Financial.symbol.in_(aliases))
        if period:
            query = query.filter(Financial.period == period)
        if min_revenue is not None:
            query = query.filter(Financial.revenue >= min_revenue)
        if min_net_income is not None:
            query = query.filter(Financial.net_income >= min_net_income)
        order_clause = Financial.period.asc() if sort == "asc" else Financial.period.desc()
        rows = query.order_by(order_clause, Financial.symbol.asc()).all()
        items_by_period: dict[str, dict] = {}
        for row in rows:
            if row.period in items_by_period:
                continue
            items_by_period[row.period] = {
                "symbol": normalized,
                "period": row.period,
                "revenue": float(row.revenue or 0),
                "net_income": float(row.net_income or 0),
                "cash_flow": float(row.cash_flow or 0),
                "roe": float(row.roe or 0),
                "debt_ratio": float(row.debt_ratio or 0),
            }
        deduped_items = list(items_by_period.values())
        total = len(deduped_items)
        items = deduped_items[offset : offset + limit]
    return items, total


def _load_db_stock_live_snapshot(symbol: str) -> dict:
    normalized = normalize_symbol(symbol)
    aliases = symbol_lookup_aliases(normalized)
    try:
        with SessionLocal() as db:
            row = (
                db.query(StockLiveSnapshot)
                .filter(StockLiveSnapshot.symbol.in_(aliases))
                .order_by(StockLiveSnapshot.as_of.desc(), StockLiveSnapshot.symbol.asc())
                .first()
            )
    except Exception:
        return {}
    if row is None:
        return {}
    payload: dict = {"symbol": normalized}
    quote = {
        "current": row.current,
        "change": row.change,
        "percent": row.percent,
        "open": row.open,
        "high": row.high,
        "low": row.low,
        "last_close": row.last_close,
        "volume": row.volume,
        "amount": row.amount,
        "turnover_rate": row.turnover_rate,
        "amplitude": row.amplitude,
        "timestamp": row.quote_timestamp or row.as_of,
    }
    if any(value is not None for value in quote.values()):
        payload["quote"] = quote
    detail = {
        "pe_ttm": row.pe_ttm,
        "pb": row.pb,
        "ps_ttm": row.ps_ttm,
        "pcf": row.pcf,
        "market_cap": row.market_cap,
        "float_market_cap": row.float_market_cap,
        "dividend_yield": row.dividend_yield,
        "volume_ratio": row.volume_ratio,
        "lot_size": row.lot_size,
    }
    if any(value is not None for value in detail.values()):
        payload["quote_detail"] = detail
    pankou = {
        "diff": row.pankou_diff,
        "ratio": row.pankou_ratio,
        "timestamp": row.pankou_timestamp or row.as_of,
        "bids": _loads_levels(row.pankou_bids_json),
        "asks": _loads_levels(row.pankou_asks_json),
    }
    if pankou["diff"] is not None or pankou["ratio"] is not None or pankou["bids"] or pankou["asks"]:
        payload["pankou"] = pankou
    return payload


def _load_db_stock_research(symbol: str, *, item_type: str, limit: int) -> list[dict]:
    normalized = normalize_symbol(symbol)
    aliases = symbol_lookup_aliases(normalized)
    try:
        with SessionLocal() as db:
            rows = (
                db.query(StockResearchItem)
                .filter(StockResearchItem.symbol.in_(aliases), StockResearchItem.item_type == item_type)
                .order_by(StockResearchItem.published_at.desc(), StockResearchItem.id.desc())
                .limit(limit)
                .all()
            )
    except Exception:
        return []
    return [
        {
            "title": row.title,
            "published_at": row.published_at,
            "link": row.link,
            "summary": row.summary,
            "institution": row.institution,
            "rating": row.rating,
            "source": row.source,
        }
        for row in rows
    ]


def _snapshot_daily_row(symbol: str) -> dict | None:
    quote = get_stock_quote(symbol)
    if not quote:
        return None
    close_val = quote.get("current")
    if close_val is None:
        return None
    open_val = quote.get("open")
    high_val = quote.get("high")
    low_val = quote.get("low")
    last_close = quote.get("last_close")
    base_open = open_val if open_val is not None else (last_close if last_close is not None else close_val)
    base_high = high_val if high_val is not None else max(float(base_open), float(close_val))
    base_low = low_val if low_val is not None else min(float(base_open), float(close_val))
    timestamp = quote.get("timestamp") or datetime.now()
    snapshot_date = _calendar_value(timestamp) if isinstance(timestamp, (date, datetime)) else date.today()
    return {
        "symbol": symbol,
        "date": snapshot_date,
        "open": float(base_open),
        "high": float(base_high),
        "low": float(base_low),
        "close": float(close_val),
        "volume": float(quote.get("volume") or 0),
    }


def _calendar_value(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def _period_key(value: date | datetime, period: LiveKlinePeriod) -> tuple[int, int]:
    calendar_value = _calendar_value(value)
    if period == "week":
        iso_year, iso_week, _ = calendar_value.isocalendar()
        return iso_year, iso_week
    if period == "month":
        return calendar_value.year, calendar_value.month
    if period == "quarter":
        return calendar_value.year, (calendar_value.month - 1) // 3 + 1
    if period == "year":
        return calendar_value.year, 1
    return calendar_value.year, calendar_value.toordinal()


def _aggregate_points(rows: Iterable[KlinePoint], period: LiveKlinePeriod) -> list[KlinePoint]:
    if period == "day":
        return list(rows)

    items: list[KlinePoint] = []
    bucket: list[KlinePoint] = []
    current_key: tuple[int, int] | None = None

    def flush() -> None:
        nonlocal bucket
        if not bucket:
            return
        first = bucket[0]
        last = bucket[-1]
        items.append(
            KlinePoint(
                date=last.date,
                open=float(first.open),
                high=max(float(row.high) for row in bucket),
                low=min(float(row.low) for row in bucket),
                close=float(last.close),
            )
        )
        bucket = []

    for row in rows:
        key = _period_key(row.date, period)
        if current_key is None:
            current_key = key
        if key != current_key:
            flush()
            current_key = key
        bucket.append(row)
    flush()
    return items


def _points_from_rows(rows: Iterable[dict]) -> list[KlinePoint]:
    points = [
        KlinePoint(
            date=row["date"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
        )
        for row in rows
        if row.get("date") is not None
    ]
    points.sort(key=lambda item: item.date)
    return points


def _filter_points(points: list[KlinePoint], start: date | None, end: date | None, limit: int) -> list[KlinePoint]:
    filtered = [
        item
        for item in points
        if (start is None or _calendar_value(item.date) >= start) and (end is None or _calendar_value(item.date) <= end)
    ]
    return filtered[-limit:]


def _minimum_kline_points(period: LiveKlinePeriod, limit: int) -> int:
    bounded_limit = max(1, int(limit))
    if period in {"day", "week", "month"}:
        return min(bounded_limit, 12)
    if period == "quarter":
        return min(bounded_limit, 8)
    if period == "year":
        return min(bounded_limit, 4)
    return 1


def _has_sufficient_kline_points(
    points: list[KlinePoint],
    period: LiveKlinePeriod,
    *,
    limit: int,
    start: date | None = None,
    end: date | None = None,
) -> bool:
    if not points:
        return False
    if period in {"1m", "30m", "60m"}:
        return True
    if start is not None or end is not None:
        return len(points) > 1
    return len(points) >= _minimum_kline_points(period, limit)


def _load_local_kline_points(
    symbol: str,
    *,
    period: LiveKlinePeriod,
    limit: int,
    start: date | None = None,
    end: date | None = None,
    is_index: bool = False,
) -> list[KlinePoint]:
    if is_index:
        return []
    if period in {"1m", "30m", "60m"}:
        intraday_points = _points_from_rows(
            _load_db_intraday_rows(symbol, period=period, limit=limit, start=start, end=end)
        )
        return _filter_points(intraday_points, start, end, limit)
    if period not in {"day", "week", "month", "quarter", "year"}:
        return []
    db_points = _points_from_rows(_load_db_daily_rows(symbol, start=start, end=end))
    if not db_points:
        return []
    if period == "day":
        points = db_points
    elif period == "week":
        points = _aggregate_points(db_points, "week")
    elif period == "month":
        points = _aggregate_points(db_points, "month")
    elif period == "quarter":
        points = _aggregate_points(db_points, "quarter")
    else:
        points = _aggregate_points(db_points, "year")
    return _filter_points(points, start, end, limit)


def list_live_stocks(
    *,
    market: str | None = None,
    keyword: str | None = None,
    sector: str | None = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "asc",
):
    normalized_market = market.upper() if market else None
    keyword_text = keyword.strip() if keyword else None
    normalized_keyword = keyword.strip().lower() if keyword else None
    sector_text = sector.strip() if sector else None
    normalized_sector = sector.strip().lower() if sector else None
    page_cache_key = build_cache_key(
        "live:stocks:page",
        market=normalized_market,
        keyword=normalized_keyword,
        sector=normalized_sector,
        limit=limit,
        offset=offset,
        sort=sort,
        version=1,
    )
    all_cache_key = build_cache_key(
        "live:stocks:all",
        market=normalized_market,
        keyword=normalized_keyword,
        sector=normalized_sector,
        sort=sort,
        version=1,
    )
    cached = get_json(page_cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        base_rows = cached["items"]
        if _needs_local_name_hydration(base_rows):
            base_rows = _hydrate_stock_rows_from_local_basics(base_rows, limit=len(base_rows))
        hydrated = _hydrate_stock_rows_from_profile_cache(base_rows, limit=len(base_rows))
        _queue_background_profile_refresh_for_rows(hydrated)
        if hydrated != cached["items"]:
            set_json(page_cache_key, {"items": hydrated, "total": cached["total"]}, ttl=LIVE_CACHE_TTL)
        return hydrated, cached["total"]

    all_cached = get_json(all_cache_key)
    if isinstance(all_cached, dict) and isinstance(all_cached.get("items"), list) and isinstance(all_cached.get("total"), int):
        all_items = _dedupe_stock_rows(all_cached["items"])
        total = int(all_cached["total"])
    else:
        all_items = _fallback_stock_rows(
            market=normalized_market,
            keyword=keyword_text,
            sector=sector_text,
            limit=None,
        )
        all_items = _dedupe_stock_rows(all_items)
        all_items.sort(key=lambda item: str(item.get("symbol", "")), reverse=sort == "desc")
        total = len(all_items)
        set_json(all_cache_key, {"items": all_items, "total": total}, ttl=LIVE_CACHE_TTL)

    payload = all_items[offset : offset + limit]
    if _needs_local_name_hydration(payload):
        payload = _hydrate_stock_rows_from_local_basics(payload, limit=len(payload))
    payload = _hydrate_stock_rows_from_profile_cache(payload, limit=len(payload))
    _queue_background_profile_refresh_for_rows(payload)
    set_json(page_cache_key, {"items": payload, "total": total}, ttl=LIVE_CACHE_TTL)
    return payload, total


def get_live_stock_profile(symbol: str, *, prefer_live: bool = False) -> dict | None:
    return _get_live_stock_profile(
        symbol,
        include_quote_detail=True,
        include_pankou=True,
        prefer_live=prefer_live,
    )


def get_live_stock_overview_profile(symbol: str, *, prefer_live: bool = False) -> dict | None:
    return _get_live_stock_profile(
        symbol,
        include_quote_detail=False,
        include_pankou=False,
        prefer_live=prefer_live,
    )


def _get_live_stock_profile(
    symbol: str,
    *,
    include_quote_detail: bool,
    include_pankou: bool,
    prefer_live: bool = False,
    queue_background_refresh: bool = True,
) -> dict | None:
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key("live:stock:profile", symbol=normalized)
    cached = get_json(cache_key)
    local_snapshot = _load_db_stock_live_snapshot(normalized) if not prefer_live else {}
    if (
        isinstance(cached, dict)
        and not prefer_live
        and not local_snapshot
        and _has_quote_signal(cached)
        and _has_identity_signal(cached)
        and (include_quote_detail or isinstance(cached.get("quote_detail"), dict))
        and (include_pankou or isinstance(cached.get("pankou"), dict))
    ):
        if queue_background_refresh:
            _queue_background_profile_refresh(normalized)
        return cached

    fallback_profile = _fallback_stock_profile(normalized)
    rows = (
        get_cached_stock_basic([normalized], allow_stale_cache=True)
        if prefer_live
        else load_stock_basics_cache([normalized], allow_stale=True)
    )
    if prefer_live and rows and str(rows[0].get("sector") or "").strip() in {"", "Unknown", "未知", "未分类"}:
        refreshed = get_cached_stock_basic([normalized], force_refresh=True, allow_stale_cache=False)
        if refreshed:
            rows = refreshed
    primary_profile = dict(rows[0]) if rows else None
    if isinstance(cached, dict):
        primary_profile = _merge_stock_profile(cached, primary_profile or fallback_profile)
    result = _merge_stock_profile(primary_profile, fallback_profile)
    cached_quote_detail, cached_pankou = _profile_extras_from_cache(cached)
    if local_snapshot.get("quote"):
        result["quote"] = dict(local_snapshot["quote"])
    if include_quote_detail and local_snapshot.get("quote_detail"):
        result["quote_detail"] = dict(local_snapshot["quote_detail"])
    elif cached_quote_detail:
        result["quote_detail"] = {key: value for key, value in cached_quote_detail.items() if key != "symbol"}
    if include_pankou and local_snapshot.get("pankou"):
        result["pankou"] = dict(local_snapshot["pankou"])
    elif cached_pankou:
        result["pankou"] = {
            "diff": cached_pankou.get("diff"),
            "ratio": cached_pankou.get("ratio"),
            "timestamp": cached_pankou.get("timestamp"),
            "bids": cached_pankou.get("bids") or [],
            "asks": cached_pankou.get("asks") or [],
        }
    if local_snapshot:
        if _has_quote_signal(result):
            set_json(cache_key, result, ttl=LIVE_CACHE_TTL)
        if not prefer_live and queue_background_refresh:
            _queue_background_profile_refresh(normalized)
        return result
    if not prefer_live:
        if queue_background_refresh:
            _queue_background_profile_refresh(normalized)
        return result
    quote = get_stock_quote(normalized)
    if not quote:
        quote = _load_db_quote_snapshot(normalized)
    if quote:
        quote_name = str(quote.get("name") or "").strip()
        if quote_name and str(result.get("name") or "").strip() in {"", normalized}:
            result["name"] = quote_name
        quote_sector = str(quote.get("sector") or "").strip()
        if quote_sector and str(result.get("sector") or "").strip() in UNKNOWN_SECTOR_VALUES:
            result["sector"] = quote_sector
    if quote:
        result["quote"] = {key: value for key, value in quote.items() if key not in {"symbol", "name", "sector"}}
    if include_quote_detail:
        quote_detail = get_stock_quote_detail(normalized) or cached_quote_detail
        if quote_detail:
            result["quote_detail"] = {key: value for key, value in quote_detail.items() if key != "symbol"}
    if include_pankou:
        pankou = get_stock_pankou(normalized) or cached_pankou
    else:
        pankou = cached_pankou
    if pankou:
        result["pankou"] = {
            "diff": pankou.get("diff"),
            "ratio": pankou.get("ratio"),
            "timestamp": pankou.get("timestamp"),
            "bids": pankou.get("bids") or [],
            "asks": pankou.get("asks") or [],
        }
    if _has_quote_signal(result):
        set_json(cache_key, result, ttl=LIVE_CACHE_TTL)
    return result


def get_live_stock_profile_extras(symbol: str, *, prefer_live: bool = False) -> dict:
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key("live:stock:profile", symbol=normalized)
    cached = get_json(cache_key)
    cached_quote_detail, cached_pankou = _profile_extras_from_cache(cached)
    local_snapshot = _load_db_stock_live_snapshot(normalized) if not prefer_live else {}
    quote_detail = local_snapshot.get("quote_detail") or cached_quote_detail
    pankou = local_snapshot.get("pankou") or cached_pankou
    if not prefer_live:
        _queue_background_profile_refresh(normalized)
    if prefer_live:
        quote_detail = get_stock_quote_detail(normalized) or quote_detail or cached_quote_detail
        pankou = get_stock_pankou(normalized) or pankou or cached_pankou
    payload: dict = {"symbol": normalized}
    if quote_detail:
        payload["quote_detail"] = {key: value for key, value in quote_detail.items() if key != "symbol"}
    if pankou:
        payload["pankou"] = {
            "diff": pankou.get("diff"),
            "ratio": pankou.get("ratio"),
            "timestamp": pankou.get("timestamp"),
            "bids": pankou.get("bids") or [],
            "asks": pankou.get("asks") or [],
        }
    if isinstance(cached, dict) and (payload.get("quote_detail") or payload.get("pankou")):
        merged = dict(cached)
        merged.update(payload)
        if _has_quote_signal(merged):
            set_json(cache_key, merged, ttl=LIVE_CACHE_TTL)
    return payload


def get_live_stock_daily(
    symbol: str,
    *,
    start: date | None = None,
    end: date | None = None,
    sort: str = "asc",
    min_volume: float | None = None,
) -> list[dict]:
    normalized = normalize_symbol(symbol)
    rows = _load_db_daily_rows(normalized, start=start, end=end)
    if not rows:
        count = 1200 if start else 360
        rows = get_kline_history(normalized, period="day", count=count, as_of=end, is_index=False)
    if not rows:
        snapshot_row = _snapshot_daily_row(normalized)
        if snapshot_row is not None:
            rows = [snapshot_row]
    filtered = [
        row
        for row in rows
        if (start is None or row["date"] >= start)
        and (end is None or row["date"] <= end)
        and (min_volume is None or float(row.get("volume", 0) or 0) >= min_volume)
    ]
    filtered.sort(key=lambda item: item["date"], reverse=sort == "desc")
    return filtered


def get_live_kline(
    symbol: str,
    *,
    period: LiveKlinePeriod = "day",
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
    is_index: bool = False,
) -> list[KlinePoint]:
    normalized = normalize_index_symbol(symbol) if is_index else normalize_symbol(symbol)
    cache_key = build_cache_key(
        "live:kline",
        symbol=normalized,
        period=period,
        limit=limit,
        start=start,
        end=end,
        is_index=is_index,
    )
    cached = get_json(cache_key)
    cached_items: list[KlinePoint] = []
    if isinstance(cached, list):
        cached_items = [KlinePoint(**item) for item in cached if isinstance(item, dict)]
        if _has_sufficient_kline_points(cached_items, period, limit=limit, start=start, end=end):
            return cached_items

    local_items = _load_local_kline_points(normalized, period=period, limit=limit, start=start, end=end, is_index=is_index)
    if _has_sufficient_kline_points(local_items, period, limit=limit, start=start, end=end):
        set_json(cache_key, [item.dict() for item in local_items], ttl=LIVE_CACHE_TTL)
        return local_items

    if period in {"1m", "30m", "60m", "day", "week", "month"}:
        if period == "1m":
            fetch_count = max(limit * 2, 240)
        elif period in {"30m", "60m", "day"}:
            fetch_count = max(limit * 2, 180)
        else:
            fetch_count = max(limit * 2, 160)
        points = _points_from_rows(
            get_kline_history(normalized, period=period, count=fetch_count, as_of=end, is_index=is_index)
        )
    elif period == "quarter":
        monthly_count = min(max(limit * 3 + 6, 36), 720)
        base_points = _points_from_rows(
            get_kline_history(normalized, period="month", count=monthly_count, as_of=end, is_index=is_index)
        )
        points = _aggregate_points(base_points, "quarter")
    else:
        monthly_count = min(max(limit * 12 + 12, 120), 720)
        base_points = _points_from_rows(
            get_kline_history(normalized, period="month", count=monthly_count, as_of=end, is_index=is_index)
        )
        points = _aggregate_points(base_points, "year")

    items = _filter_points(points, start, end, limit)
    if not items and not is_index and period == "day":
        snapshot_row = _snapshot_daily_row(normalized)
        if snapshot_row is not None:
            items = _filter_points(_points_from_rows([snapshot_row]), start, end, limit)
    if not items:
        items = local_items or cached_items
    if items:
        set_json(cache_key, [item.dict() for item in items], ttl=LIVE_CACHE_TTL)
    return items


def get_live_financials(
    symbol: str,
    *,
    limit: int = 50,
    offset: int = 0,
    period: str | None = None,
    min_revenue: float | None = None,
    min_net_income: float | None = None,
    sort: str = "desc",
):
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key(
        "live:financials",
        symbol=normalized,
        limit=limit,
        offset=offset,
        period=period,
        min_revenue=min_revenue,
        min_net_income=min_net_income,
        sort=sort,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        cached_items = cached["items"]
        if cached_items and _financial_rows_have_signal(cached_items):
            return cached_items, cached["total"]

    items, total = _load_db_financial_rows(
        normalized,
        limit=limit,
        offset=offset,
        period=period,
        min_revenue=min_revenue,
        min_net_income=min_net_income,
        sort=sort,
    )
    if items and _financial_rows_have_signal(items):
        set_json(cache_key, {"items": items, "total": total}, ttl=LIVE_CACHE_TTL)
        return items, total

    rows = get_recent_financials(normalized, count=max(limit + offset, 8))
    if period:
        rows = [row for row in rows if row.get("period") == period]
    if min_revenue is not None:
        rows = [row for row in rows if float(row.get("revenue", 0) or 0) >= min_revenue]
    if min_net_income is not None:
        rows = [row for row in rows if float(row.get("net_income", 0) or 0) >= min_net_income]
    rows.sort(key=lambda item: str(item.get("period", "")), reverse=sort != "asc")
    total = len(rows)
    items = rows[offset : offset + limit]
    if not items or not _financial_rows_have_signal(items):
        return [], 0
    if items and _financial_rows_have_signal(items):
        set_json(cache_key, {"items": items, "total": total}, ttl=LIVE_CACHE_TTL)
    return items, total


def get_live_fundamental(symbol: str) -> dict | None:
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key("live:fundamental", symbol=normalized)
    cached = get_json(cache_key)
    if isinstance(cached, dict) and _fundamental_payload_is_usable(cached):
        return cached

    rows, _ = _load_db_financial_rows(normalized, limit=4, offset=0, sort="desc")
    if not rows or not _financial_rows_have_signal(rows):
        rows = get_recent_financials(normalized, count=4)
    if not rows or not _financial_rows_have_signal(rows):
        return None
    current = rows[0]
    previous = rows[1] if len(rows) > 1 else rows[0]
    profit_quality = calc_profit_quality(current.get("net_income", 0), current.get("cash_flow", 0))
    growth = calc_growth(current.get("revenue", 0), previous.get("revenue", 0) or current.get("revenue", 0))
    risk = calc_risk(current.get("debt_ratio", 0), (current.get("debt_ratio", 0) or 0) * 100.0, 100.0)
    score = calc_fundamental_score(profit_quality, growth, risk)
    result = {
        "symbol": normalized,
        "score": float(score),
        "summary": (
            f"{normalized} 综合得分 {score:.1f}。"
            f"盈利质量 {profit_quality:.2f}，成长性 {growth:.2f}，风险项 {risk:.2f}。"
        ),
        "updated_at": datetime.now(),
    }
    if _fundamental_payload_is_usable(result):
        set_json(cache_key, item_to_dict(result), ttl=LIVE_CACHE_TTL)
    return result


def _filter_indicator_rows(rows: list[dict], *, start: date | None, end: date | None, limit: int) -> list[dict]:
    filtered = [
        row
        for row in rows
        if row.get("date") is not None
        and (start is None or _calendar_value(row["date"]) >= start)
        and (end is None or _calendar_value(row["date"]) <= end)
    ]
    return filtered[-limit:]


def _load_indicator_rows(
    symbol: str,
    *,
    indicator: str,
    window: int,
    limit: int,
    start: date | None,
    end: date | None,
) -> list[dict]:
    normalized = normalize_symbol(symbol)
    local_rows = _load_db_daily_rows(normalized, start=start, end=end)
    if local_rows:
        return _filter_indicator_rows(local_rows, start=start, end=end, limit=limit)

    required_count = max(limit + window * 4, 300)
    remote_rows = get_daily_history(normalized, count=required_count, as_of=end)
    return _filter_indicator_rows(remote_rows, start=start, end=end, limit=limit)


def _indicator_lines_and_params(indicator: str, window: int) -> tuple[list[str], dict[str, int | float | str]]:
    if indicator in {"ma", "sma", "ema", "wma", "rsi", "atr", "cci", "wr", "roc", "mom", "mfi"}:
        return [indicator], {"window": window}
    if indicator == "obv":
        return ["obv"], {}
    if indicator == "macd":
        return ["macd", "signal", "hist"], {"fast": 12, "slow": 26, "signal": 9}
    if indicator == "boll":
        return ["middle", "upper", "lower"], {"window": window, "stddev": 2.0}
    if indicator == "kdj":
        return ["k", "d", "j"], {"window": window, "k_smooth": 3, "d_smooth": 3}
    if indicator == "adx":
        return ["adx", "plus_di", "minus_di"], {"window": window}
    return [indicator], {"window": window}


def _calculate_indicator_payload(indicator: str, rows: list[dict], window: int) -> tuple[list[str], dict[str, int | float | str], dict[str, list[float]]]:
    closes = [float(row.get("close") or 0.0) for row in rows]
    highs = [float(row.get("high") or 0.0) for row in rows]
    lows = [float(row.get("low") or 0.0) for row in rows]
    volumes = [float(row.get("volume") or 0.0) for row in rows]
    lines, params = _indicator_lines_and_params(indicator, window)

    if indicator in {"ma", "sma"}:
        values = calc_ma(closes, window)
        return lines, params, {"ma" if indicator == "ma" else "sma": values}
    if indicator == "ema":
        return lines, params, {"ema": calc_ema(closes, window)}
    if indicator == "wma":
        return lines, params, {"wma": calc_wma(closes, window)}
    if indicator == "rsi":
        return lines, params, {"rsi": calc_rsi(closes, window)}
    if indicator == "macd":
        return lines, params, calc_macd(closes, fast=12, slow=26, signal=9)
    if indicator == "boll":
        return lines, params, calc_bollinger_bands(closes, window, num_std=2.0)
    if indicator == "kdj":
        return lines, params, calc_kdj(highs, lows, closes, window)
    if indicator == "atr":
        return lines, params, {"atr": calc_atr(highs, lows, closes, window)}
    if indicator == "cci":
        return lines, params, {"cci": calc_cci(highs, lows, closes, window)}
    if indicator == "wr":
        return lines, params, {"wr": calc_wr(highs, lows, closes, window)}
    if indicator == "obv":
        return lines, params, {"obv": calc_obv(closes, volumes)}
    if indicator == "roc":
        return lines, params, {"roc": calc_roc(closes, window)}
    if indicator == "mom":
        return lines, params, {"mom": calc_momentum(closes, window)}
    if indicator == "adx":
        return lines, params, calc_adx(highs, lows, closes, window)
    if indicator == "mfi":
        return lines, params, {"mfi": calc_mfi(highs, lows, closes, volumes, window)}
    return [indicator], {"window": window}, {indicator: calc_ma(closes, window)}


def get_live_indicator_series(
    symbol: str,
    indicator: str,
    *,
    window: int = 14,
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key(
        "live:indicator",
        symbol=normalized,
        indicator=indicator,
        window=window,
        limit=limit,
        start=start,
        end=end,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list):
        items = [IndicatorPoint(**item) for item in cached["items"] if isinstance(item, dict)]
        lines = [str(item) for item in cached.get("lines", []) if str(item)]
        params = dict(cached.get("params") or {})
        if items and lines:
            return items, lines, params, True

    indicator = indicator.lower()
    row_limit = max(limit + window * 4, 300)
    rows = _load_indicator_rows(
        normalized,
        indicator=indicator,
        window=window,
        limit=row_limit,
        start=start,
        end=end,
    )
    if not rows:
        return [], [], {}, False
    lines, params, series_payload = _calculate_indicator_payload(indicator, rows, window)
    items: list[IndicatorPoint] = []
    for idx, row in enumerate(rows):
        values = {
            line: float(series_payload.get(line, [0.0] * len(rows))[idx])
            for line in lines
            if idx < len(series_payload.get(line, []))
        }
        primary_line = lines[0] if lines else indicator
        items.append(
            IndicatorPoint(
                date=_calendar_value(row["date"]),
                value=float(values.get(primary_line, 0.0)) if primary_line in values else None,
                values=values,
            )
        )
    items = items[-limit:]
    set_json(
        cache_key,
        {"items": [item_to_dict(item) for item in items], "lines": lines, "params": params},
        ttl=LIVE_CACHE_TTL,
    )
    return items, lines, params, False


def get_live_risk_snapshot(symbol: str, *, window: int = 60) -> dict | None:
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key("live:risk:snapshot", symbol=normalized, window=window)
    cached = get_json(cache_key)
    if isinstance(cached, dict):
        payload = dict(cached)
        payload["cache_hit"] = True
        return payload

    points = get_live_kline(normalized, period="day", limit=window)
    if not points:
        return None
    closes = [float(point.close) for point in points]
    returns = [
        (closes[idx] - closes[idx - 1]) / closes[idx - 1]
        for idx in range(1, len(closes))
        if closes[idx - 1]
    ]
    payload = {
        "symbol": normalized,
        "max_drawdown": calc_max_drawdown(closes),
        "volatility": calc_volatility(returns),
        "as_of": points[-1].date,
        "cache_hit": False,
    }
    set_json(cache_key, item_to_dict(payload), ttl=LIVE_CACHE_TTL)
    return payload


def get_live_risk_series(
    symbol: str,
    *,
    window: int = 20,
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key(
        "live:risk:series",
        symbol=normalized,
        window=window,
        limit=limit,
        start=start,
        end=end,
    )
    cached = get_json(cache_key)
    if isinstance(cached, list):
        items = [RiskPoint(**item) for item in cached if isinstance(item, dict)]
        if items:
            return items, True

    points = get_live_kline(normalized, period="day", limit=limit, start=start, end=end)
    closes = [float(point.close) for point in points]
    if not closes:
        return [], False
    returns = [
        (closes[idx] - closes[idx - 1]) / closes[idx - 1]
        for idx in range(1, len(closes))
        if closes[idx - 1]
    ]
    items: list[RiskPoint] = []
    for idx, point in enumerate(points):
        window_start = max(0, idx - window + 1)
        window_prices = closes[window_start : idx + 1]
        window_returns = returns[window_start:idx] if idx > 0 else []
        items.append(
            RiskPoint(
                date=point.date,
                max_drawdown=calc_max_drawdown(window_prices),
                volatility=calc_volatility(window_returns),
            )
        )
    set_json(cache_key, [item.dict() for item in items], ttl=LIVE_CACHE_TTL)
    return items, False


def get_live_stock_research(symbol: str, *, report_limit: int = 10, forecast_limit: int = 10) -> dict:
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key(
        "live:research",
        symbol=normalized,
        report_limit=report_limit,
        forecast_limit=forecast_limit,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("reports"), list) and isinstance(
        cached.get("earning_forecasts"), list
    ):
        if cached.get("reports") or cached.get("earning_forecasts"):
            return cached

    local_payload = {
        "symbol": normalized,
        "reports": _load_db_stock_research(normalized, item_type="report", limit=report_limit),
        "earning_forecasts": _load_db_stock_research(normalized, item_type="earning_forecast", limit=forecast_limit),
    }
    if local_payload["reports"] or local_payload["earning_forecasts"]:
        set_json(cache_key, local_payload, ttl=LIVE_CACHE_TTL)
        return local_payload

    payload = {
        "symbol": normalized,
        "reports": get_stock_reports(normalized, limit=report_limit),
        "earning_forecasts": get_stock_earning_forecasts(normalized, limit=forecast_limit),
    }
    if payload["reports"] or payload["earning_forecasts"]:
        set_json(cache_key, payload, ttl=LIVE_CACHE_TTL)
    return payload
