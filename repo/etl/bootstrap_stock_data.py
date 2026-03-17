from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

from etl.fetchers.market_client import get_stock_basic, market_data_session
from etl.fetchers.snowball_client import (
    get_daily_history,
    get_financials,
    get_index_history,
    get_market_stock_pool,
    market_from_symbol,
)
from etl.loaders.pg_loader import (
    upsert_daily_prices,
    upsert_financials,
    upsert_fundamental_score,
    upsert_stocks,
)
from etl.transformers.fundamentals import (
    build_fundamental_score_row,
    calc_fundamental_score,
    calc_growth,
    calc_profit_quality,
    calc_risk,
)
from etl.utils.env import load_project_env
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)
INDEX_SYMBOLS = ["000001.SH", "399001.SZ", "399006.SZ"]
STATE_DIR = Path(__file__).resolve().parents[1] / "state"
CHECKPOINT_PATH = STATE_DIR / "bootstrap_stock_data_checkpoint.json"
load_project_env()


def _latest_market_date(as_of: date | None = None) -> date:
    target = as_of or date.today()
    while target.weekday() >= 5:
        target -= timedelta(days=1)
    return target


def _quarter_end_periods(as_of: date, count: int) -> list[str]:
    month = ((as_of.month - 1) // 3 + 1) * 3
    quarter_end = date(as_of.year, month, 1)
    if month == 12:
        quarter_end = quarter_end.replace(day=31)
    else:
        quarter_end = (date(quarter_end.year, quarter_end.month + 1, 1) - timedelta(days=1))
    if quarter_end > as_of:
        month -= 3
        if month <= 0:
            month += 12
            year = as_of.year - 1
        else:
            year = as_of.year
        quarter_end = date(year, month, 1)
        if month == 12:
            quarter_end = quarter_end.replace(day=31)
        else:
            quarter_end = (date(quarter_end.year, quarter_end.month + 1, 1) - timedelta(days=1))

    periods: list[str] = []
    current = quarter_end
    for _ in range(max(1, count)):
        periods.append(f"{current.year:04d}{current.month:02d}")
        month = current.month - 3
        year = current.year
        if month <= 0:
            month += 12
            year -= 1
        current = date(year, month, 1)
        if month == 12:
            current = current.replace(day=31)
        else:
            current = date(current.year, current.month + 1, 1) - timedelta(days=1)
    return periods


def _seed_stock_rows(symbols: list[str]) -> list[dict]:
    return [
        {
            "symbol": symbol,
            "name": symbol,
            "market": market_from_symbol(symbol),
            "sector": "Unknown",
        }
        for symbol in symbols
    ]


def _merge_stock_rows(symbols: list[str], fetched_rows: list[dict]) -> list[dict]:
    by_symbol = {row.get("symbol"): row for row in fetched_rows if row.get("symbol")}
    rows: list[dict] = []
    for symbol in symbols:
        row = by_symbol.get(symbol)
        if row:
            rows.append(row)
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": symbol,
                "market": market_from_symbol(symbol),
                "sector": "Unknown",
            }
        )
    return rows


def _build_summary(symbol: str, score: float, profit_quality: float, growth: float, risk: float) -> str:
    return (
        f"{symbol} score {score:.1f}. "
        f"Profit quality {profit_quality:.2f}, growth {growth:.2f}, risk {risk:.2f}."
    )


def _upsert_latest_fundamental(symbol: str, rows: list[dict], as_of: date) -> int:
    if not rows:
        return 0
    ordered = sorted(rows, key=lambda item: item["period"], reverse=True)
    current = ordered[0]
    previous = ordered[1] if len(ordered) > 1 else current
    profit_quality = calc_profit_quality(current.get("net_income", 0), current.get("cash_flow", 0))
    growth = calc_growth(current.get("revenue", 0), previous.get("revenue", 0) or current.get("revenue", 0))
    risk = calc_risk(current.get("debt_ratio", 0), (current.get("debt_ratio", 0) or 0) * 100.0, 100.0)
    score = calc_fundamental_score(profit_quality, growth, risk)
    summary = _build_summary(symbol, score, profit_quality, growth, risk)
    return upsert_fundamental_score([build_fundamental_score_row(symbol, score, summary, as_of)])


def _checkpoint_signature(
    *,
    target_date: date,
    daily_count: int,
    financial_periods: int,
    a_count: int,
    hk_count: int,
) -> str:
    payload = {
        "target_date": target_date.isoformat(),
        "daily_count": daily_count,
        "financial_periods": financial_periods,
        "a_count": a_count,
        "hk_count": hk_count,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _load_checkpoint(signature: str) -> dict | None:
    if not CHECKPOINT_PATH.exists():
        return None
    try:
        payload = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("bootstrap_stock_data checkpoint load failed [%s]: %s", CHECKPOINT_PATH, exc)
        return None
    if str(payload.get("signature") or "") != signature:
        return None
    return payload if isinstance(payload, dict) else None


def _save_checkpoint(
    signature: str,
    *,
    target_symbols: list[str],
    periods: list[str],
    next_symbol_index: int,
    index_done: bool,
) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "signature": signature,
        "target_symbols": target_symbols,
        "periods": periods,
        "next_symbol_index": max(0, next_symbol_index),
        "index_done": bool(index_done),
        "updated_at": date.today().isoformat(),
    }
    CHECKPOINT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clear_checkpoint(signature: str | None = None) -> None:
    if not CHECKPOINT_PATH.exists():
        return
    if signature is None:
        try:
            CHECKPOINT_PATH.unlink()
        except OSError:
            return
        return
    payload = _load_checkpoint(signature)
    if payload is None:
        return
    try:
        CHECKPOINT_PATH.unlink()
    except OSError:
        return


