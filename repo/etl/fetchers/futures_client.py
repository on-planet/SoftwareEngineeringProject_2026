from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List
import os

from etl.fetchers.snowball_client import _call_kline_with_retry, snowball_session, to_snowball_symbol
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
    try:
        number = float(text)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        try:
            number = int(value)
            if number > 10_000_000_000:
                return datetime.fromtimestamp(number / 1000, tz=timezone.utc).date()
            if number > 1_000_000_000:
                return datetime.fromtimestamp(number, tz=timezone.utc).date()
            text = str(number)
            if len(text) == 8:
                return datetime.strptime(text, "%Y%m%d").date()
        except Exception:
            return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    return None


def _extract_kline_rows(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    columns = data.get("column") or data.get("columns")
    items = data.get("item") or data.get("items")
    if not isinstance(columns, list) or not isinstance(items, list):
        return []
    rows: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            rows.append(item)
            continue
        if not isinstance(item, list):
            continue
        row: dict = {}
        for idx, key in enumerate(columns):
            if idx >= len(item):
                break
            row[str(key)] = item[idx]
        rows.append(row)
    return rows


def _futures_map() -> dict[str, str]:
    raw = os.getenv(
        "SNOWBALL_FUTURES_MAP",
        "GOLD=GC00Y,SILVER=SI00Y,WTI=CL00Y,BRENT=BZ00Y,NATGAS=NG00Y,COPPER=HG00Y",
    )
    output: dict[str, str] = {}
    for item in raw.split(","):
        if "=" not in item:
            continue
        name, symbol = item.split("=", 1)
        name = name.strip().upper()
        symbol = symbol.strip().upper()
        if name and symbol:
            output[name] = symbol
    return output


def _latest_row_on_or_before(rows: list[dict], as_of: date) -> tuple[dict, date] | None:
    best_row: dict | None = None
    best_date: date | None = None
    for row in rows:
        row_date = _to_date(row.get("timestamp") or row.get("time") or row.get("date"))
        if row_date is None or row_date > as_of:
            continue
        if best_row is None or (best_date is not None and row_date > best_date) or best_date is None:
            best_row = row
            best_date = row_date
    if best_row is None or best_date is None:
        return None
    return best_row, best_date


def get_futures_daily(as_of: date) -> List[dict]:
    if ball is None:
        LOGGER.warning("pysnowball unavailable, skip futures")
        return []
    has_token = any(
        os.getenv(name, "").strip()
        for name in ("XUEQIUTOKEN", "SNOWBALL_TOKEN", "XQ_A_TOKEN", "SNOWBALL_A_TOKEN")
    )
    if not has_token:
        LOGGER.warning("missing snowball token env, skip futures")
        return []

    rows: list[dict] = []
    lookback = max(30, int(os.getenv("SNOWBALL_FUTURES_LOOKBACK", "180")))
    with snowball_session():
        for name, raw_symbol in _futures_map().items():
            snow_symbol = to_snowball_symbol(raw_symbol)
            payload = _call_kline_with_retry(
                snow_symbol,
                period="day",
                count=lookback,
                context="snowball futures kline",
            )
            if payload is None:
                continue
            parsed_rows = _extract_kline_rows(payload)
            if not parsed_rows:
                LOGGER.warning("snowball futures payload has no kline rows [%s/%s]", name, snow_symbol)
                continue
            latest = _latest_row_on_or_before(parsed_rows, as_of)
            if latest is None:
                available_dates = sorted(
                    {
                        row_date.isoformat()
                        for row in parsed_rows
                        if (row_date := _to_date(row.get("timestamp") or row.get("time") or row.get("date"))) is not None
                    }
                )
                LOGGER.warning(
                    "snowball futures no row on or before %s [%s/%s], available_dates=%s",
                    as_of,
                    name,
                    snow_symbol,
                    available_dates[-3:],
                )
                continue
            row, row_date = latest
            rows.append(
                {
                    "symbol": name,
                    "name": name,
                    "date": row_date,
                    "open": _safe_float(row.get("open")),
                    "high": _safe_float(row.get("high")),
                    "low": _safe_float(row.get("low")),
                    "close": _safe_float(row.get("close")),
                    "volume": _safe_float(row.get("volume")),
                    "source": "Snowball",
                }
            )
    return ensure_required(rows, ["symbol", "date"], "futures.daily")
