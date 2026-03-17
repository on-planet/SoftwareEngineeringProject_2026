from __future__ import annotations

import os
from datetime import date, datetime
from typing import Callable

from etl.fetchers.snowball_client import normalize_symbol
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)
INDUSTRY_FAILURE_COOLDOWN_SECONDS = max(60, int(os.getenv("BAOSTOCK_INDUSTRY_FAILURE_COOLDOWN_SECONDS", "900")))
_industry_retry_not_before: datetime | None = None

try:
    import baostock as bs  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    bs = None
    LOGGER.warning("baostock import failed: %s", exc)


def _normalize_baostock_symbol(raw_symbol: str) -> str | None:
    token = str(raw_symbol or "").strip()
    if not token:
        return None
    lowered = token.lower()
    if lowered.startswith("sh."):
        return f"{token[3:]}.SH"
    if lowered.startswith("sz."):
        return f"{token[3:]}.SZ"
    if lowered.startswith("bj."):
        return f"{token[3:]}.BJ"
    return None


def _parse_baostock_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    return None


def _safe_logout() -> None:
    if bs is None:
        return
    try:
        bs.logout()
    except Exception:
        return


def _mark_industry_failure() -> None:
    global _industry_retry_not_before
    _industry_retry_not_before = datetime.now()


def _industry_cooldown_active() -> bool:
    if _industry_retry_not_before is None:
        return False
    return (datetime.now() - _industry_retry_not_before).total_seconds() < INDUSTRY_FAILURE_COOLDOWN_SECONDS


def _query_constituents(query_fn: Callable[[], object], index_symbol: str, as_of: date) -> list[dict]:
    if bs is None:
        return []
    try:
        login = bs.login()
    except Exception as exc:  # pragma: no cover - runtime env dependent
        LOGGER.warning("baostock login failed: %s", exc)
        return []

    if getattr(login, "error_code", None) not in (None, "0"):
        LOGGER.warning("baostock login error: %s %s", getattr(login, "error_code", ""), getattr(login, "error_msg", ""))
        _safe_logout()
        return []

    try:
        result = query_fn()
    except Exception as exc:  # pragma: no cover - runtime env dependent
        LOGGER.warning("baostock query failed [%s]: %s", index_symbol, exc)
        _safe_logout()
        return []

    if getattr(result, "error_code", None) not in (None, "0"):
        LOGGER.warning(
            "baostock query error [%s]: %s %s",
            index_symbol,
            getattr(result, "error_code", ""),
            getattr(result, "error_msg", ""),
        )
        _safe_logout()
        return []

    rows: list[dict] = []
    rank = 0
    fields = [str(field) for field in (getattr(result, "fields", None) or [])]
    try:
        while getattr(result, "error_code", None) in (None, "0") and result.next():
            row = result.get_row_data()
            if not row:
                continue
            rank += 1
            record = dict(zip(fields, row)) if fields and len(fields) == len(row) else {}
            symbol_raw = record.get("code") or (row[1] if len(row) > 1 else row[0] if len(row) > 0 else "")
            symbol = _normalize_baostock_symbol(symbol_raw)
            if not symbol:
                continue
            name_raw = record.get("code_name") or (row[2] if len(row) > 2 else row[1] if len(row) > 1 else None)
            update_date = _parse_baostock_date(record.get("updateDate") or record.get("update_date") or record.get("date"))
            item = {
                "index_symbol": normalize_symbol(index_symbol),
                "symbol": symbol,
                "date": update_date or as_of,
                "weight": None,
                "rank": rank,
                "source": "BaoStock",
            }
            if name_raw not in (None, ""):
                item["name"] = str(name_raw)
            rows.append(item)
    except Exception as exc:
        LOGGER.warning("baostock constituent decode failed [%s]: %s", index_symbol, exc)
        rows = []
    _safe_logout()
    return rows


