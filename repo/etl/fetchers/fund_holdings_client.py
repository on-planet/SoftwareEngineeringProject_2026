from __future__ import annotations

from datetime import date, datetime
from typing import List
import re

from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)

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


def _report_date_candidates(as_of: date) -> list[str]:
    quarter_ends = [
        date(as_of.year, 3, 31),
        date(as_of.year, 6, 30),
        date(as_of.year, 9, 30),
        date(as_of.year, 12, 31),
    ]
    candidate_dates = [as_of]
    candidate_dates.extend(day for day in quarter_ends if day <= as_of)
    if as_of.month <= 3:
        candidate_dates.append(date(as_of.year - 1, 12, 31))

    seen: set[str] = set()
    output: list[str] = []
    for candidate in sorted(set(candidate_dates), reverse=True):
        for text in (candidate.strftime("%Y-%m-%d"), candidate.strftime("%Y%m%d")):
            if text not in seen:
                seen.add(text)
                output.append(text)
    return output


def _is_empty_decode_error(exc: Exception) -> bool:
    text = str(exc).strip().lower()
    return text == "no value to decode" or "expecting value" in text


def _normalize_symbol(symbol: str) -> str:
    upper = symbol.strip().upper()
    if upper.endswith((".SH", ".SZ", ".HK")):
        return upper
    digits = re.sub(r"\D", "", upper)
    if len(digits) == 5:
        return f"{digits}.HK"
    if len(digits) == 6 and digits.startswith(("5", "6", "9")):
        return f"{digits}.SH"
    if len(digits) == 6:
        return f"{digits}.SZ"
    return upper


def _pick(record: dict, *keys: str):
    for key in keys:
        if key in record and record.get(key) not in (None, ""):
            return record.get(key)
    return None


def _try_fetch_with_dates(fetcher_name: str, as_of: date):
    if ak is None or not hasattr(ak, fetcher_name):
        return None
    fetcher = getattr(ak, fetcher_name)
    for candidate in _report_date_candidates(as_of):
        try:
            df = fetcher(date=candidate)
        except Exception as exc:
            if _is_empty_decode_error(exc):
                LOGGER.info("%s empty for %s", fetcher_name, candidate)
                continue
            LOGGER.warning("%s failed for %s: %s", fetcher_name, candidate, exc)
            continue
        records = _df_to_records(df)
        if records:
            LOGGER.info("%s loaded %s rows for %s", fetcher_name, len(records), candidate)
            return df
        LOGGER.info("%s empty dataframe for %s", fetcher_name, candidate)
    return None


def get_fund_holdings(as_of: date) -> List[dict]:
    """Fetch fund holdings for the given date using AkShare."""
    if ak is None:
        LOGGER.warning("akshare unavailable, skip fund holdings")
        return []

    rows: List[dict] = []
    df = _try_fetch_with_dates("fund_portfolio_hold_em", as_of)
    if df is None:
        df = _try_fetch_with_dates("fund_holdings", as_of)

    records = _df_to_records(df)
    if not records:
        return []

    for record in records:
        report_date = _to_date(
            _pick(
                record,
                "报告日期",
                "报告期",
                "report_date",
                "date",
                "截止日期",
            )
        )
        if report_date is None:
            report_date = as_of
        fund_code = _pick(record, "基金代码", "fund_code", "基金", "基金代码.")
        symbol = _pick(record, "股票代码", "证券代码", "symbol", "股票代码.")
        if not fund_code or not symbol:
            continue
        shares = _pick(record, "持仓股数", "持股数", "shares")
        market_value = _pick(record, "持仓市值", "市值", "market_value")
        weight = _pick(record, "占净值比例", "持仓占比", "weight")
        try:
            shares_val = float(shares) if shares is not None else None
        except Exception:
            shares_val = None
        try:
            market_value_val = float(market_value) if market_value is not None else None
        except Exception:
            market_value_val = None
        try:
            weight_val = float(weight) if weight is not None else None
            if weight_val is not None and weight_val > 1:
                weight_val = weight_val / 100.0
        except Exception:
            weight_val = None
        rows.append(
            {
                "fund_code": str(fund_code),
                "symbol": _normalize_symbol(str(symbol)),
                "report_date": report_date,
                "shares": shares_val,
                "market_value": market_value_val,
                "weight": weight_val,
            }
        )

    return ensure_required(rows, ["fund_code", "symbol", "report_date"], "fund_holdings")
