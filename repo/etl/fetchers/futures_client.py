from __future__ import annotations

from datetime import date, datetime
from typing import List
import os

from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover
    ak = None
    LOGGER.warning("akshare import failed in futures client: %s", exc)

try:
    import pandas as pd  # type: ignore
except Exception as exc:  # pragma: no cover
    pd = None
    LOGGER.warning("pandas import failed in futures client: %s", exc)


TARGET_PRODUCTS: dict[str, dict[str, str]] = {
    "cu_f": {"symbol": "CU", "name": "铜", "sina_code": "CU0"},
    "au_f": {"symbol": "AU", "name": "黄金", "sina_code": "AU0"},
    "ag_f": {"symbol": "AG", "name": "白银", "sina_code": "AG0"},
    "ao_f": {"symbol": "AO", "name": "氧化铝", "sina_code": "AO0"},
    "sc_f": {"symbol": "SC", "name": "原油", "sina_code": "SC0"},
    "fu_f": {"symbol": "FU", "name": "燃料油", "sina_code": "FU0"},
}


TARGET_PRODUCTS.update(
    {
        "al_f": {"symbol": "AL", "name": "Aluminum", "sina_code": "AL0"},
        "zn_f": {"symbol": "ZN", "name": "Zinc", "sina_code": "ZN0"},
        "pb_f": {"symbol": "PB", "name": "Lead", "sina_code": "PB0"},
        "ni_f": {"symbol": "NI", "name": "Nickel", "sina_code": "NI0"},
        "sn_f": {"symbol": "SN", "name": "Tin", "sina_code": "SN0"},
        "rb_f": {"symbol": "RB", "name": "Rebar", "sina_code": "RB0"},
        "hc_f": {"symbol": "HC", "name": "Hot Coil", "sina_code": "HC0"},
        "ss_f": {"symbol": "SS", "name": "Stainless Steel", "sina_code": "SS0"},
        "ru_f": {"symbol": "RU", "name": "Rubber", "sina_code": "RU0"},
        "br_f": {"symbol": "BR", "name": "Butadiene Rubber", "sina_code": "BR0"},
        "bu_f": {"symbol": "BU", "name": "Bitumen", "sina_code": "BU0"},
        "sp_f": {"symbol": "SP", "name": "Paper Pulp", "sina_code": "SP0"},
        "lu_f": {"symbol": "LU", "name": "Low Sulfur Fuel Oil", "sina_code": "LU0"},
        "nr_f": {"symbol": "NR", "name": "TSR 20 Rubber", "sina_code": "NR0"},
        "bc_f": {"symbol": "BC", "name": "Bonded Copper", "sina_code": "BC0"},
        "m_f": {"symbol": "M", "name": "Soybean Meal", "sina_code": "M0"},
        "y_f": {"symbol": "Y", "name": "Soybean Oil", "sina_code": "Y0"},
        "a_f": {"symbol": "A", "name": "Soybean No.1", "sina_code": "A0"},
        "b_f": {"symbol": "B", "name": "Soybean No.2", "sina_code": "B0"},
        "c_f": {"symbol": "C", "name": "Corn", "sina_code": "C0"},
        "cs_f": {"symbol": "CS", "name": "Corn Starch", "sina_code": "CS0"},
        "p_f": {"symbol": "P", "name": "Palm Oil", "sina_code": "P0"},
        "i_f": {"symbol": "I", "name": "Iron Ore", "sina_code": "I0"},
        "j_f": {"symbol": "J", "name": "Coke", "sina_code": "J0"},
        "jm_f": {"symbol": "JM", "name": "Coking Coal", "sina_code": "JM0"},
        "l_f": {"symbol": "L", "name": "LLDPE", "sina_code": "L0"},
        "pp_f": {"symbol": "PP", "name": "Polypropylene", "sina_code": "PP0"},
        "v_f": {"symbol": "V", "name": "PVC", "sina_code": "V0"},
        "eg_f": {"symbol": "EG", "name": "Ethylene Glycol", "sina_code": "EG0"},
        "eb_f": {"symbol": "EB", "name": "Styrene", "sina_code": "EB0"},
        "pg_f": {"symbol": "PG", "name": "LPG", "sina_code": "PG0"},
        "lh_f": {"symbol": "LH", "name": "Live Hog", "sina_code": "LH0"},
        "cf_f": {"symbol": "CF", "name": "Cotton", "sina_code": "CF0"},
        "sr_f": {"symbol": "SR", "name": "Sugar", "sina_code": "SR0"},
        "ta_f": {"symbol": "TA", "name": "PTA", "sina_code": "TA0"},
        "ma_f": {"symbol": "MA", "name": "Methanol", "sina_code": "MA0"},
        "oi_f": {"symbol": "OI", "name": "Rapeseed Oil", "sina_code": "OI0"},
        "rm_f": {"symbol": "RM", "name": "Rapeseed Meal", "sina_code": "RM0"},
        "fg_f": {"symbol": "FG", "name": "Glass", "sina_code": "FG0"},
        "sa_f": {"symbol": "SA", "name": "Soda Ash", "sina_code": "SA0"},
        "pf_f": {"symbol": "PF", "name": "Polyester Staple Fiber", "sina_code": "PF0"},
        "ap_f": {"symbol": "AP", "name": "Apple", "sina_code": "AP0"},
        "cj_f": {"symbol": "CJ", "name": "Red Dates", "sina_code": "CJ0"},
        "pk_f": {"symbol": "PK", "name": "Peanut", "sina_code": "PK0"},
        "ur_f": {"symbol": "UR", "name": "Urea", "sina_code": "UR0"},
        "sm_f": {"symbol": "SM", "name": "Manganese Silicon", "sina_code": "SM0"},
        "sf_f": {"symbol": "SF", "name": "Ferrosilicon", "sina_code": "SF0"},
        "if_f": {"symbol": "IF", "name": "CSI 300 Index", "sina_code": "IF0"},
        "ih_f": {"symbol": "IH", "name": "SSE 50 Index", "sina_code": "IH0"},
        "ic_f": {"symbol": "IC", "name": "CSI 500 Index", "sina_code": "IC0"},
        "im_f": {"symbol": "IM", "name": "CSI 1000 Index", "sina_code": "IM0"},
        "t_f": {"symbol": "T", "name": "10Y Treasury Bond", "sina_code": "T0"},
        "tf_f": {"symbol": "TF", "name": "5Y Treasury Bond", "sina_code": "TF0"},
        "ts_f": {"symbol": "TS", "name": "2Y Treasury Bond", "sina_code": "TS0"},
        "tl_f": {"symbol": "TL", "name": "30Y Treasury Bond", "sina_code": "TL0"},
    }
)
SUPPORTED_FUTURES_SYMBOLS = tuple(spec["symbol"] for spec in TARGET_PRODUCTS.values())


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


