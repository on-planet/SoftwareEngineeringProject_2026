from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Literal

from app.core.cache import get_json, set_json
from app.schemas.indicators import IndicatorPoint
from app.schemas.kline import KlinePoint
from app.schemas.risk_series import RiskPoint
from app.services.cache_utils import build_cache_key, item_to_dict
from app.utils.symbols import normalize_symbol
from etl.fetchers.snowball_client import (
    get_market_stock_pool,
    get_kline_history,
    get_recent_financials,
    get_stock_earning_forecasts,
    get_stock_basics,
    get_stock_reports,
    market_from_symbol,
    search_stocks,
)
from etl.transformers.fundamentals import calc_fundamental_score, calc_growth, calc_profit_quality, calc_risk
from etl.transformers.indicators import calc_ma, calc_max_drawdown, calc_rsi, calc_volatility
from etl.utils.env import load_project_env

load_project_env()

LiveKlinePeriod = Literal["day", "week", "month", "quarter", "year"]
LIVE_CACHE_TTL = 300


def _period_key(value: date, period: LiveKlinePeriod) -> tuple[int, int]:
    if period == "week":
        iso_year, iso_week, _ = value.isocalendar()
        return iso_year, iso_week
    if period == "month":
        return value.year, value.month
    if period == "quarter":
        return value.year, (value.month - 1) // 3 + 1
    if period == "year":
        return value.year, 1
    return value.year, value.toordinal()


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
        if (start is None or item.date >= start) and (end is None or item.date <= end)
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
    if keyword_text:
        items = search_stocks(keyword_text, market=normalized_market, limit=target_size)
    elif normalized_market in {"A", "HK", "US"}:
        items = get_market_stock_pool(normalized_market, limit=target_size)
    else:
        items = get_market_stock_pool("A", limit=target_size) + get_market_stock_pool("HK", limit=target_size)

    items.sort(key=lambda item: str(item.get("symbol", "")), reverse=sort == "desc")
    total = len(items)
    payload = items[offset : offset + limit]
    set_json(cache_key, {"items": payload, "total": total}, ttl=LIVE_CACHE_TTL)
    return payload, total


def get_live_stock_profile(symbol: str) -> dict | None:
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key("live:stock:profile", symbol=normalized)
    cached = get_json(cache_key)
    if isinstance(cached, dict):
        return cached

    rows = get_stock_basics([normalized])
    if rows:
        result = rows[0]
    else:
        return None
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
    normalized = normalize_symbol(symbol)
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

    if period in {"day", "week", "month"}:
        fetch_count = max(limit * (3 if period == "day" else 2), 160)
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
        return cached["items"], cached["total"]

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
    set_json(cache_key, {"items": items, "total": total}, ttl=LIVE_CACHE_TTL)
    return items, total


def get_live_fundamental(symbol: str) -> dict | None:
    normalized = normalize_symbol(symbol)
    cache_key = build_cache_key("live:fundamental", symbol=normalized)
    cached = get_json(cache_key)
    if isinstance(cached, dict):
        return cached

    rows = get_recent_financials(normalized, count=4)
    if not rows:
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
            f"{normalized} score {score:.1f}. "
            f"Profit quality {profit_quality:.2f}, growth {growth:.2f}, risk {risk:.2f}."
        ),
        "updated_at": datetime.now(),
    }
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
        return cached

    payload = {
        "symbol": normalized,
        "reports": get_stock_reports(normalized, limit=report_limit),
        "earning_forecasts": get_stock_earning_forecasts(normalized, limit=forecast_limit),
    }
    set_json(cache_key, payload, ttl=LIVE_CACHE_TTL)
    return payload
