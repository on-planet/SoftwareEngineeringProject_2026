from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
import os
import time

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
FINANCIAL_JOB_WORKERS = max(1, int(os.getenv("FINANCIAL_JOB_WORKERS", "8")))


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


def _fetch_symbol_financial_payload(symbol: str, target_period: str, latest_period: str, as_of: date) -> tuple[list[dict], dict | None, str]:
    if latest_period and latest_period >= target_period:
        return [], None, latest_period

    data = get_financials(symbol, period=target_period)
    if not data:
        return [], None, latest_period
    actual_period = str(data.get("period") or "")
    if latest_period and actual_period and actual_period <= latest_period:
        return [], None, latest_period

    financial_rows = normalize_financials([data])
    if not financial_rows:
        return [], None, latest_period

    profit_quality = calc_profit_quality(data.get("net_income", 0), data.get("cash_flow", 0))
    growth = calc_growth(data.get("revenue", 0), data.get("revenue", 0) * 0.9)
    risk = calc_risk(data.get("debt_ratio", 0), short_debt=50_000_000, cash=100_000_000)
    score = calc_fundamental_score(profit_quality, growth, risk)
    summary = generate_summary(symbol, score, profit_quality, growth, risk)
    score_row = build_fundamental_score_row(symbol, score, summary, as_of)
    return financial_rows, score_row, actual_period or latest_period


def run_financial_job(start: date, end: date) -> int:
    """Run financial job: fetch financials, calculate score, store into DB (incremental)."""
    total = 0
    symbols = _iter_symbols()
    latest_periods = get_latest_financial_periods(symbols)
    LOGGER.info("financial_job start symbols=%s workers=%s", len(symbols), FINANCIAL_JOB_WORKERS)
    for as_of in date_range(start, end):
        loop_start = time.perf_counter()
        target_period = _latest_quarter_period(as_of)
        financial_payload: list[dict] = []
        score_payload: list[dict] = []
        pending_symbols = [
            symbol
            for symbol in symbols
            if not str(latest_periods.get(symbol) or "") or str(latest_periods.get(symbol) or "") < target_period
        ]
        if pending_symbols:
            workers = max(1, min(FINANCIAL_JOB_WORKERS, len(pending_symbols)))
            done = 0
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="financial_job") as executor:
                future_map = {
                    executor.submit(
                        _fetch_symbol_financial_payload,
                        symbol,
                        target_period,
                        str(latest_periods.get(symbol) or ""),
                        as_of,
                    ): symbol
                    for symbol in pending_symbols
                }
                for future in as_completed(future_map):
                    symbol = future_map[future]
                    done += 1
                    try:
                        rows, score_row, actual_period = future.result()
                    except Exception as exc:
                        LOGGER.warning("financial_job failed [%s %s]: %s", symbol, target_period, exc)
                        continue
                    if rows:
                        financial_payload.extend(rows)
                    if score_row:
                        score_payload.append(score_row)
                    if actual_period:
                        latest_periods[symbol] = actual_period
                    if done % 200 == 0 or done >= len(pending_symbols):
                        LOGGER.info("financial_job progress %s/%s period=%s date=%s", done, len(pending_symbols), target_period, as_of)

        if financial_payload:
            upsert_financials(financial_payload)
        if score_payload:
            total += upsert_fundamental_score(score_payload)
        if not financial_payload:
            LOGGER.info("financial_job up-to-date for %s target_period=%s", as_of, target_period)
        else:
            LOGGER.info(
                "financial_job %s period=%s financial_rows=%s score_rows=%s cost=%.2fs",
                as_of,
                target_period,
                len(financial_payload),
                len(score_payload),
                time.perf_counter() - loop_start,
            )

    return total
