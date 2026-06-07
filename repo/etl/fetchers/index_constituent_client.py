from __future__ import annotations

from datetime import date
from typing import List
import re

from etl.fetchers.snowball_client import normalize_symbol
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover
    ak = None
    LOGGER.warning("akshare import failed in index constituent client: %s", exc)

try:
    import pandas as pd  # type: ignore
except Exception as exc:  # pragma: no cover
    pd = None
    LOGGER.warning("pandas import failed in index constituent client: %s", exc)


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


def _index_code_from_symbol(local_symbol: str) -> str | None:
    normalized = normalize_symbol(local_symbol)
    digits = re.sub(r"\D", "", normalized)
    return digits if digits else None


def get_index_constituents(index_symbol: str, as_of: date) -> List[dict]:
    if ak is None or pd is None:
        return []
    local_symbol = normalize_symbol(index_symbol)
    index_code = _index_code_from_symbol(local_symbol)
    if not index_code:
        return []

    try:
        df = ak.index_stock_cons_weight_csindex(symbol=index_code)
    except Exception as exc:
        LOGGER.warning("akshare index constituents fetch failed [%s]: %s", local_symbol, exc)
        return []
    if df is None or getattr(df, "empty", True):
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    for record in df.to_dict(orient="records"):
        code = str(record.get("成分券代码") or record.get("code") or "").strip()
        if not code:
            continue
        if len(code) == 6:
            if code.startswith(("4", "8")):
                symbol = f"{code}.BJ"
            elif code.startswith(("5", "6", "9")):
                symbol = f"{code}.SH"
            else:
                symbol = f"{code}.SZ"
        else:
            symbol = normalize_symbol(code)
        if symbol in seen:
            continue
        seen.add(symbol)

        weight = _safe_float(record.get("权重") or record.get("weight"))

        row = {
            "index_symbol": local_symbol,
            "symbol": symbol,
            "date": as_of,
            "weight": weight or 0.0,
            "rank": len(rows) + 1,
            "source": "AkShare CSI",
        }
        name = str(record.get("成分券名称") or record.get("name") or "").strip()
        if name:
            row["name"] = name
        rows.append(row)

    total_weight = sum(float(row.get("weight") or 0.0) for row in rows)
    if total_weight > 1.5:
        for row in rows:
            row["weight"] = float(row.get("weight") or 0.0) / 100.0

    return ensure_required(rows, ["index_symbol", "symbol", "date", "weight"], "index.constituents")
