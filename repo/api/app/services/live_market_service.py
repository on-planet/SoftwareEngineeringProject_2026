from __future__ import annotations

from datetime import date, datetime
import os
from typing import Iterable, Literal

from app.core.cache import get_json, set_json
from app.core.db import SessionLocal
from app.models.daily_prices import DailyPrice
from app.models.financials import Financial
from app.schemas.indicators import IndicatorPoint
from app.schemas.kline import KlinePoint
from app.schemas.risk_series import RiskPoint
from app.services.cache_utils import build_cache_key, item_to_dict
from app.utils.symbols import normalize_symbol, symbol_lookup_aliases
from etl.fetchers.market_client import get_stock_basic as get_cached_stock_basic
from etl.fetchers.snowball_client import (
    get_market_stock_pool,
    get_kline_history,
    get_recent_financials,
    get_stock_earning_forecasts,
    get_stock_basics,
    get_stock_pankou,
    get_stock_quote,
    get_stock_quote_detail,
    get_stock_reports,
    normalize_index_symbol,
    market_from_symbol,
    search_stocks,
)
from etl.transformers.fundamentals import calc_fundamental_score, calc_growth, calc_profit_quality, calc_risk
from etl.transformers.indicators import calc_ma, calc_max_drawdown, calc_rsi, calc_volatility
from etl.utils.env import load_project_env

load_project_env()

LiveKlinePeriod = Literal["1m", "30m", "60m", "day", "week", "month", "quarter", "year"]
LIVE_CACHE_TTL = max(60, int(os.getenv("API_LIVE_CACHE_TTL", "1800")))
A_SHARE_SH_PREFIXES = ("600", "601", "603", "605", "688", "689", "900")
A_SHARE_SZ_PREFIXES = ("000", "001", "002", "003", "200", "300", "301")


