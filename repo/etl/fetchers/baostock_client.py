from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO
import os
from threading import Lock
from typing import Iterable, List

from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)
_SESSION_LOCK = Lock()
_SESSION_DEPTH = 0

try:
    import baostock as bs  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    bs = None
    LOGGER.warning("baostock import failed: %s", exc)


@dataclass
class _BSResult:
    ok: bool
    error_code: str
    error_msg: str
    output: str = ""


def _login() -> _BSResult:
    if bs is None:
        return _BSResult(False, "-1", "baostock unavailable")
    try:
        buffer = StringIO()
        with redirect_stdout(buffer):
            lg = bs.login()
        return _BSResult(lg.error_code == "0", lg.error_code, lg.error_msg, buffer.getvalue().strip())
    except Exception as exc:
        return _BSResult(False, "-1", str(exc))


@contextmanager
def baostock_session():
    global _SESSION_DEPTH
    if bs is None:
        yield
        return
    with _SESSION_LOCK:
        if _SESSION_DEPTH == 0:
            result = _login()
            if not result.ok:
                LOGGER.warning("baostock login failed: %s %s", result.error_code, result.error_msg)
                yield
                return
            if result.output:
                LOGGER.info("baostock session: %s", result.output)
        _SESSION_DEPTH += 1
    try:
        yield
    finally:
        with _SESSION_LOCK:
            _SESSION_DEPTH -= 1
            if _SESSION_DEPTH == 0:
                logout_output = _logout()
                if logout_output:
                    LOGGER.info("baostock session: %s", logout_output)


def _logout() -> str:
    if bs is None:
        return ""
    try:
        buffer = StringIO()
        with redirect_stdout(buffer):
            bs.logout()
        return buffer.getvalue().strip()
    except Exception:
        return ""


def _with_session(fn):
    def wrapper(*args, **kwargs):
        global _SESSION_DEPTH
        if bs is None:
            return [] if fn.__name__.startswith("get_") else {}
        if _SESSION_DEPTH > 0:
            return fn(*args, **kwargs)
        result = _login()
        if not result.ok:
            LOGGER.warning("baostock login failed: %s %s", result.error_code, result.error_msg)
            return [] if fn.__name__.startswith("get_") else {}
        logout_output = ""
        try:
            return fn(*args, **kwargs)
        finally:
            logout_output = _logout()
            combined = "; ".join([
                part
                for part in [result.output, logout_output]
                if part
            ])
            if combined:
                LOGGER.info("baostock session: %s", combined)

    return wrapper


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


def _normalize_symbol(code: str) -> str:
    code = str(code)
    if code.endswith(".SH") or code.endswith(".SZ") or code.endswith(".HK"):
        return code
    if code.startswith("sh.") or code.startswith("sz."):
        prefix, digits = code.split(".", 1)
        return f"{digits}.SH" if prefix == "sh" else f"{digits}.SZ"
    if code.startswith(("5", "6", "9")):
        return f"{code}.SH"
    if code.startswith(("00", "30", "32")):
        return f"{code}.SZ"
    return f"{code}.SH"


def _strip_suffix(symbol: str) -> str:
    if symbol.endswith(".SH") or symbol.endswith(".SZ"):
        return symbol.split(".")[0]
    return symbol


def _to_bs_code(symbol: str) -> str:
    if symbol.startswith("sh.") or symbol.startswith("sz."):
        return symbol
    if symbol.endswith(".SH"):
        return f"sh.{symbol.split('.')[0]}"
    if symbol.endswith(".SZ"):
        return f"sz.{symbol.split('.')[0]}"
    raw = _strip_suffix(symbol)
    if raw.startswith(("5", "6", "9")):
        return f"sh.{raw}"
    return f"sz.{raw}"


def _iter_rows(result) -> Iterable[dict]:
    if result is None:
        return []
    if getattr(result, "error_code", "1") != "0":
        LOGGER.warning("baostock query failed: %s %s", result.error_code, result.error_msg)
        return []
    fields = result.fields or []
    rows = []
    while result.next():
        row = result.get_row_data()
        rows.append(dict(zip(fields, row)))
    return rows


@_with_session
def get_stock_basic() -> List[dict]:
    """Fetch A-share stock basic list using BaoStock."""
    if bs is None:
        LOGGER.warning("baostock unavailable, skip stock basic")
        return []
    rows: List[dict] = []
    rs = bs.query_stock_basic()
    for record in _iter_rows(rs):
        code = record.get("code")
        name = record.get("code_name") or record.get("name")
        industry = record.get("industry") or "未知"
        if not code:
            continue
        rows.append(
            {
                "symbol": _normalize_symbol(code),
                "name": str(name) if name is not None else _normalize_symbol(code),
                "market": "A",
                "sector": str(industry) if industry is not None else "未知",
            }
        )
    return ensure_required(rows, ["symbol", "name", "market", "sector"], "baostock.stock_basic")


@_with_session
def get_index_daily(as_of: date) -> List[dict]:
    """Fetch A-share index daily data for the given date using BaoStock."""
    if bs is None:
        LOGGER.warning("baostock unavailable, skip index daily")
        return []
    index_symbols = ["000001", "399001", "399006"]
    rows: List[dict] = []
    start_date = as_of.strftime("%Y-%m-%d")
    end_date = start_date
    for raw_symbol in index_symbols:
        bs_code = _to_bs_code(raw_symbol if raw_symbol.startswith(("sh.", "sz.")) else raw_symbol)
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,code,close,preclose",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3",
        )
        for record in _iter_rows(rs):
            row_date = _to_date(record.get("date"))
            if row_date != as_of:
                continue
            close = record.get("close")
            preclose = record.get("preclose")
            change = None
            try:
                if close is not None and preclose is not None:
                    change = float(close) - float(preclose)
            except Exception:
                change = None
            rows.append(
                {
                    "symbol": _normalize_symbol(record.get("code") or bs_code),
                    "date": as_of,
                    "close": float(close) if close is not None else None,
                    "change": float(change) if change is not None else None,
                }
            )
    return ensure_required(rows, ["symbol", "date", "close", "change"], "baostock.index_daily")


