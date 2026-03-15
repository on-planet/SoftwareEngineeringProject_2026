from __future__ import annotations

from datetime import date
from typing import Iterable, List
import os
import re

from etl.fetchers.snowball_client import normalize_symbol
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)

try:
    import pysnowball as ball  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    ball = None
    LOGGER.warning("pysnowball import failed: %s", exc)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1]
    try:
        number = float(text)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _extract_dict_rows(payload) -> list[dict]:
    rows: list[dict] = []
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            rows.append(node)
            stack.extend(node.values())
            continue
        if isinstance(node, list):
            stack.extend(node)
    return [row for row in rows if row]


def _pick(record: dict, keys: Iterable[str]):
    for key in keys:
        if key in record and record.get(key) not in (None, ""):
            return record.get(key)
    return None


def _index_code_map() -> dict[str, str]:
    raw = os.getenv(
        "SNOWBALL_INDEX_CONS_MAP",
        "000001.SH=000001,399001.SZ=399001,399006.SZ=399006",
    )
    output: dict[str, str] = {}
    for item in raw.split(","):
        if "=" not in item:
            continue
        left, right = item.split("=", 1)
        index_symbol = normalize_symbol(left.strip())
        index_code = re.sub(r"\D", "", right.strip())
        if index_symbol and index_code:
            output[index_symbol] = index_code
    return output


def get_index_constituents(index_symbol: str, as_of: date) -> List[dict]:
    if ball is None:
        LOGGER.warning("pysnowball unavailable, skip index constituents")
        return []

    local_symbol = normalize_symbol(index_symbol)
    index_code = _index_code_map().get(local_symbol, re.sub(r"\D", "", local_symbol))
    if not index_code:
        return []

    try:
        payload = ball.index_weight_top10(index_code)
    except Exception as exc:
        LOGGER.warning("snowball index_weight_top10 failed [%s]: %s", index_code, exc)
        return []

    rows: list[dict] = []
    for record in _extract_dict_rows(payload):
        raw_symbol = _pick(
            record,
            (
                "stockCode",
                "stock_code",
                "consCode",
                "cons_code",
                "secu_code",
                "symbol",
                "code",
            ),
        )
        if raw_symbol in (None, ""):
            continue
        symbol = normalize_symbol(str(raw_symbol))
        if not symbol.endswith((".SH", ".SZ", ".HK", ".US")):
            continue
        weight = _safe_float(_pick(record, ("weight", "weightValue", "iweight", "weight_rate", "ratio"))) or 0.0
        if weight > 1:
            weight = weight / 100.0
        rows.append(
            {
                "index_symbol": local_symbol,
                "symbol": symbol,
                "date": as_of,
                "weight": weight,
            }
        )
    return ensure_required(rows, ["index_symbol", "symbol", "date", "weight"], "index.constituents")
