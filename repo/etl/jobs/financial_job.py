from __future__ import annotations

from datetime import date

from etl.fetchers.stock_basic_client import get_stock_basic
from etl.fetchers.tushare_client import get_financials
from etl.loaders.pg_loader import upsert_financials, upsert_fundamental_score
from etl.transformers.fundamentals import (
    build_fundamental_score_row,
    calc_profit_quality,
    calc_growth,
    calc_risk,
    calc_fundamental_score,
    normalize_financials,
)
from etl.utils.dates import date_range
from etl.utils.llm_summary import generate_summary
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _iter_symbols() -> list[str]:
    rows = get_stock_basic()
    symbols = [row.get("symbol") for row in rows if row.get("symbol")]
    return symbols or ["000001.SH"]


def run_financial_job(start: date, end: date) -> int:
    """Run financial job: fetch financials, calculate score, store into DB (incremental)."""
    total = 0
    symbols = _iter_symbols()
    for as_of in date_range(start, end):
        period = as_of.strftime("%Y%m")
        for symbol in symbols:
            data = get_financials(symbol, period=period)
            if not data:
                continue
            financial_rows = normalize_financials([data])
            upsert_financials(financial_rows)

            profit_quality = calc_profit_quality(data.get("net_income", 0), data.get("cash_flow", 0))
            growth = calc_growth(data.get("revenue", 0), data.get("revenue", 0) * 0.9)
            risk = calc_risk(data.get("debt_ratio", 0), short_debt=50_000_000, cash=100_000_000)
            score = calc_fundamental_score(profit_quality, growth, risk)

            summary = generate_summary(symbol, score, profit_quality, growth, risk)
            score_row = build_fundamental_score_row(symbol, score, summary, as_of)
            total += upsert_fundamental_score([score_row])

        if not total:
            LOGGER.info("financial_job empty for %s", as_of)

    return total