def _looks_like_equity_symbol(symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    if normalized.endswith(".HK"):
        return normalized[:-3].isdigit()
    if normalized.endswith(".SH"):
        return normalized[:-3].isdigit() and normalized[:-3].startswith(A_SHARE_SH_PREFIXES)
    if normalized.endswith(".SZ"):
        return normalized[:-3].isdigit() and normalized[:-3].startswith(A_SHARE_SZ_PREFIXES)
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


def _filter_stock_rows(rows: Iterable[dict], *, market: str | None = None, keyword: str | None = None) -> list[dict]:
    normalized_rows = _dedupe_stock_rows(rows)
    keyword_text = keyword.strip().lower() if keyword else None
    output: list[dict] = []
    for row in normalized_rows:
        row_market = str(row.get("market") or "").upper()
        if market and row_market != market:
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


def _fallback_stock_rows(*, market: str | None = None, keyword: str | None = None, limit: int = 100) -> list[dict]:
    rows = get_cached_stock_basic(allow_stale_cache=True)
    filtered = _filter_stock_rows(rows, market=market, keyword=keyword)
    return filtered[:limit]


def _merge_stock_rows(primary: Iterable[dict], fallback: Iterable[dict], *, limit: int) -> list[dict]:
    fallback_by_symbol = {row["symbol"]: row for row in _dedupe_stock_rows(fallback)}
    merged: list[dict] = []
    seen: set[str] = set()

    for row in _dedupe_stock_rows(primary):
        symbol = row["symbol"]
        fallback_row = fallback_by_symbol.get(symbol, {})
        merged_row = dict(row)
        if not merged_row.get("name") or str(merged_row.get("name")) == symbol:
            merged_row["name"] = fallback_row.get("name") or symbol
        if not merged_row.get("sector") or str(merged_row.get("sector")) in {"", "Unknown"}:
            merged_row["sector"] = fallback_row.get("sector") or "Unknown"
        if not merged_row.get("market"):
            merged_row["market"] = fallback_row.get("market") or market_from_symbol(symbol)
        merged.append(merged_row)
        seen.add(symbol)

    for row in _dedupe_stock_rows(fallback):
        if row["symbol"] in seen:
            continue
        merged.append(row)
        seen.add(row["symbol"])
        if len(merged) >= limit:
            break
    return merged[:limit]


def _fallback_stock_profile(symbol: str) -> dict:
    rows = get_cached_stock_basic([symbol], allow_stale_cache=True)
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


def list_live_stocks(
    *,
    market: str | None = None,
    keyword: str | None = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "asc",
):
    normalized_market = market.upper() if market else None
    keyword_text = keyword.strip() if keyword else None
    normalized_keyword = keyword.strip().lower() if keyword else None
    cache_key = build_cache_key(
        "live:stocks",
        market=normalized_market,
        keyword=normalized_keyword,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        return cached["items"], cached["total"]

    target_size = max(limit + offset, 100)
    fallback_rows = _fallback_stock_rows(market=normalized_market, keyword=keyword_text, limit=target_size)
    if keyword_text:
        items = search_stocks(keyword_text, market=normalized_market, limit=target_size)
    elif normalized_market in {"A", "HK", "US"}:
        items = get_market_stock_pool(normalized_market, limit=target_size)
    else:
        items = get_market_stock_pool("A", limit=target_size) + get_market_stock_pool("HK", limit=target_size)

    items = _merge_stock_rows(items, fallback_rows, limit=target_size)
    items.sort(key=lambda item: str(item.get("symbol", "")), reverse=sort == "desc")
    total = len(items)
    payload = items[offset : offset + limit]
    set_json(cache_key, {"items": payload, "total": total}, ttl=LIVE_CACHE_TTL)
    return payload, total


def get_live_stock_profile(symbol: str) -> dict | None:
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key("live:stock:profile", symbol=normalized)
    cached = get_json(cache_key)
    if isinstance(cached, dict) and _has_quote_signal(cached):
        return cached

    fallback_profile = _fallback_stock_profile(normalized)
    rows = get_stock_basics([normalized])
    result = _merge_stock_profile(dict(rows[0]) if rows else None, fallback_profile)
    quote = get_stock_quote(normalized)
    quote_detail = get_stock_quote_detail(normalized)
    pankou = get_stock_pankou(normalized)
    if quote:
        result["quote"] = {key: value for key, value in quote.items() if key != "symbol"}
    if quote_detail:
        result["quote_detail"] = {key: value for key, value in quote_detail.items() if key != "symbol"}
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


def get_live_stock_daily(
    symbol: str,
    *,
    start: date | None = None,
    end: date | None = None,
    sort: str = "asc",
    min_volume: float | None = None,
) -> list[dict]:
    normalized = normalize_symbol(symbol)
    count = 1200 if start else 360
    rows = get_kline_history(normalized, period="day", count=count, as_of=end, is_index=False)
    if not rows:
        rows = _load_db_daily_rows(normalized, start=start, end=end)
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
    if isinstance(cached, list):
        items = [KlinePoint(**item) for item in cached if isinstance(item, dict)]
        if items:
            return items

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
        base_points = _points_from_rows(
            get_kline_history(normalized, period="month", count=max(limit * 3 + 6, 36), as_of=end, is_index=is_index)
        )
        points = _aggregate_points(base_points, "quarter")
    else:
        base_points = _points_from_rows(
            get_kline_history(normalized, period="month", count=max(limit * 12 + 12, 120), as_of=end, is_index=is_index)
        )
        points = _aggregate_points(base_points, "year")

    items = _filter_points(points, start, end, limit)
    if not items and not is_index and period in {"day", "week", "month", "quarter", "year"}:
        db_points = _points_from_rows(_load_db_daily_rows(normalized, start=start, end=end))
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
        items = _filter_points(points, start, end, limit)
    if not items and not is_index and period == "day":
        snapshot_row = _snapshot_daily_row(normalized)
        if snapshot_row is not None:
            items = _filter_points(_points_from_rows([snapshot_row]), start, end, limit)
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
        items, total = _load_db_financial_rows(
            normalized,
            limit=limit,
            offset=offset,
            period=period,
            min_revenue=min_revenue,
            min_net_income=min_net_income,
            sort=sort,
        )
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

    rows = get_recent_financials(normalized, count=4)
    if not rows or not _financial_rows_have_signal(rows):
        rows, _ = _load_db_financial_rows(normalized, limit=4, offset=0, sort="desc")
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
    if isinstance(cached, list):
        items = [IndicatorPoint(**item) for item in cached if isinstance(item, dict)]
        if items:
            return items, True

    points = get_live_kline(normalized, period="day", limit=max(limit, window * 8), start=start, end=end)
    closes = [float(point.close) for point in points]
    if not closes:
        return [], False
    values = calc_ma(closes, window) if indicator == "ma" else calc_rsi(closes, window)
    items = [IndicatorPoint(date=point.date, value=float(value)) for point, value in zip(points, values)][-limit:]
    set_json(cache_key, [item.dict() for item in items], ttl=LIVE_CACHE_TTL)
    return items, False


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

    payload = {
        "symbol": normalized,
        "reports": get_stock_reports(normalized, limit=report_limit),
        "earning_forecasts": get_stock_earning_forecasts(normalized, limit=forecast_limit),
    }
    if payload["reports"] or payload["earning_forecasts"]:
        set_json(cache_key, payload, ttl=LIVE_CACHE_TTL)
    return payload
