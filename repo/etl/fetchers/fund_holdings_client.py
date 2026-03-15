from __future__ import annotations

from datetime import date, datetime
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
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        if text.endswith("%"):
            text = text[:-1]
        value = text
    try:
        number = float(value)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _to_date(value, fallback: date) -> date:
    if value is None:
        return fallback
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return fallback
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    return fallback


def _pick(record: dict, keys: Iterable[str]):
    for key in keys:
        if key in record and record.get(key) not in (None, ""):
            return record.get(key)
    return None


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
    # Prefer flattened child rows over root dicts.
    return [row for row in rows if any(isinstance(v, (str, int, float)) for v in row.values())]


def _normalize_cn_fund_code(text: str) -> str:
    digits = re.sub(r"\D", "", text)
    return digits[:6] if len(digits) >= 6 else text.strip()


def get_fund_codes() -> list[str]:
    raw = os.getenv("SNOWBALL_FUND_CODES", "").strip()
    if raw:
        return [_normalize_cn_fund_code(item) for item in raw.split(",") if item.strip()]
    # A small default CN fund set to keep pipeline runnable.
    return ["161725", "110022", "001186"]


def get_fund_holdings(as_of: date) -> List[dict]:
    if ball is None:
        LOGGER.warning("pysnowball unavailable, skip fund holdings")
        return []

    rows: list[dict] = []
    for fund_code in get_fund_codes():
        try:
            payload = ball.fund_asset(fund_code)
        except Exception as exc:
            LOGGER.warning("snowball fund_asset failed [%s]: %s", fund_code, exc)
            continue

        for record in _extract_dict_rows(payload):
            raw_symbol = _pick(
                record,
                (
                    "symbol",
                    "stock_symbol",
                    "stock_code",
                    "code",
                    "ticker",
                    "stock",
                    "asset_code",
                ),
            )
            if raw_symbol in (None, ""):
                continue
            symbol = normalize_symbol(str(raw_symbol))
            if not symbol.endswith((".SH", ".SZ", ".HK", ".US")):
                continue

            weight = _safe_float(_pick(record, ("weight", "ratio", "proportion", "percent", "position_ratio")))
            if weight is not None and weight > 1:
                weight = weight / 100.0

            rows.append(
                {
                    "fund_code": fund_code,
                    "symbol": symbol,
                    "report_date": _to_date(
                        _pick(record, ("report_date", "date", "reportDate", "end_date", "publish_date")),
                        as_of,
                    ),
                    "shares": _safe_float(_pick(record, ("shares", "volume", "amount", "position_shares"))),
                    "market_value": _safe_float(_pick(record, ("market_value", "value", "marketValue", "position_value"))),
                    "weight": weight,
                }
            )

    return ensure_required(rows, ["fund_code", "symbol", "report_date"], "fund_holdings")
