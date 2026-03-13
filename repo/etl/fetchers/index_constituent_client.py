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


def _normalize_symbol(symbol: str) -> str:
    if symbol.endswith(".SH") or symbol.endswith(".SZ") or symbol.endswith(".HK"):
        return symbol
    if symbol.startswith(("5", "6", "9")):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"


def _strip_suffix(symbol: str) -> str:
    if symbol.endswith(".SH") or symbol.endswith(".SZ") or symbol.endswith(".HK"):
        return symbol.split(".")[0]
    return symbol


def _detect_index_market(index_symbol: str) -> str | None:
    if index_symbol.endswith(".SH"):
        return "sh"
    if index_symbol.endswith(".SZ"):
        return "sz"
    if index_symbol.endswith(".CSI"):
        return "csi"
    return None


def _call_index_cons(index_symbol: str):
    if ak is None:
        return None
    market = _detect_index_market(index_symbol)
    symbol = _strip_suffix(index_symbol)
    if hasattr(ak, "index_stock_cons"):
        try:
            if market:
                try:
                    return ak.index_stock_cons(index=market, symbol=symbol)
                except TypeError:
                    return ak.index_stock_cons(market=market, symbol=symbol)
            return ak.index_stock_cons(symbol=symbol)
        except Exception as exc:
            LOGGER.warning("index_stock_cons failed for %s: %s", index_symbol, exc)
    return None


def get_index_constituents(index_symbol: str, as_of: date) -> List[dict]:
    """Fetch index constituents for a given date using AkShare."""
    if ak is None:
        LOGGER.warning("akshare unavailable, skip index constituents")
        return []

    df = _call_index_cons(index_symbol)
    rows: List[dict] = []
    for record in _df_to_records(df):
        symbol = record.get("成分券代码") or record.get("证券代码") or record.get("symbol")
        if not symbol:
            continue
        weight = record.get("权重") or record.get("weight") or record.get("权重(%)")
        try:
            weight_val = float(weight) / 100.0 if weight is not None else 0.0
        except Exception:
            weight_val = 0.0
        rows.append(
            {
                "index_symbol": index_symbol,
                "symbol": _normalize_symbol(str(symbol)),
                "date": as_of,
                "weight": weight_val,
            }
        )

    return ensure_required(rows, ["index_symbol", "symbol", "date", "weight"], "index.constituents")