_FUTURES_HISTORY_CACHE: dict[str, pd.DataFrame] = {}


def _fetch_product_history(product_id: str) -> pd.DataFrame | None:
    if ak is None or pd is None:
        return None
    spec = TARGET_PRODUCTS.get(product_id)
    if spec is None:
        return None
    cache_key = spec["sina_code"]
    cached = _FUTURES_HISTORY_CACHE.get(cache_key)
    if cached is not None and not getattr(cached, "empty", True):
        return cached
    try:
        df = ak.futures_zh_daily_sina(symbol=cache_key)
    except Exception as exc:
        LOGGER.warning("akshare futures fetch failed [%s]: %s", product_id, exc)
        return None
    if df is None or getattr(df, "empty", True):
        return None
    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    except Exception:
        pass
    _FUTURES_HISTORY_CACHE[cache_key] = df
    return df


def _row_for_date(df, as_of: date) -> dict | None:
    if df is None or getattr(df, "empty", True):
        return None
    filtered = df[df["date"] <= as_of]
    if filtered.empty:
        return None
    # 按日期降序取最新的一条
    sorted_df = filtered.sort_values(by="date", ascending=False)
    return sorted_df.iloc[0].to_dict()


def _normalize_row(product_id: str, row: dict | None, as_of: date) -> dict | None:
    if row is None:
        return None
    spec = TARGET_PRODUCTS[product_id]
    close_val = _safe_float(row.get("close"))
    if close_val is None:
        return None
    open_val = _safe_float(row.get("open"))
    high_val = _safe_float(row.get("high"))
    low_val = _safe_float(row.get("low"))
    settle_val = _safe_float(row.get("settle"))
    volume_val = _safe_float(row.get("volume"))
    hold_val = _safe_float(row.get("hold"))
    return {
        "symbol": spec["symbol"],
        "name": spec["name"],
        "date": row.get("date") or as_of,
        "contract_month": None,
        "open": open_val if open_val is not None else close_val,
        "high": high_val if high_val is not None else close_val,
        "low": low_val if low_val is not None else close_val,
        "close": close_val,
        "settlement": settle_val if settle_val is not None else close_val,
        "open_interest": hold_val,
        "turnover": None,
        "volume": volume_val,
        "source": "AkShare",
    }


def get_futures_daily(as_of: date) -> list[dict]:
    rows: list[dict] = []
    for product_id in TARGET_PRODUCTS:
        df = _fetch_product_history(product_id)
        row = _row_for_date(df, as_of)
        normalized = _normalize_row(product_id, row, as_of)
        if normalized is not None:
            rows.append(normalized)
    return ensure_required(rows, ["symbol", "date"], "futures.daily")


def get_futures_history(
    symbol: str,
    *,
    start: date | None = None,
    end: date | None = None,
    limit: int = 480,
) -> list[dict]:
    normalized_symbol = str(symbol or "").strip().upper()
    product_id = next(
        (
            key
            for key, spec in TARGET_PRODUCTS.items()
            if str(spec.get("symbol") or "").strip().upper() == normalized_symbol
        ),
        None,
    )
    if product_id is None:
        return []
    df = _fetch_product_history(product_id)
    if df is None or getattr(df, "empty", True):
        return []

    end_at = end or date.today()
    rows: list[dict] = []
    for raw in df.to_dict(orient="records"):
        row_date = raw.get("date")
        if isinstance(row_date, datetime):
            row_date = row_date.date()
        if not isinstance(row_date, date):
            continue
        if start is not None and row_date < start:
            continue
        if row_date > end_at:
            continue
        normalized = _normalize_row(product_id, raw, row_date)
        if normalized is not None:
            rows.append(normalized)
    rows.sort(key=lambda item: item.get("date"))
    if limit > 0:
        rows = rows[-limit:]
    return ensure_required(rows, ["symbol", "date"], "futures.history")


def get_futures_weekly(as_of: date) -> list[dict]:
    rows = get_futures_daily(as_of)
    for row in rows:
        row["source"] = "AkShare"
    return ensure_required(rows, ["symbol", "date"], "futures.weekly")
