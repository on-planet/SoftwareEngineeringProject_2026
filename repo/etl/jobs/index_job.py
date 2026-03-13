from __future__ import annotations

from datetime import date

from etl.fetchers.stock_basic_client import get_stock_basic
from etl.fetchers.tushare_client import get_index_daily, get_daily_prices
from etl.loaders.pg_loader import upsert_stocks, upsert_indices, upsert_daily_prices
from etl.loaders.redis_cache import cache_heatmap, cache_risk
from etl.transformers.heatmap import build_heatmap, normalize_daily_rows
from etl.transformers.indicators import calc_max_drawdown, calc_volatility
from etl.utils.dates import date_range
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _infer_market(symbol: str | None) -> str | None:
    if not symbol:
        return None
    if symbol.endswith(".HK"):
        return "HK"
    if symbol.endswith(".SH") or symbol.endswith(".SZ"):
        return "A"
    return None


def run_index_job(start: date, end: date) -> int:
    """Run index job: fetch indices and store into DB (incremental)."""
    stock_rows = get_stock_basic()
    upsert_stocks(stock_rows)
    stock_meta = {row.get("symbol"): row for row in stock_rows}
    price_history: dict[str, list[float]] = {}

    total = 0
    for as_of in date_range(start, end):
        index_rows = get_index_daily(as_of)
        if not index_rows:
            LOGGER.info("index_job empty for %s", as_of)
            continue
        upsert_indices(index_rows)

        symbols = [row["symbol"] for row in index_rows]
        daily_rows_raw = get_daily_prices(symbols, as_of)
        daily_rows = normalize_daily_rows(daily_rows_raw)
        if daily_rows:
            upsert_daily_prices(daily_rows)
        total += len(daily_rows)

        closes = [row["close"] for row in daily_rows]
        returns = []
        for i in range(1, len(closes)):
            if closes[i - 1] == 0:
                continue
            returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
        risk_payload = {
            "max_drawdown": calc_max_drawdown(closes),
            "volatility": calc_volatility(returns),
            "as_of": as_of,
        }
        cache_risk("ALL", risk_payload)

        for row in daily_rows:
            symbol = row.get("symbol")
            if not symbol:
                continue
            series = price_history.setdefault(symbol, [])
            series.append(float(row.get("close", 0) or 0))
            series = series[-60:]
            price_history[symbol] = series
            returns = [
                (series[i] - series[i - 1]) / series[i - 1]
                for i in range(1, len(series))
                if series[i - 1]
            ]
            cache_risk(
                symbol,
                {
                    "symbol": symbol,
                    "max_drawdown": calc_max_drawdown(series),
                    "volatility": calc_volatility(returns),
                    "as_of": as_of,
                },
            )

        heatmap_input = []
        for row in daily_rows:
            symbol = row.get("symbol")
            meta = stock_meta.get(symbol) or {}
            market = meta.get("market") or _infer_market(symbol)
            heatmap_input.append(
                {
                    "sector": meta.get("sector") or "未知",
                    "market": market,
                    "close": row.get("close", 0),
                    "change": row.get("close", 0) - row.get("open", 0),
                }
            )
        heatmap_rows = build_heatmap(heatmap_input)
        heatmap_payload = {"date": as_of.isoformat(), "items": heatmap_rows}
        cache_heatmap(as_of, heatmap_payload)

    return total
