from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import List
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.models.daily_prices import DailyPrice
from etl.loaders.redis_cache import cache_risk_series, cache_indicator
from etl.transformers.indicators import calc_max_drawdown, calc_volatility, calc_ma, calc_rsi
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _select_prices(db: Session, symbol: str, end: date | None, limit: int) -> List[DailyPrice]:
    query = db.query(DailyPrice).filter(DailyPrice.symbol == symbol)
    if end is not None:
        query = query.filter(DailyPrice.date <= end)
    return (
        query.order_by(DailyPrice.date.desc())
        .limit(limit)
        .all()[::-1]
    )


def write_risk_series_cache(db: Session, symbol: str, window: int = 20, limit: int = 200, end: date | None = None) -> None:
    rows = _select_prices(db, symbol, end, limit)
    if not rows:
        return
    closes = [float(row.close or 0) for row in rows]
    returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1]
    ]
    items = []
    for idx in range(len(rows)):
        start = max(0, idx - window + 1)
        window_prices = closes[start : idx + 1]
        window_returns = returns[start:idx] if idx > 0 else []
        items.append(
            {
                "date": rows[idx].date,
                "max_drawdown": calc_max_drawdown(window_prices),
                "volatility": calc_volatility(window_returns),
            }
        )
    cache_risk_series(symbol, {"symbol": symbol, "items": items}, window=window, limit=limit, end=end)


def write_indicator_cache(
    db: Session,
    symbol: str,
    indicator: str,
    window: int = 14,
    limit: int = 200,
    end: date | None = None,
) -> None:
    rows = _select_prices(db, symbol, end, limit)
    if not rows:
        return
    closes = [float(row.close or 0) for row in rows]
    if indicator == "ma":
        values = calc_ma(closes, window)
    elif indicator == "rsi":
        values = calc_rsi(closes, window)
    else:
        return
    items = [
        {"date": row.date, "value": float(value)}
        for row, value in zip(rows, values)
    ]
    cache_indicator(
        symbol,
        indicator,
        {"symbol": symbol, "indicator": indicator, "window": window, "items": items},
        window=window,
        limit=limit,
        end=end,
    )


def list_symbols(db: Session, limit: int = 200) -> list[str]:
    rows = db.query(DailyPrice.symbol).group_by(DailyPrice.symbol).limit(limit).all()
    return [row[0] for row in rows]


def list_updated_symbols(db: Session, as_of: date) -> list[str]:
    rows = (
        db.query(DailyPrice.symbol)
        .filter(DailyPrice.date == as_of)
        .group_by(DailyPrice.symbol)
        .order_by(DailyPrice.symbol.asc())
        .all()
    )
    return [row[0] for row in rows]


def _write_symbol_caches(db: Session, symbol: str, *, end: date | None = None) -> None:
    write_risk_series_cache(db, symbol, end=end)
    write_indicator_cache(db, symbol, "ma", window=20, end=end)
    write_indicator_cache(db, symbol, "rsi", window=14, end=end)


def _run_symbol_metrics(session_factory, symbol: str, end: date | None) -> str:
    db = session_factory()
    try:
        _write_symbol_caches(db, symbol, end=end)
        return symbol
    finally:
        db.close()


def run_metrics_cache_job(
    database_url: str,
    symbols: list[str],
    *,
    end: date | None = None,
    workers: int | None = None,
) -> int:
    unique_symbols: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = str(symbol).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_symbols.append(normalized)
    if not unique_symbols:
        return 0

    max_workers = max(1, workers or int(os.getenv("METRICS_CACHE_WORKERS", "4")))
    engine = create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    processed = 0
    try:
        if max_workers <= 1 or len(unique_symbols) == 1:
            for symbol in unique_symbols:
                _run_symbol_metrics(session_factory, symbol, end)
                processed += 1
            return processed

        LOGGER.info("metrics_cache_job workers=%s symbols=%s end=%s", max_workers, len(unique_symbols), end)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(_run_symbol_metrics, session_factory, symbol, end): symbol
                for symbol in unique_symbols
            }
            for done, future in enumerate(as_completed(future_map), start=1):
                symbol = future_map[future]
                try:
                    future.result()
                    processed += 1
                except Exception as exc:
                    LOGGER.warning("metrics_cache_job failed [%s]: %s", symbol, exc)
                if done % 100 == 0 or done >= len(unique_symbols):
                    LOGGER.info("metrics_cache_job progress %s/%s end=%s", done, len(unique_symbols), end)
        return processed
    finally:
        engine.dispose()