def _query_stock_industry() -> list[dict]:
    if bs is None:
        return []
    if _industry_cooldown_active():
        return []
    try:
        login = bs.login()
    except Exception as exc:  # pragma: no cover - runtime env dependent
        LOGGER.warning("baostock login failed: %s", exc)
        _mark_industry_failure()
        return []

    if getattr(login, "error_code", None) not in (None, "0"):
        LOGGER.warning("baostock login error: %s %s", getattr(login, "error_code", ""), getattr(login, "error_msg", ""))
        _mark_industry_failure()
        _safe_logout()
        return []

    try:
        result = bs.query_stock_industry()
    except Exception as exc:  # pragma: no cover - runtime env dependent
        LOGGER.warning("baostock query_stock_industry failed: %s", exc)
        _mark_industry_failure()
        _safe_logout()
        return []

    if getattr(result, "error_code", None) not in (None, "0"):
        LOGGER.warning(
            "baostock query_stock_industry error: %s %s",
            getattr(result, "error_code", ""),
            getattr(result, "error_msg", ""),
        )
        _mark_industry_failure()
        _safe_logout()
        return []

    fields = [str(field) for field in (getattr(result, "fields", None) or [])]
    rows: list[dict] = []
    try:
        while getattr(result, "error_code", None) in (None, "0") and result.next():
            row = result.get_row_data()
            if not row:
                continue
            record = dict(zip(fields, row)) if fields and len(fields) == len(row) else {}
            symbol = _normalize_baostock_symbol(record.get("code") or "")
            if not symbol:
                continue
            item = {
                "symbol": symbol,
                "name": record.get("code_name") or None,
                "sector": record.get("industry") or None,
                "industry_classification": record.get("industryClassification") or None,
                "update_date": _parse_baostock_date(record.get("updateDate")),
            }
            rows.append(item)
    except Exception as exc:
        LOGGER.warning("baostock stock industry decode failed: %s", exc)
        _mark_industry_failure()
        rows = []

    _safe_logout()
    return rows


def get_sz50_constituents(index_symbol: str, as_of: date) -> list[dict]:
    if bs is None:
        return []
    return _query_constituents(bs.query_sz50_stocks, index_symbol, as_of)


def get_stock_industry(*, as_of: date | None = None) -> list[dict]:
    rows = _query_stock_industry()
    if not as_of:
        return rows
    filtered: list[dict] = []
    for row in rows:
        row_date = row.get("update_date")
        if row_date is None or row_date <= as_of:
            filtered.append(row)
    return filtered


def _normalize_baostock_index_symbol(index_symbol: str) -> str | None:
    normalized = normalize_symbol(index_symbol)
    if not normalized:
        return None
    if normalized.endswith(".SH"):
        return f"sh.{normalized[:-3]}"
    if normalized.endswith(".SZ"):
        return f"sz.{normalized[:-3]}"
    if normalized.endswith(".BJ"):
        return f"bj.{normalized[:-3]}"
    return None


def get_index_member_constituents(index_symbol: str, as_of: date) -> list[dict]:
    if bs is None:
        return []
    index_code = _normalize_baostock_index_symbol(index_symbol)
    if not index_code:
        return []
    query_fn = getattr(bs, "query_index_member", None)
    if query_fn is None:
        return []

    def _call_query():
        date_text = as_of.strftime("%Y-%m-%d")
        for args in ((index_code, date_text), (index_code,)):
            try:
                return query_fn(*args)
            except TypeError:
                continue
        return query_fn(index_code)

    return _query_constituents(_call_query, index_symbol, as_of)


def get_hs300_constituents(index_symbol: str, as_of: date) -> list[dict]:
    if bs is None:
        return []
    return _query_constituents(bs.query_hs300_stocks, index_symbol, as_of)


def get_zz500_constituents(index_symbol: str, as_of: date) -> list[dict]:
    if bs is None:
        return []
    return _query_constituents(bs.query_zz500_stocks, index_symbol, as_of)