@_with_session
def get_daily_prices(symbols, as_of: date) -> List[dict]:
    """Fetch A-share daily prices for the given symbols and date using BaoStock."""
    if bs is None:
        LOGGER.warning("baostock unavailable, skip daily prices")
        return []
    rows: List[dict] = []
    start_date = as_of.strftime("%Y-%m-%d")
    end_date = start_date
    total = len(symbols)
    workers = int(os.getenv("BAOSTOCK_WORKERS", "8"))
    batch_size = int(os.getenv("BAOSTOCK_BATCH_SIZE", "200"))

    def _fetch_batch(batch: list[str]) -> List[dict]:
        output: List[dict] = []
        for symbol in batch:
            bs_code = _to_bs_code(symbol)
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,code,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3",
            )
            for record in _iter_rows(rs):
                row_date = _to_date(record.get("date"))
                if row_date != as_of:
                    continue
                output.append(
                    {
                        "symbol": _normalize_symbol(record.get("code") or bs_code),
                        "date": as_of,
                        "open": float(record.get("open")) if record.get("open") not in (None, "") else None,
                        "high": float(record.get("high")) if record.get("high") not in (None, "") else None,
                        "low": float(record.get("low")) if record.get("low") not in (None, "") else None,
                        "close": float(record.get("close")) if record.get("close") not in (None, "") else None,
                        "volume": float(record.get("volume")) if record.get("volume") not in (None, "") else None,
                    }
                )
        return output

    if workers <= 1:
        completed = 0
        for idx in range(0, total, batch_size):
            batch = symbols[idx: idx + batch_size]
            completed += len(batch)
            LOGGER.info("baostock daily progress %s/%s for %s", completed, total, as_of)
            rows.extend(_fetch_batch(batch))
    else:
        LOGGER.info(
            "baostock daily parallel workers=%s batch=%s total=%s date=%s",
            workers,
            batch_size,
            total,
            as_of,
        )
        with ThreadPoolExecutor(max_workers=workers) as executor:
            batches = [symbols[i: i + batch_size] for i in range(0, total, batch_size)]
            future_map = {executor.submit(_fetch_batch, batch): batch for batch in batches}
            completed = 0
            for future in as_completed(future_map):
                batch = future_map[future]
                completed += len(batch)
                if completed == len(batch) or completed % 200 == 0 or completed >= total:
                    LOGGER.info("baostock daily progress %s/%s for %s", completed, total, as_of)
                try:
                    rows.extend(future.result())
                except Exception as exc:
                    LOGGER.warning("baostock daily batch failed size=%s: %s", len(batch), exc)

    return ensure_required(
        rows,
        ["symbol", "date", "open", "high", "low", "close", "volume"],
        "baostock.daily",
    )


def _period_to_year_quarter(period: str) -> tuple[str, str]:
    year = period[:4]
    month = int(period[4:6]) if len(period) >= 6 else 12
    quarter = (month - 1) // 3 + 1
    return year, str(quarter)


@_with_session
def get_financials(symbol: str, period: str) -> dict:
    """Fetch financial statements for a symbol and period using BaoStock."""
    if bs is None:
        LOGGER.warning("baostock unavailable, skip financials")
        return {}
    bs_code = _to_bs_code(symbol)
    year, quarter = _period_to_year_quarter(period)

    profit = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
    growth = bs.query_growth_data(code=bs_code, year=year, quarter=quarter)
    balance = bs.query_balance_data(code=bs_code, year=year, quarter=quarter)
    cash_flow = bs.query_cash_flow_data(code=bs_code, year=year, quarter=quarter)

    profit_row = next(iter(_iter_rows(profit)), {})
    growth_row = next(iter(_iter_rows(growth)), {})
    balance_row = next(iter(_iter_rows(balance)), {})
    cash_row = next(iter(_iter_rows(cash_flow)), {})

    revenue = growth_row.get("totalRevenue") or growth_row.get("totalRevenueYoy")
    net_income = profit_row.get("netProfit") or profit_row.get("netProfitAttrP")
    cash_flow_val = cash_row.get("netCashFlow") or cash_row.get("netCashflowFromOper")
    roe = profit_row.get("roeAvg") or profit_row.get("roe")
    debt_ratio = balance_row.get("debtToAsset")

    row = {
        "symbol": _normalize_symbol(bs_code),
        "period": period,
        "revenue": float(revenue) if revenue not in (None, "") else 0.0,
        "net_income": float(net_income) if net_income not in (None, "") else 0.0,
        "cash_flow": float(cash_flow_val) if cash_flow_val not in (None, "") else 0.0,
        "roe": float(roe) if roe not in (None, "") else 0.0,
        "debt_ratio": float(debt_ratio) if debt_ratio not in (None, "") else 0.0,
    }

    rows = ensure_required(
        [row],
        ["symbol", "period", "revenue", "net_income", "cash_flow", "roe", "debt_ratio"],
        "baostock.financials",
    )
    return rows[0] if rows else {}
