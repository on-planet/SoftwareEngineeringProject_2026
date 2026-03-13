from __future__ import annotations

from datetime import date, datetime
from typing import List

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


def get_fund_holdings(as_of: date) -> List[dict]:
    """Fetch fund holdings for the given date using AkShare."""
    if ak is None:
        LOGGER.warning("akshare unavailable, skip fund holdings")
        return []

    rows: List[dict] = []
    df = None
    if hasattr(ak, "fund_portfolio_hold_em"):
        try:
            df = ak.fund_portfolio_hold_em(date=as_of.strftime("%Y-%m-%d"))
        except Exception as exc:
            LOGGER.warning("fund_portfolio_hold_em failed: %s", exc)
    elif hasattr(ak, "fund_holdings"):
        try:
            df = ak.fund_holdings(date=as_of.strftime("%Y-%m-%d"))
        except Exception as exc:
            LOGGER.warning("fund_holdings failed: %s", exc)

    for record in _df_to_records(df):
        report_date = _to_date(
            record.get("报告日期")
            or record.get("报告期")
            or record.get("report_date")
            or record.get("date")
        )
        if report_date is None:
            report_date = as_of
        fund_code = record.get("基金代码") or record.get("fund_code") or record.get("基金")
        symbol = record.get("股票代码") or record.get("证券代码") or record.get("symbol")
        if not fund_code or not symbol:
            continue
        shares = record.get("持仓股数") or record.get("持股数") or record.get("shares")
        market_value = record.get("持仓市值") or record.get("市值") or record.get("market_value")
        weight = record.get("占净值比例") or record.get("持仓占比") or record.get("weight")
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
                "symbol": str(symbol),
                "report_date": report_date,
                "shares": shares_val,
                "market_value": market_value_val,
                "weight": weight_val,
            }
        )

    return ensure_required(
        rows,
        ["fund_code", "symbol", "report_date"],
        "fund_holdings",
    )
