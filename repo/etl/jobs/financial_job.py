from __future__ import annotations

from datetime import date, timedelta

from etl.fetchers.market_client import get_stock_basic, get_financials
from etl.loaders.pg_loader import get_latest_financial_periods, upsert_financials, upsert_fundamental_score
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


def _latest_quarter_period(as_of: date) -> str:
    month = ((as_of.month - 1) // 3 + 1) * 3
    quarter_end_year = as_of.year
    quarter_end = date(quarter_end_year, month, 1)
    if month == 12:
        quarter_end = quarter_end.replace(day=31)
    else:
        quarter_end = date(quarter_end.year, quarter_end.month + 1, 1) - timedelta(days=1)
    if quarter_end > as_of:
        month -= 3
        if month <= 0:
            month += 12
            quarter_end_year -= 1
    return f"{quarter_end_year:04d}{month:02d}"


def run_financial_job(start: date, end: date) -> int:
    """Run financial job: fetch financials, calculate score, store into DB (incremental)."""
    total = 0
    symbols = _iter_symbols()
    latest_periods = get_latest_financial_periods(symbols)
    for as_of in date_range(start, end):
        target_period = _latest_quarter_period(as_of)
        financial_payload: list[dict] = []
        score_payload: list[dict] = []
        for symbol in symbols:
            latest_period = str(latest_periods.get(symbol) or "")
            if latest_period and latest_period >= target_period:
                continue

            data = get_financials(symbol, period=target_period)
            if not data:
                continue
            actual_period = str(data.get("period") or "")
            if latest_period and actual_period and actual_period <= latest_period:
                continue

            financial_rows = normalize_financials([data])
            if not financial_rows:
                continue
            financial_payload.extend(financial_rows)

            profit_quality = calc_profit_quality(data.get("net_income", 0), data.get("cash_flow", 0))
            growth = calc_growth(data.get("revenue", 0), data.get("revenue", 0) * 0.9)
            risk = calc_risk(data.get("debt_ratio", 0), short_debt=50_000_000, cash=100_000_000)
            score = calc_fundamental_score(profit_quality, growth, risk)

            summary = generate_summary(symbol, score, profit_quality, growth, risk)
            score_payload.append(build_fundamental_score_row(symbol, score, summary, as_of))
            if actual_period:
                latest_periods[symbol] = actual_period

        if financial_payload:
            upsert_financials(financial_payload)
        if score_payload:
            total += upsert_fundamental_score(score_payload)
        if not financial_payload:
            LOGGER.info("financial_job up-to-date for %s target_period=%s", as_of, target_period)

    return total
