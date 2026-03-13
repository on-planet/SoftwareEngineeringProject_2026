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


def get_hk_daily(as_of: date) -> List[dict]:
    """Fetch HK daily prices for the given date using AkShare."""
    if ak is None:
        LOGGER.warning("akshare unavailable, skip hk daily")
        return []

    rows: List[dict] = []
    df = None
    if hasattr(ak, "stock_hk_daily"):
        try:
            df = ak.stock_hk_daily()
        except Exception as exc:
            LOGGER.warning("stock_hk_daily failed: %s", exc)
    if df is None:
        return []

    for record in _df_to_records(df):
        row_date = _to_date(record.get("date") or record.get("日期"))
        if row_date != as_of:
            continue
        symbol = record.get("symbol") or record.get("代码") or record.get("股票代码")
        if not symbol:
            continue
        if not str(symbol).endswith(".HK"):
            symbol = f"{symbol}.HK"
        rows.append(
            {
                "symbol": str(symbol),
                "date": as_of,
                "open": record.get("open") or record.get("开盘"),
                "high": record.get("high") or record.get("最高"),
                "low": record.get("low") or record.get("最低"),
                "close": record.get("close") or record.get("收盘"),
                "volume": record.get("volume") or record.get("成交量") or record.get("vol"),
            }
        )

    return ensure_required(
        rows,
        ["symbol", "date", "open", "high", "low", "close", "volume"],
        "akshare.hk_daily",
    )


def get_macro_series(code: str, start: date, end: date) -> List[dict]:
    """Fetch macro series data for the given code and range using AkShare."""
    if ak is None:
        LOGGER.warning("akshare unavailable, skip macro series")
        return []

    rows: List[dict] = []
    code_upper = code.upper()

    try:
        df = None
        if code_upper == "CPI" and hasattr(ak, "macro_china_cpi"):
            df = ak.macro_china_cpi()
        elif code_upper == "PPI" and hasattr(ak, "macro_china_ppi"):
            df = ak.macro_china_ppi()
        elif code_upper == "M2" and hasattr(ak, "macro_china_money_supply"):
            df = ak.macro_china_money_supply()
        elif code_upper == "PMI" and hasattr(ak, "macro_china_pmi"):
            df = ak.macro_china_pmi()
        elif code_upper == "SHIBOR" and hasattr(ak, "macro_china_shibor_all"):
            df = ak.macro_china_shibor_all()
        elif code_upper == "TSF" and hasattr(ak, "macro_china_tsf"):
            df = ak.macro_china_tsf()

        for record in _df_to_records(df):
            row_date = _to_date(record.get("日期") or record.get("date"))
            if row_date is None:
                continue
            if row_date < start or row_date > end:
                continue
            value = None
            if code_upper == "M2":
                value = record.get("M2") or record.get("货币和准货币(M2)") or record.get("m2")
            elif code_upper == "SHIBOR":
                value = record.get("隔夜") or record.get("ON") or record.get("value")
            elif code_upper == "TSF":
                value = record.get("社会融资规模") or record.get("value")
            else:
                value = record.get("同比") or record.get("同比增长") or record.get("value")
            rows.append({"key": code_upper, "date": row_date, "value": value})
    except Exception as exc:
        LOGGER.warning("macro series failed for %s: %s", code, exc)

    return ensure_required(rows, ["key", "date", "value"], "akshare.macro_series")
