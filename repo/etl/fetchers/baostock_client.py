from __future__ import annotations

import os
from datetime import date
from typing import Callable

from etl.fetchers.snowball_client import normalize_symbol
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover
    ak = None
    LOGGER.warning("akshare import failed in baostock client: %s", exc)

try:
    import pandas as pd  # type: ignore
except Exception as exc:  # pragma: no cover
    pd = None
    LOGGER.warning("pandas import failed in baostock client: %s", exc)


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


def _parse_date(value) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    return None


def _normalize_symbol_from_code(code: str) -> str | None:
    token = str(code or "").strip()
    if not token:
        return None
    lowered = token.lower()
    if lowered.startswith("sh."):
        return f"{token[3:]}.SH"
    if lowered.startswith("sz."):
        return f"{token[3:]}.SZ"
    if lowered.startswith("bj."):
        return f"{token[3:]}.BJ"
    # 已经是 6 位数字
    if len(token) == 6 and token.isdigit():
        if token.startswith(("4", "8")):
            return f"{token}.BJ"
        if token.startswith(("5", "6", "9")):
            return f"{token}.SH"
        return f"{token}.SZ"
    return normalize_symbol(token)


def get_stock_industry(*, as_of: date | None = None) -> list[dict]:
    if ak is None or pd is None:
        return []
    try:
        df = ak.stock_industry_category_cninfo()
    except Exception as exc:
        LOGGER.warning("akshare stock_industry_category_cninfo failed: %s", exc)
        return []
    if df is None or getattr(df, "empty", True):
        return []

    rows: list[dict] = []
    for record in df.to_dict(orient="records"):
        code = str(record.get("股票代码") or record.get("code") or "").strip()
        if not code:
            continue
        symbol = _normalize_symbol_from_code(code)
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": str(record.get("股票简称") or record.get("name") or "").strip() or None,
                "sector": str(record.get("行业分类") or record.get("industry") or "").strip() or None,
                "industry_classification": str(record.get("行业分类") or record.get("industryClassification") or "").strip() or None,
                "update_date": as_of,
            }
        )
    return rows


def _query_constituents(query_fn: Callable[[], object], index_symbol: str, as_of: date) -> list[dict]:
    # 已废弃：指数成分统一由 index_constituent_client 提供
    LOGGER.warning("baostock _query_constituents is deprecated, use index_constituent_client")
    return []


def get_sz50_constituents(index_symbol: str, as_of: date) -> list[dict]:
    from etl.fetchers.index_constituent_client import get_index_constituents
    return get_index_constituents(index_symbol, as_of)


def get_hs300_constituents(index_symbol: str, as_of: date) -> list[dict]:
    from etl.fetchers.index_constituent_client import get_index_constituents
    return get_index_constituents(index_symbol, as_of)


def get_zz500_constituents(index_symbol: str, as_of: date) -> list[dict]:
    from etl.fetchers.index_constituent_client import get_index_constituents
    return get_index_constituents(index_symbol, as_of)


def get_index_member_constituents(index_symbol: str, as_of: date) -> list[dict]:
    from etl.fetchers.index_constituent_client import get_index_constituents
    return get_index_constituents(index_symbol, as_of)