def run_bootstrap(
    *,
    as_of: date | None = None,
    daily_count: int = 480,
    financial_periods: int = 8,
    a_count: int = 100,
    hk_count: int = 100,
    resume: bool = True,
    reset_progress: bool = False,
) -> dict[str, int]:
    target_date = _latest_market_date(as_of)
    signature = _checkpoint_signature(
        target_date=target_date,
        daily_count=daily_count,
        financial_periods=financial_periods,
        a_count=a_count,
        hk_count=hk_count,
    )
    if reset_progress:
        _clear_checkpoint()
    checkpoint = _load_checkpoint(signature) if resume else None
    if checkpoint:
        target_symbols = [str(item) for item in checkpoint.get("target_symbols") or [] if str(item).strip()]
        periods = [str(item) for item in checkpoint.get("periods") or [] if str(item).strip()]
        try:
            start_index = max(0, int(checkpoint.get("next_symbol_index") or 0))
        except Exception:
            start_index = 0
        index_done = bool(checkpoint.get("index_done"))
        LOGGER.info(
            "bootstrap stock data resume symbols=%s next_symbol_index=%s index_done=%s",
            len(target_symbols),
            start_index,
            index_done,
        )
    else:
        target_symbols = [
            row["symbol"]
            for row in get_market_stock_pool("A", limit=a_count) + get_market_stock_pool("HK", limit=hk_count)
            if row.get("symbol")
        ]
        periods = _quarter_end_periods(target_date, financial_periods)
        start_index = 0
        index_done = False
        if resume:
            _save_checkpoint(
                signature,
                target_symbols=target_symbols,
                periods=periods,
                next_symbol_index=0,
                index_done=False,
            )

    LOGGER.info(
        "bootstrap stock data start date=%s symbols=%s daily_count=%s financial_periods=%s resume_from=%s index_done=%s",
        target_date,
        len(target_symbols),
        daily_count,
        financial_periods,
        start_index,
        index_done,
    )

    counters = {"stocks": 0, "daily_prices": 0, "financials": 0, "fundamental_scores": 0, "index_prices": 0}

    upsert_stocks(_seed_stock_rows(target_symbols))
    counters["stocks"] += len(target_symbols)

    with market_data_session():
        fetched_rows = get_stock_basic(target_symbols)
        stock_rows = _merge_stock_rows(target_symbols, fetched_rows)
        counters["stocks"] += upsert_stocks(stock_rows)

        if not index_done:
            for index_symbol in INDEX_SYMBOLS:
                index_rows = get_index_history(index_symbol, count=daily_count, as_of=target_date)
                if index_rows:
                    counters["index_prices"] += upsert_daily_prices(index_rows)
            if resume:
                _save_checkpoint(
                    signature,
                    target_symbols=target_symbols,
                    periods=periods,
                    next_symbol_index=start_index,
                    index_done=True,
                )

        total_symbols = len(target_symbols)
        if start_index >= total_symbols:
            LOGGER.info("bootstrap stock data checkpoint already complete symbols=%s", total_symbols)
        for idx in range(start_index, total_symbols):
            symbol = target_symbols[idx]
            history_rows = get_daily_history(symbol, count=daily_count, as_of=target_date)
            if history_rows:
                counters["daily_prices"] += upsert_daily_prices(history_rows)

            financial_rows_by_period: dict[str, dict] = {}
            for period in periods:
                row = get_financials(symbol, period)
                period_key = row.get("period") if row else None
                if row and period_key:
                    financial_rows_by_period[str(period_key)] = row
            financial_rows = sorted(financial_rows_by_period.values(), key=lambda item: item["period"], reverse=True)
            if financial_rows:
                counters["financials"] += upsert_financials(financial_rows)
                counters["fundamental_scores"] += _upsert_latest_fundamental(symbol, financial_rows, target_date)
            if resume:
                _save_checkpoint(
                    signature,
                    target_symbols=target_symbols,
                    periods=periods,
                    next_symbol_index=idx + 1,
                    index_done=True,
                )

            completed = idx + 1
            if completed % 10 == 0 or completed == total_symbols:
                LOGGER.info(
                    "bootstrap stock data progress %s/%s daily=%s financials=%s",
                    completed,
                    total_symbols,
                    counters["daily_prices"],
                    counters["financials"],
                )

    if resume:
        _clear_checkpoint(signature)
    LOGGER.info("bootstrap stock data done: %s", counters)
    return counters


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap 100 A-share and 100 HK stock data.")
    parser.add_argument("--as-of", type=str, default=None, help="Target market date in YYYY-MM-DD format.")
    parser.add_argument("--daily-count", type=int, default=480, help="Daily kline rows to request per symbol.")
    parser.add_argument("--financial-periods", type=int, default=8, help="Number of quarter periods to backfill.")
    parser.add_argument("--a-count", type=int, default=100, help="How many A-share symbols to backfill.")
    parser.add_argument("--hk-count", type=int, default=100, help="How many Hong Kong symbols to backfill.")
    parser.add_argument("--no-resume", action="store_true", help="Do not resume from the last checkpoint.")
    parser.add_argument("--reset-progress", action="store_true", help="Clear the saved checkpoint before backfill.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    run_bootstrap(
        as_of=as_of,
        daily_count=args.daily_count,
        financial_periods=args.financial_periods,
        a_count=args.a_count,
        hk_count=args.hk_count,
        resume=not args.no_resume,
        reset_progress=args.reset_progress,
    )


if __name__ == "__main__":
    main()
