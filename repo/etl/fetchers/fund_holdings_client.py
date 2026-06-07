from __future__ import annotations

from datetime import date, datetime
from typing import List
import os
import re

from etl.fetchers.snowball_client import normalize_symbol
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover
    ak = None
    LOGGER.warning("akshare import failed in fund client: %s", exc)

try:
    import pandas as pd  # type: ignore
except Exception as exc:  # pragma: no cover
    pd = None
    LOGGER.warning("pandas import failed in fund client: %s", exc)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _normalize_cn_fund_code(text: str) -> str:
    digits = re.sub(r"\D", "", text)
    return digits[:6] if len(digits) >= 6 else text.strip()


def _quarter_for_date(as_of: date) -> str:
    quarter = (as_of.month - 1) // 3 + 1
    return f"{as_of.year}{quarter}"


def get_fund_codes() -> list[str]:
    raw = os.getenv("SNOWBALL_FUND_CODES", "").strip()
    if raw:
        return [_normalize_cn_fund_code(item) for item in raw.split(",") if item.strip()]
    return ["161725", "110022", "001186"]


def get_fund_holdings(as_of: date) -> List[dict]:
    if ak is None or pd is None:
        LOGGER.warning("akshare unavailable, skip fund holdings")
        return []

    quarter = _quarter_for_date(as_of)
    rows: list[dict] = []
    for fund_code in get_fund_codes():
        try:
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date=quarter)
        except Exception as exc:
            LOGGER.warning("akshare fund_portfolio_hold_em failed [%s]: %s", fund_code, exc)
            continue
        if df is None or getattr(df, "empty", True):
            continue

        for record in df.to_dict(orient="records"):
            raw_symbol = record.get("股票代码") or record.get("code") or record.get("symbol")
            if raw_symbol in (None, ""):
                continue
            symbol = normalize_symbol(str(raw_symbol))
            if not symbol.endswith((".SH", ".SZ", ".BJ", ".HK", ".US")):
                continue

            weight = _safe_float(record.get("占净值比例") or record.get("weight") or record.get("proportion"))
            if weight is not None and weight > 1:
                weight = weight / 100.0

            rows.append(
                {
                    "fund_code": fund_code,
                    "symbol": symbol,
                    "report_date": as_of,
                    "shares": _safe_float(record.get("持股数") or record.get("shares") or record.get("volume")),
                    "market_value": _safe_float(record.get("持仓市值") or record.get("market_value") or record.get("value")),
                    "weight": weight,
                }
            )

    return ensure_required(rows, ["fund_code", "symbol", "report_date"], "fund_holdings")
