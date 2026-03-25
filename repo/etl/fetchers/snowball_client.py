from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from threading import Lock
from typing import Iterable, List
import json
import os
import re
import shutil
import subprocess
import time

from etl.utils.env import load_project_env
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)
CN_TZ = timezone(timedelta(hours=8))
load_project_env()

try:
    import pysnowball as ball  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    ball = None
    LOGGER.warning("pysnowball import failed: %s", exc)

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    ak = None
    LOGGER.warning("akshare import failed in snowball client: %s", exc)

try:
    import pandas as pd  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    pd = None
    LOGGER.warning("pandas import failed in snowball client: %s", exc)

try:
    import requests  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    requests = None
    LOGGER.warning("requests import failed in snowball client: %s", exc)

_TOKEN_READY = False
_TOKEN_READY_FINGERPRINT = ""
_TOKEN_WARNING_SHOWN = False
_TOKEN_BLOCKED = False
_TOKEN_BLOCKED_VALUE = ""
_TOKEN_BLOCK_WARNING_SHOWN = False
AK_HK_SPOT_CACHE_TTL_SECONDS = max(3, int(os.getenv("AKSHARE_HK_SPOT_CACHE_SECONDS", "12")))
_AK_HK_SPOT_CACHE_TS = 0.0
_AK_HK_SPOT_CACHE_BY_SYMBOL: dict[str, dict] = {}
_AK_HK_SPOT_CACHE_LOCK = Lock()
AK_A_MARGIN_CACHE_TTL_SECONDS = max(60, int(os.getenv("AKSHARE_A_MARGIN_CACHE_SECONDS", "3600")))
AK_A_MARGIN_LOOKBACK_DAYS = max(0, int(os.getenv("AKSHARE_A_MARGIN_LOOKBACK_DAYS", "10")))
HK_KLINE_CURL_FALLBACK_ENABLED = os.getenv("HK_KLINE_CURL_FALLBACK_ENABLED", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}
HK_KLINE_CURL_TIMEOUT_SECONDS = max(5, int(os.getenv("HK_KLINE_CURL_TIMEOUT_SECONDS", "20")))
_AK_A_MARGIN_CACHE_TS = 0.0
_AK_A_MARGIN_CACHE_DATE = ""
_AK_A_MARGIN_CACHE_ROWS: list[dict] = []
_AK_A_MARGIN_CACHE_READY = False
_AK_A_MARGIN_CACHE_LOCK = Lock()
_SYMBOL_RE = re.compile(r"^[A-Z]{2}\d{6}$")
_BJ_SYMBOL_RE = re.compile(r"^BJ\d{6}$")
_HK_SYMBOL_RE = re.compile(r"^HK\d{1,5}$")
_US_SYMBOL_RE = re.compile(r"^US[A-Z.]+$")
_DEFAULT_INDEX_SPECS = (
    {"symbol": "000001.SH", "snowball_symbol": "SH000001", "name": "\u4e0a\u8bc1\u6307\u6570", "market": "A"},
    {"symbol": "399001.SZ", "snowball_symbol": "SZ399001", "name": "\u6df1\u8bc1\u6210\u6307", "market": "A"},
    {"symbol": "399006.SZ", "snowball_symbol": "SZ399006", "name": "\u521b\u4e1a\u677f\u6307", "market": "A"},
    {"symbol": "000016.SH", "snowball_symbol": "SH000016", "name": "\u4e0a\u8bc150", "market": "A"},
    {"symbol": "000300.SH", "snowball_symbol": "SH000300", "name": "\u6caa\u6df1300", "market": "A"},
    {"symbol": "000688.SH", "snowball_symbol": "SH000688", "name": "\u79d1\u521b50", "market": "A"},
    {"symbol": "899050.BJ", "snowball_symbol": "BJ899050", "name": "\u5317\u8bc150", "market": "A"},
    {"symbol": "HKHSI", "snowball_symbol": "HKHSI", "name": "\u6052\u751f\u6307\u6570", "market": "HK"},
    {"symbol": "HKHSCEI", "snowball_symbol": "HKHSCEI", "name": "\u56fd\u4f01\u6307\u6570", "market": "HK"},
    {"symbol": "HKHSTECH", "snowball_symbol": "HKHSTECH", "name": "\u6052\u751f\u79d1\u6280\u6307\u6570", "market": "HK"},
)
_INDEX_ALIAS_MAP = {
    "000001": "000001.SH",
    "000001.SH": "000001.SH",
    "SH000001": "000001.SH",
    "399001": "399001.SZ",
    "399001.SZ": "399001.SZ",
    "SZ399001": "399001.SZ",
    "399006": "399006.SZ",
    "399006.SZ": "399006.SZ",
    "SZ399006": "399006.SZ",
    "000016": "000016.SH",
    "000016.SH": "000016.SH",
    "SH000016": "000016.SH",
    "000300": "000300.SH",
    "000300.SH": "000300.SH",
    "SH000300": "000300.SH",
    "000688": "000688.SH",
    "000688.SH": "000688.SH",
    "SH000688": "000688.SH",
    "899050": "899050.BJ",
    "899050.BJ": "899050.BJ",
    "BJ899050": "899050.BJ",
    "HSI": "HKHSI",
    "HKHSI": "HKHSI",
    "HSCEI": "HKHSCEI",
    "HKHSCEI": "HKHSCEI",
    "HSTECH": "HKHSTECH",
    "HKHSTECH": "HKHSTECH",
}
EASTMONEY_HK_KLINE_ENDPOINT = "https://33.push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_HK_KLINE_FIELDS1 = "f1,f2,f3,f4,f5,f6"
EASTMONEY_HK_KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"


def _safe_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            result = _safe_float(item)
            if result is not None:
                return result
        return None
    if isinstance(value, dict):
        for item in value.values():
            result = _safe_float(item)
            if result is not None:
                return result
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
                return datetime.fromtimestamp(number / 1000.0, tz=CN_TZ).date()
            if number > 1_000_000_000:
                return datetime.fromtimestamp(float(number), tz=CN_TZ).date()
            text = str(number)
            if len(text) == 8:
                return datetime.strptime(text, "%Y%m%d").date()
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    return None


def normalize_symbol(symbol: str) -> str:
    upper = symbol.strip().upper()
    if not upper:
        return upper
    if upper.endswith((".SH", ".SZ", ".BJ", ".HK", ".US")):
        if upper.endswith(".HK"):
            code = upper[:-3]
            if code.isdigit():
                return f"{code.zfill(5)}.HK"
        return upper
    if _SYMBOL_RE.match(upper):
        market = upper[:2]
        code = upper[2:]
        return f"{code}.{market}"
    if _BJ_SYMBOL_RE.match(upper):
        return f"{upper[2:]}.BJ"
    if _HK_SYMBOL_RE.match(upper):
        return f"{upper[2:].zfill(5)}.HK"
    if _US_SYMBOL_RE.match(upper):
        return f"{upper[2:]}.US"
    digits = re.sub(r"\D", "", upper)
    if 1 <= len(digits) <= 5:
        return f"{digits.zfill(5)}.HK"
    if len(digits) == 6 and digits.startswith(("4", "8")):
        return f"{digits}.BJ"
    if len(digits) == 6 and digits.startswith(("5", "6", "9")):
        return f"{digits}.SH"
    if len(digits) == 6:
        return f"{digits}.SZ"
    if upper.isalpha():
        return f"{upper}.US"
    return upper


def normalize_index_symbol(symbol: str) -> str:
    upper = symbol.strip().upper()
    if not upper:
        return upper
    if upper in _INDEX_ALIAS_MAP:
        return _INDEX_ALIAS_MAP[upper]
    normalized = normalize_symbol(upper)
    if normalized in {str(item["symbol"]) for item in _DEFAULT_INDEX_SPECS}:
        return normalized
    return upper


def supported_index_specs() -> list[dict]:
    return [dict(spec) for spec in _index_specs_by_symbol().values()]


def index_name(symbol: str) -> str:
    canonical = normalize_index_symbol(symbol)
    spec = _index_specs_by_symbol().get(canonical)
    return str(spec.get("name") or canonical) if spec else canonical


def index_market(symbol: str) -> str:
    canonical = normalize_index_symbol(symbol)
    spec = _index_specs_by_symbol().get(canonical)
    return str(spec.get("market") or "") if spec else ""


def to_snowball_symbol(symbol: str) -> str:
    upper = symbol.strip().upper()
    canonical_index = _INDEX_ALIAS_MAP.get(upper)
    if canonical_index:
        return _index_map().get(canonical_index, upper)
    if _SYMBOL_RE.match(upper) or _BJ_SYMBOL_RE.match(upper) or _HK_SYMBOL_RE.match(upper) or _US_SYMBOL_RE.match(upper):
        if _HK_SYMBOL_RE.match(upper):
            return f"HK{upper[2:].zfill(5)}"
        return upper
    normalized = normalize_symbol(upper)
    if normalized.endswith(".SH"):
        return f"SH{normalized[:-3]}"
    if normalized.endswith(".SZ"):
        return f"SZ{normalized[:-3]}"
    if normalized.endswith(".BJ"):
        return f"BJ{normalized[:-3]}"
    if normalized.endswith(".HK"):
        return f"HK{normalized[:-3].zfill(5)}"
    if normalized.endswith(".US"):
        return f"US{normalized[:-3]}"
    return normalized


def _snowball_symbol_candidates(symbol: str, *, is_index: bool = False) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(value: str | None) -> None:
        if value in (None, ""):
            return
        token = str(value).strip().upper()
        if not token or token in seen:
            return
        seen.add(token)
        candidates.append(token)

    raw = str(symbol).strip().upper()
    if is_index:
        canonical = normalize_index_symbol(raw)
        _add(_index_map().get(canonical))
        _add(canonical)
        _add(raw)
        return candidates

    normalized = normalize_symbol(raw)
    _add(to_snowball_symbol(normalized))
    _add(normalized)
    _add(raw)
    if normalized.endswith(".HK"):
        code = normalized[:-3]
        digits = re.sub(r"\D", "", code)
        if digits:
            padded = digits.zfill(5)
            unpadded = str(int(digits))
            _add(f"HK{padded}")
            _add(f"HK{unpadded}")
            _add(padded)
            _add(unpadded)
    elif normalized.endswith((".SH", ".SZ")):
        market = normalized[-2:]
        code = normalized[:-3]
        _add(f"{market}{code}")
        _add(code)
    elif normalized.endswith(".US"):
        code = normalized[:-3]
        _add(f"US{code}")
        _add(code)
    return candidates


def from_snowball_symbol(symbol: str) -> str:
    upper = symbol.strip().upper()
    reverse_index_map = {snowball_symbol: local_symbol for local_symbol, snowball_symbol in _index_map().items()}
    if upper in reverse_index_map:
        return reverse_index_map[upper]
    if upper.startswith(("SH", "SZ")) and len(upper) == 8 and upper[2:].isdigit():
        return f"{upper[2:]}.{upper[:2]}"
    if upper.startswith("BJ") and len(upper) == 8 and upper[2:].isdigit():
        return f"{upper[2:]}.BJ"
    if upper.startswith("HK") and len(upper) >= 6:
        return f"{upper[2:].zfill(5)}.HK"
    if upper.startswith("US") and len(upper) > 2:
        return f"{upper[2:]}.US"
    return normalize_symbol(upper)


def market_from_symbol(symbol: str) -> str:
    normalized = normalize_index_symbol(symbol) if symbol in _index_specs_by_symbol() else normalize_symbol(symbol)
    if normalized.endswith(".HK"):
        return "HK"
    if normalized.endswith((".SH", ".SZ", ".BJ")):
        return "A"
    return "US"


def _parse_env_symbols(env_name: str) -> list[str]:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return []
    output: list[str] = []
    for item in raw.split(","):
        token = item.strip()
        if token:
            output.append(normalize_symbol(token))
    return output


def _parse_env_keywords(env_name: str) -> list[str]:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return []
    output: list[str] = []
    for item in raw.split(","):
        token = item.strip()
        if token:
            output.append(token.upper())
    return output


def _stock_universe() -> list[str]:
    symbols = _parse_env_symbols("SNOWBALL_STOCK_SYMBOLS")
    if not symbols:
        a_rows = get_market_stock_pool("A", limit=int(os.getenv("SNOWBALL_A_SHARE_LIMIT", "100")))
        hk_rows = get_market_stock_pool("HK", limit=int(os.getenv("SNOWBALL_HK_LIMIT", "100")))
        symbols = [row["symbol"] for row in a_rows + hk_rows if row.get("symbol")]
    deduped: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _limit_symbols(symbols: list[str]) -> list[str]:
    limit = int(os.getenv("SNOWBALL_STOCK_BASIC_LIMIT", "0"))
    if limit <= 0:
        return symbols
    return symbols[:limit]


def _ensure_token() -> bool:
    global _TOKEN_READY, _TOKEN_READY_FINGERPRINT
    global _TOKEN_WARNING_SHOWN, _TOKEN_BLOCKED, _TOKEN_BLOCKED_VALUE, _TOKEN_BLOCK_WARNING_SHOWN
    if ball is None:
        return False
    candidates = _token_candidates()
    fingerprint = "||".join(candidates)
    if not candidates:
        if not _TOKEN_WARNING_SHOWN:
            LOGGER.warning(
                "missing Snowball token; set one of XUEQIUTOKEN/SNOWBALL_TOKEN/XQ_A_TOKEN "
                "(optionally with XUEQIU_U/SNOWBALL_U)"
            )
            _TOKEN_WARNING_SHOWN = True
        return False
    if _TOKEN_BLOCKED and fingerprint != _TOKEN_BLOCKED_VALUE:
        _TOKEN_BLOCKED = False
        _TOKEN_BLOCKED_VALUE = ""
        _TOKEN_BLOCK_WARNING_SHOWN = False
    if _TOKEN_BLOCKED and fingerprint == _TOKEN_BLOCKED_VALUE:
        if not _TOKEN_BLOCK_WARNING_SHOWN:
            LOGGER.warning("snowball token is blocked by upstream (400016); update token to recover token APIs")
            _TOKEN_BLOCK_WARNING_SHOWN = True
        return False
    if _TOKEN_READY and _TOKEN_READY_FINGERPRINT == fingerprint:
        return True
    if _TOKEN_READY and _TOKEN_READY_FINGERPRINT != fingerprint:
        _TOKEN_READY = False
        _TOKEN_READY_FINGERPRINT = ""
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            ball.set_token(candidate)
            _TOKEN_READY = True
            _TOKEN_READY_FINGERPRINT = fingerprint
            return True
        except Exception as exc:
            last_error = exc
            continue
    if last_error is not None:
        LOGGER.warning("set snowball token failed: %s", last_error)
    return False


def _refresh_token() -> bool:
    global _TOKEN_READY, _TOKEN_READY_FINGERPRINT
    _TOKEN_READY = False
    _TOKEN_READY_FINGERPRINT = ""
    return _ensure_token()


def _block_current_token() -> None:
    global _TOKEN_READY, _TOKEN_READY_FINGERPRINT
    global _TOKEN_BLOCKED, _TOKEN_BLOCKED_VALUE, _TOKEN_BLOCK_WARNING_SHOWN
    fingerprint = "||".join(_token_candidates())
    _TOKEN_READY = False
    _TOKEN_READY_FINGERPRINT = ""
    if not fingerprint:
        return
    _TOKEN_BLOCKED = True
    _TOKEN_BLOCKED_VALUE = fingerprint
    _TOKEN_BLOCK_WARNING_SHOWN = False


def _exception_text(exc: Exception) -> str:
    if exc.args:
        first = exc.args[0]
        if isinstance(first, (bytes, bytearray)):
            try:
                return first.decode("utf-8", errors="ignore")
            except Exception:
                return str(first)
        if isinstance(first, str):
            return first
    return str(exc)


def _call_with_token_retry(request_fn, *, context: str, ref: str):
    if ball is None or not _ensure_token():
        return None
    for attempt in range(2):
        try:
            return request_fn()
        except Exception as exc:
            if _is_windows_socket_block_error(exc):
                LOGGER.info("%s network blocked [%s]: %s", context, ref, exc)
                return None
            if attempt == 0 and _is_auth_error(exc):
                LOGGER.warning("%s auth expired [%s], refreshing token and retry", context, ref)
                if _refresh_token():
                    continue
            if _is_auth_error(exc):
                _block_current_token()
                LOGGER.warning("%s auth rejected [%s], token blocked for this run (400016)", context, ref)
                return None
            LOGGER.warning("%s failed [%s]: %s", context, ref, exc)
            return None
    return None


def _token_candidates() -> list[str]:
    raw_env = (
        os.getenv("XUEQIUTOKEN", "").strip()
        or os.getenv("SNOWBALL_TOKEN", "").strip()
        or os.getenv("XQ_A_TOKEN", "").strip()
        or os.getenv("SNOWBALL_A_TOKEN", "").strip()
    )
    xq_a = os.getenv("XQ_A_TOKEN", "").strip() or os.getenv("SNOWBALL_A_TOKEN", "").strip()
    user_id = os.getenv("XUEQIU_U", "").strip() or os.getenv("XUEQIU_UID", "").strip() or os.getenv("SNOWBALL_U", "").strip()
    candidates: list[str] = []

    # Full cookie string (e.g. "xq_a_token=...;u=...")
    if raw_env and "xq_a_token=" in raw_env:
        candidates.append(raw_env)
    # xq_a_token provided without key
    if raw_env and "=" not in raw_env and ";" not in raw_env:
        candidates.append(f"xq_a_token={raw_env}")
    # Explicit xq_a_token env
    if xq_a:
        if xq_a.startswith("xq_a_token="):
            candidates.append(xq_a)
        else:
            candidates.append(f"xq_a_token={xq_a}")
    # If raw is already key=value but not full cookie, keep original as fallback
    if raw_env and raw_env not in candidates:
        candidates.append(raw_env)

    if user_id:
        with_u: list[str] = []
        u_part = user_id if user_id.startswith("u=") else f"u={user_id}"
        for token in candidates:
            if "xq_a_token=" not in token:
                continue
            if ";u=" in token:
                with_u.append(token)
            else:
                with_u.append(f"{token};{u_part}")
        candidates = with_u + candidates

    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        token = item.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def _is_auth_error(exc: Exception) -> bool:
    text = _exception_text(exc)
    return "400016" in text or "重新登录" in text or "登录" in text


def _call_kline_with_retry(
    snow_symbol: str,
    *,
    period: str,
    count: int,
    context: str,
):
    return _call_with_token_retry(
        lambda: ball.kline(snow_symbol, period=period, count=count),
        context=context,
        ref=snow_symbol,
    )


def _extract_payload_items(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("list", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if isinstance(data.get("quote"), dict):
            return [data["quote"]]
        return [data]
    return []


def _extract_primary_record(payload, *, symbol: str | None = None, preferred_keys: Iterable[str] = ()) -> dict:
    candidates = _extract_payload_items(payload) + _extract_dict_rows(payload)
    normalized_symbol = normalize_symbol(symbol) if symbol else None
    snow_symbol = to_snowball_symbol(symbol) if symbol else None
    best: dict | None = None
    best_score = -1
    for row in candidates:
        if not isinstance(row, dict) or not row:
            continue
        score = 0
        raw_symbol = _pick(row, ("symbol", "code", "ticker", "stock_symbol", "quote_symbol"))
        if raw_symbol not in (None, ""):
            row_symbol = normalize_symbol(str(raw_symbol))
            if normalized_symbol and row_symbol == normalized_symbol:
                score += 10
            if snow_symbol and str(raw_symbol).strip().upper() == snow_symbol:
                score += 10
        for key in preferred_keys:
            if row.get(key) not in (None, "", [], {}):
                score += 1
        if score > best_score:
            best = row
            best_score = score
    return best or {}


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


def _to_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, (int, float)):
        try:
            number = int(value)
            if number > 10_000_000_000:
                return datetime.fromtimestamp(number / 1000.0, tz=CN_TZ)
            if number > 1_000_000_000:
                return datetime.fromtimestamp(float(number), tz=CN_TZ)
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:19], fmt)
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


def _latest_kline_row_on_or_before(rows: list[dict], as_of: date) -> tuple[dict, date] | None:
    best_row: dict | None = None
    best_date: date | None = None
    for row in rows:
        row_date = _to_date(row.get("timestamp") or row.get("time") or row.get("date"))
        if row_date is None or row_date > as_of:
            continue
        if best_row is None or best_date is None or row_date > best_date:
            best_row = row
            best_date = row_date
    if best_row is None or best_date is None:
        return None
    return best_row, best_date


def _extract_row_symbol(item: dict) -> str | None:
    raw_symbol = _pick(item, ("symbol", "code", "ticker", "stock_symbol", "quote_symbol"))
    if raw_symbol in (None, ""):
        return None
    return normalize_symbol(str(raw_symbol))


def _call_quotec_single(symbol: str) -> dict | None:
    if ball is None:
        return None
    normalized = normalize_symbol(symbol)
    for candidate in _snowball_symbol_candidates(normalized):
        try:
            payload = ball.quotec(candidate)
        except Exception:
            continue
        rows = _extract_payload_items(payload)
        if not rows:
            continue
        record = _extract_primary_record(
            {"data": rows},
            symbol=normalized,
            preferred_keys=("current", "price", "volume", "high", "low"),
        )
        if record:
            return record
        return rows[0]
    return None


def _call_quotec(symbols: list[str]) -> list[dict]:
    if ball is None:
        return []
    chunk_size = max(1, int(os.getenv("SNOWBALL_QUOTEC_BATCH_SIZE", "80")))
    output: list[dict] = []
    for idx in range(0, len(symbols), chunk_size):
        chunk = symbols[idx : idx + chunk_size]
        snowball_symbols = ",".join(to_snowball_symbol(symbol) for symbol in chunk)
        try:
            payload = ball.quotec(snowball_symbols)
        except Exception as exc:
            LOGGER.warning("snowball quotec failed for batch size=%s: %s", len(chunk), exc)
            continue
        rows = _extract_payload_items(payload)
        output.extend(rows)
        found = {normalized for normalized in (_extract_row_symbol(item) for item in rows) if normalized}
        for symbol in chunk:
            normalized = normalize_symbol(symbol)
            if normalized in found:
                continue
            recovered = _call_quotec_single(normalized)
            if recovered:
                output.append(recovered)
    return output


def _pick_frame_column(columns: Iterable[object], candidates: Iterable[str]) -> str | None:
    column_map = {str(item).strip().lower(): str(item) for item in columns}
    for candidate in candidates:
        value = column_map.get(str(candidate).strip().lower())
        if value:
            return value
    return None


def _is_windows_socket_block_error(exc: Exception) -> bool:
    text = str(exc or "")
    return "WinError 10013" in text or "access permissions" in text.lower() or "访问权限不允许" in text


def _safe_text(value: object, *, max_length: int = 256) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return compact[:max_length].strip()


def _to_record_dicts(frame) -> list[dict]:
    if frame is None:
        return []
    if isinstance(frame, list):
        return [item for item in frame if isinstance(item, dict)]
    if isinstance(frame, dict):
        return [frame]
    to_dict = getattr(frame, "to_dict", None)
    if not callable(to_dict):
        return []
    try:
        records = to_dict(orient="records")
    except TypeError:
        try:
            records = to_dict("records")
        except Exception:
            return []
    except Exception:
        return []
    if not isinstance(records, list):
        return []
    return [item for item in records if isinstance(item, dict)]


def _a_symbol_code(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if "." not in normalized:
        return normalized
    return normalized.split(".", 1)[0]


def _hk_symbol_code(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if not normalized.endswith(".HK"):
        return normalized
    code = normalized[:-3]
    digits = re.sub(r"\D", "", code)
    if not digits:
        return code
    return digits.zfill(5)


def _fetch_ak_a_margin_snapshot_compat(date_key: str) -> list[dict]:
    if pd is None or requests is None:
        return []
    url = "https://www.szse.cn/api/report/ShowReport"
    params = {
        "SHOWTYPE": "xlsx",
        "CATALOGID": "1834_xxpl",
        "txtDate": "-".join([date_key[:4], date_key[4:6], date_key[6:]]),
        "tab1PAGENO": "1",
        "random": "0.7425245522795993",
        "TABKEY": "tab1",
    }
    headers = {
        "Referer": "https://www.szse.cn/disclosure/margin/object/index.html",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as exc:
        LOGGER.warning("akshare szse margin compat request failed [%s]: %s", date_key, exc)
        return []
    try:
        frame = pd.read_excel(BytesIO(response.content), engine="openpyxl", dtype={"证券代码": str})
    except Exception as exc:
        LOGGER.warning("akshare szse margin compat parse failed [%s]: %s", date_key, exc)
        return []
    return _to_record_dicts(frame)


def _load_ak_a_margin_snapshot(*, as_of: date | None = None) -> tuple[list[dict], str]:
    global _AK_A_MARGIN_CACHE_TS, _AK_A_MARGIN_CACHE_DATE, _AK_A_MARGIN_CACHE_ROWS, _AK_A_MARGIN_CACHE_READY
    if ak is None:
        return [], ""
    fetch_fn = getattr(ak, "stock_margin_underlying_info_szse", None)
    if fetch_fn is None:
        return [], ""

    now = time.monotonic()
    with _AK_A_MARGIN_CACHE_LOCK:
        if _AK_A_MARGIN_CACHE_READY and (now - _AK_A_MARGIN_CACHE_TS) <= AK_A_MARGIN_CACHE_TTL_SECONDS:
            return list(_AK_A_MARGIN_CACHE_ROWS), _AK_A_MARGIN_CACHE_DATE

    base_date = as_of or date.today()
    rows: list[dict] = []
    snapshot_date = ""
    for delta in range(AK_A_MARGIN_LOOKBACK_DAYS + 1):
        probe = base_date - timedelta(days=delta)
        probe_key = probe.strftime("%Y%m%d")
        try:
            frame = fetch_fn(date=probe_key)
            records = _to_record_dicts(frame)
        except Exception as exc:
            text = str(exc)
            if "Expected file path name or file-like object, got <class 'bytes'> type" in text:
                records = _fetch_ak_a_margin_snapshot_compat(probe_key)
            else:
                LOGGER.warning("akshare szse margin fetch failed [%s]: %s", probe_key, exc)
                continue
        if not records:
            continue
        rows = records
        snapshot_date = probe_key
        break

    with _AK_A_MARGIN_CACHE_LOCK:
        _AK_A_MARGIN_CACHE_TS = time.monotonic()
        _AK_A_MARGIN_CACHE_DATE = snapshot_date
        _AK_A_MARGIN_CACHE_ROWS = list(rows)
        _AK_A_MARGIN_CACHE_READY = True
        return list(_AK_A_MARGIN_CACHE_ROWS), _AK_A_MARGIN_CACHE_DATE


def _build_ak_a_margin_research_rows(symbol: str, *, limit: int = 10) -> list[dict]:
    normalized = normalize_symbol(symbol)
    if not normalized.endswith(".SZ"):
        return []
    snapshot_rows, snapshot_key = _load_ak_a_margin_snapshot()
    if not snapshot_rows:
        return []

    sample = snapshot_rows[0]
    code_col = _pick_frame_column(
        sample.keys(),
        ("code", "symbol", "security_code", "\u8bc1\u5238\u4ee3\u7801", "\u4ee3\u7801", "\u80a1\u7968\u4ee3\u7801"),
    )
    name_col = _pick_frame_column(
        sample.keys(),
        ("name", "security_name", "stock_name", "\u8bc1\u5238\u7b80\u79f0", "\u8bc1\u5238\u540d\u79f0", "\u7b80\u79f0"),
    )
    if not code_col:
        return []

    matched: dict | None = None
    target_code = _a_symbol_code(normalized)
    for row in snapshot_rows:
        raw_code = _safe_text(row.get(code_col), max_length=32)
        if not raw_code:
            continue
        digits = re.sub(r"\D", "", raw_code)
        code = digits[-6:] if len(digits) >= 6 else raw_code
        if code == target_code:
            matched = row
            break
    if not matched:
        return []

    published_at = _to_datetime(snapshot_key) if snapshot_key else None
    name = _safe_text(matched.get(name_col), max_length=64) if name_col else normalized
    summary_parts: list[str] = []
    for key in (
        "\u878d\u8d44\u4e70\u5165\u6807\u7684",
        "\u878d\u5238\u5356\u51fa\u6807\u7684",
        "\u878d\u8d44\u4fdd\u8bc1\u91d1\u6bd4\u4f8b",
        "\u878d\u5238\u4fdd\u8bc1\u91d1\u6bd4\u4f8b",
        "\u6807\u7684\u8bc1\u5238\u7c7b\u578b",
    ):
        if key not in matched:
            continue
        value = _safe_text(matched.get(key), max_length=64)
        if not value:
            continue
        summary_parts.append(f"{key}:{value}")
    summary = " | ".join(summary_parts)
    row = {
        "title": f"{name or normalized} SZSE margin underlying",
        "published_at": published_at,
        "link": "",
        "summary": summary,
        "institution": "SZSE",
        "rating": "\u878d\u8d44\u878d\u5238",
        "source": "AkShare SZSE Margin Underlying",
    }
    return [row][: max(1, limit)]


def _build_ak_hk_profit_forecast_rows(symbol: str, *, limit: int = 10) -> list[dict]:
    normalized = normalize_symbol(symbol)
    if not normalized.endswith(".HK") or ak is None:
        return []
    fetch_fn = getattr(ak, "stock_hk_profit_forecast_et", None)
    if fetch_fn is None:
        return []

    code = _hk_symbol_code(normalized)
    indicators = ("\u76c8\u5229\u9884\u6d4b\u6982\u89c8", "\u76c8\u5229\u9884\u6d4b")
    frame = None
    last_exception: Exception | None = None
    no_data_indicators: list[str] = []
    for indicator in indicators:
        try:
            frame = fetch_fn(symbol=code, indicator=indicator)
            break
        except Exception as exc:
            last_exception = exc
            message = str(exc).lower()
            if isinstance(exc, IndexError) or "list index out of range" in message or "out of bounds" in message:
                no_data_indicators.append(indicator)
                continue
            LOGGER.warning("akshare hk profit forecast fetch failed [%s] indicator=%s: %s", normalized, indicator, exc)
            return []
    if frame is None:
        if no_data_indicators:
            LOGGER.info(
                "akshare hk profit forecast no data [%s] indicators=%s",
                normalized,
                ",".join(no_data_indicators),
            )
        elif last_exception is not None:
            LOGGER.info("akshare hk profit forecast unavailable [%s]: %s", normalized, last_exception)
        return []

    records = _to_record_dicts(frame)
    if not records:
        return []

    sample = records[0]
    institution_col = _pick_frame_column(
        sample.keys(),
        ("institution", "org", "broker", "\u673a\u6784", "\u7814\u62a5\u673a\u6784", "\u8bc1\u5238\u516c\u53f8"),
    )
    rating_col = _pick_frame_column(
        sample.keys(),
        ("rating", "latest_rating", "\u8bc4\u7ea7", "\u6700\u65b0\u8bc4\u7ea7", "\u6295\u8d44\u8bc4\u7ea7"),
    )
    date_col = _pick_frame_column(
        sample.keys(),
        ("date", "publish_date", "report_date", "\u65e5\u671f", "\u53d1\u5e03\u65e5\u671f", "\u7814\u62a5\u65e5\u671f"),
    )
    link_col = _pick_frame_column(sample.keys(), ("url", "link", "\u94fe\u63a5", "\u516c\u544a\u5730\u5740"))
    title_col = _pick_frame_column(sample.keys(), ("title", "report_title", "\u6807\u9898", "\u5185\u5bb9"))

    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        institution = _safe_text(record.get(institution_col), max_length=128) if institution_col else ""
        rating = _safe_text(record.get(rating_col), max_length=128) if rating_col else ""
        published_at = _to_datetime(record.get(date_col)) if date_col else None
        link = _safe_text(record.get(link_col), max_length=512) if link_col else ""
        explicit_title = _safe_text(record.get(title_col), max_length=160) if title_col else ""
        if explicit_title:
            title = explicit_title
        elif institution and rating:
            title = f"{institution} profit forecast ({rating})"
        elif institution:
            title = f"{institution} profit forecast"
        else:
            title = f"{normalized} profit forecast"

        summary_parts: list[str] = []
        for key, value in record.items():
            if value in (None, "", [], {}):
                continue
            key_text = _safe_text(key, max_length=32)
            value_text = _safe_text(value, max_length=48)
            if not key_text or not value_text:
                continue
            if key_text.lower() in {
                str(institution_col or "").lower(),
                str(rating_col or "").lower(),
                str(date_col or "").lower(),
                str(link_col or "").lower(),
                str(title_col or "").lower(),
            }:
                continue
            summary_parts.append(f"{key_text}:{value_text}")
            if len(summary_parts) >= 5:
                break
        summary = " | ".join(summary_parts)
        dedupe_key = (
            title,
            published_at.isoformat() if published_at else "",
            link,
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        rows.append(
            {
                "title": title,
                "published_at": published_at,
                "link": link,
                "summary": summary,
                "institution": institution,
                "rating": rating,
                "source": "AkShare HK Profit Forecast",
            }
        )
    rows.sort(key=lambda item: item.get("published_at") or datetime.min, reverse=True)
    return rows[: max(1, limit)]


def _normalize_hk_quote_symbol(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return ""
    return f"{digits.zfill(5)}.HK"


def _build_ak_hk_spot_cache(df) -> dict[str, dict]:
    if pd is None or df is None or getattr(df, "empty", True):
        return {}
    symbol_col = _pick_frame_column(df.columns, ("代码", "代號", "code", "symbol", "证券代码", "股票代码"))
    if not symbol_col:
        return {}
    name_col = _pick_frame_column(df.columns, ("名称", "name", "简称", "证券简称", "股票名称"))
    current_col = _pick_frame_column(df.columns, ("最新价", "最新", "最新價", "price", "current", "last"))
    change_col = _pick_frame_column(df.columns, ("涨跌额", "漲跌額", "change", "chg"))
    percent_col = _pick_frame_column(df.columns, ("涨跌幅", "漲跌幅", "percent", "pct", "chg_percent"))
    open_col = _pick_frame_column(df.columns, ("今开", "今開", "open"))
    high_col = _pick_frame_column(df.columns, ("最高", "high"))
    low_col = _pick_frame_column(df.columns, ("最低", "low"))
    last_close_col = _pick_frame_column(df.columns, ("昨收", "昨收盘", "昨收盤", "preclose", "last_close", "prev_close"))
    volume_col = _pick_frame_column(df.columns, ("成交量", "volume", "vol"))
    amount_col = _pick_frame_column(df.columns, ("成交额", "成交額", "amount", "turnover"))

    normalized_df = df.where(pd.notna(df), None)
    now = datetime.now(tz=CN_TZ)
    by_symbol: dict[str, dict] = {}
    for record in normalized_df.to_dict(orient="records"):
        symbol = _normalize_hk_quote_symbol(record.get(symbol_col))
        if not symbol:
            continue
        by_symbol[symbol] = {
            "symbol": symbol,
            "name": str(record.get(name_col) or symbol) if name_col else symbol,
            "current": _safe_float(record.get(current_col)) if current_col else None,
            "change": _safe_float(record.get(change_col)) if change_col else None,
            "percent": _safe_float(record.get(percent_col)) if percent_col else None,
            "open": _safe_float(record.get(open_col)) if open_col else None,
            "high": _safe_float(record.get(high_col)) if high_col else None,
            "low": _safe_float(record.get(low_col)) if low_col else None,
            "last_close": _safe_float(record.get(last_close_col)) if last_close_col else None,
            "volume": _safe_float(record.get(volume_col)) if volume_col else None,
            "amount": _safe_float(record.get(amount_col)) if amount_col else None,
            "timestamp": now,
        }
    return by_symbol


def _fetch_ak_hk_spot_cache() -> dict[str, dict]:
    if ak is None or pd is None:
        return {}
    fetch_fn = getattr(ak, "stock_hk_spot", None) or getattr(ak, "stock_hk_spot_em", None)
    if fetch_fn is None:
        return {}
    try:
        frame = fetch_fn()
    except Exception as exc:
        LOGGER.warning("akshare hk spot fetch failed: %s", exc)
        return {}
    return _build_ak_hk_spot_cache(frame)


def _get_ak_hk_spot_quote(symbol: str, *, allow_refresh: bool = False) -> dict:
    global _AK_HK_SPOT_CACHE_TS, _AK_HK_SPOT_CACHE_BY_SYMBOL
    normalized = normalize_symbol(symbol)
    if not normalized.endswith(".HK"):
        return {}
    now = time.monotonic()
    with _AK_HK_SPOT_CACHE_LOCK:
        cache_hit = (
            _AK_HK_SPOT_CACHE_BY_SYMBOL
            and (now - _AK_HK_SPOT_CACHE_TS) <= AK_HK_SPOT_CACHE_TTL_SECONDS
            and normalized in _AK_HK_SPOT_CACHE_BY_SYMBOL
        )
        if cache_hit:
            return dict(_AK_HK_SPOT_CACHE_BY_SYMBOL.get(normalized) or {})

    if not allow_refresh:
        return {}

    refreshed = _fetch_ak_hk_spot_cache()
    with _AK_HK_SPOT_CACHE_LOCK:
        if refreshed:
            _AK_HK_SPOT_CACHE_TS = time.monotonic()
            _AK_HK_SPOT_CACHE_BY_SYMBOL = refreshed
        return dict(_AK_HK_SPOT_CACHE_BY_SYMBOL.get(normalized) or {})


def _fetch_ak_hk_kline_history(
    symbol: str,
    *,
    period: str,
    count: int,
    as_of: date | None = None,
) -> list[dict]:
    if ak is None or pd is None:
        return []
    normalized = normalize_symbol(symbol)
    if not normalized.endswith(".HK"):
        return []
    code = _hk_symbol_code(normalized)

    def _curl_fallback_rows() -> list[dict]:
        if period not in {"day", "week", "month"}:
            return []
        return _fetch_eastmoney_hk_kline_history_via_curl(
            normalized,
            period=period,
            count=count,
            as_of=as_of,
        )

    rows: list[dict] = []
    if period in {"1m", "30m", "60m"}:
        fetch_fn = getattr(ak, "stock_hk_hist_min_em", None)
        if fetch_fn is None:
            return []
        period_map = {"1m": "1", "30m": "30", "60m": "60"}
        end_at = as_of or date.today()
        try:
            frame = fetch_fn(
                symbol=code,
                period=period_map[period],
                adjust="",
                start_date="1979-09-01 09:32:00",
                end_date=f"{end_at.isoformat()} 23:59:59",
            )
        except Exception as exc:
            LOGGER.warning("akshare hk kline fetch failed [%s %s]: %s", normalized, period, exc)
            return []
        for record in _to_record_dicts(frame):
            row_time = _to_datetime(
                _pick(record, ("\u65f6\u95f4", "\u65e5\u671f", "time", "datetime", "date", "timestamp"))
            )
            if row_time is None:
                continue
            if as_of is not None and row_time.date() > as_of:
                continue
            open_val = _safe_float(_pick(record, ("\u5f00\u76d8", "open")))
            high_val = _safe_float(_pick(record, ("\u6700\u9ad8", "high")))
            low_val = _safe_float(_pick(record, ("\u6700\u4f4e", "low")))
            close_val = _safe_float(_pick(record, ("\u6536\u76d8", "\u6700\u65b0\u4ef7", "close", "price")))
            volume_val = _safe_float(_pick(record, ("\u6210\u4ea4\u91cf", "volume")))
            if None in (open_val, high_val, low_val, close_val, volume_val):
                continue
            rows.append(
                {
                    "symbol": normalized,
                    "date": row_time,
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "close": close_val,
                    "volume": volume_val,
                }
            )
    elif period in {"day", "week", "month"}:
        fetch_fn = getattr(ak, "stock_hk_hist", None)
        if fetch_fn is None:
            return []
        period_map = {"day": "daily", "week": "weekly", "month": "monthly"}
        end_at = as_of or date.today()
        lookback_days = {"day": max(400, count * 3), "week": max(800, count * 14), "month": max(1500, count * 40)}[period]
        start_at = end_at - timedelta(days=lookback_days)
        try:
            frame = fetch_fn(
                symbol=code,
                period=period_map[period],
                start_date=start_at.strftime("%Y%m%d"),
                end_date=end_at.strftime("%Y%m%d"),
                adjust="",
            )
        except Exception as exc:
            if _is_windows_socket_block_error(exc):
                LOGGER.info("akshare hk kline python network blocked [%s %s]: %s", normalized, period, exc)
                return _curl_fallback_rows()
            LOGGER.warning("akshare hk kline fetch failed [%s %s]: %s", normalized, period, exc)
            return []
        for record in _to_record_dicts(frame):
            row_date = _to_date(_pick(record, ("\u65e5\u671f", "\u65f6\u95f4", "date", "time")))
            if row_date is None:
                continue
            if as_of is not None and row_date > as_of:
                continue
            open_val = _safe_float(_pick(record, ("\u5f00\u76d8", "open")))
            high_val = _safe_float(_pick(record, ("\u6700\u9ad8", "high")))
            low_val = _safe_float(_pick(record, ("\u6700\u4f4e", "low")))
            close_val = _safe_float(_pick(record, ("\u6536\u76d8", "close")))
            volume_val = _safe_float(_pick(record, ("\u6210\u4ea4\u91cf", "volume")))
            if None in (open_val, high_val, low_val, close_val, volume_val):
                continue
            rows.append(
                {
                    "symbol": normalized,
                    "date": row_date,
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "close": close_val,
                    "volume": volume_val,
                }
            )
        if not rows:
            return _curl_fallback_rows()
    else:
        return []

    rows.sort(key=lambda item: (item.get("date") or datetime.min, str(item.get("symbol") or "")))
    if count > 0:
        rows = rows[-count:]
    return rows


def _fetch_eastmoney_hk_kline_history_via_curl(
    symbol: str,
    *,
    period: str,
    count: int,
    as_of: date | None = None,
) -> list[dict]:
    if not HK_KLINE_CURL_FALLBACK_ENABLED:
        return []
    if period not in {"day", "week", "month"}:
        return []
    normalized = normalize_symbol(symbol)
    if not normalized.endswith(".HK"):
        return []
    code = _hk_symbol_code(normalized)
    klt_map = {"day": "101", "week": "102", "month": "103"}
    curl_path = shutil.which("curl.exe") or shutil.which("curl")
    if not curl_path:
        return []
    command = [
        curl_path,
        "-L",
        "-sS",
        EASTMONEY_HK_KLINE_ENDPOINT,
        "--get",
        "--data-urlencode",
        f"secid=116.{code}",
        "--data-urlencode",
        f"fields1={EASTMONEY_HK_KLINE_FIELDS1}",
        "--data-urlencode",
        f"fields2={EASTMONEY_HK_KLINE_FIELDS2}",
        "--data-urlencode",
        f"klt={klt_map[period]}",
        "--data-urlencode",
        "fqt=0",
        "--data-urlencode",
        "end=20500000",
        "--data-urlencode",
        "lmt=1000000",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=HK_KLINE_CURL_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as exc:
        LOGGER.warning("curl hk kline fetch failed [%s %s]: %s", normalized, period, exc)
        return []
    if completed.returncode != 0 or not str(completed.stdout or "").strip():
        stderr = str(completed.stderr or "").strip()
        if stderr:
            LOGGER.warning("curl hk kline fetch failed [%s %s]: %s", normalized, period, stderr)
        return []
    try:
        payload = json.loads(completed.stdout)
    except Exception as exc:
        LOGGER.warning("curl hk kline parse failed [%s %s]: %s", normalized, period, exc)
        return []
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    if not isinstance(klines, list):
        return []
    rows: list[dict] = []
    for item in klines:
        parts = str(item or "").split(",")
        if len(parts) < 6:
            continue
        row_date = _to_date(parts[0])
        if row_date is None:
            continue
        if as_of is not None and row_date > as_of:
            continue
        open_val = _safe_float(parts[1])
        close_val = _safe_float(parts[2])
        high_val = _safe_float(parts[3])
        low_val = _safe_float(parts[4])
        volume_val = _safe_float(parts[5])
        if None in (open_val, high_val, low_val, close_val, volume_val):
            continue
        rows.append(
            {
                "symbol": normalized,
                "date": row_date,
                "open": open_val,
                "high": high_val,
                "low": low_val,
                "close": close_val,
                "volume": volume_val,
            }
        )
    rows.sort(key=lambda item: (item.get("date") or datetime.min.date(), str(item.get("symbol") or "")))
    if count > 0:
        rows = rows[-count:]
    return rows


def _fetch_snowball_kline_history(
    symbol: str,
    *,
    period: str,
    count: int,
    as_of: date | None = None,
    is_index: bool = False,
) -> list[dict]:
    if ball is None or not _ensure_token():
        return []
    for snow_symbol in _snowball_symbol_candidates(symbol, is_index=is_index):
        payload = _call_kline_with_retry(
            snow_symbol,
            period=period,
            count=max(30, count),
            context="snowball kline history",
        )
        if payload is None:
            continue
        rows = _parse_kline_history_rows(
            symbol,
            _extract_kline_rows(payload),
            as_of=as_of,
            preserve_time=period in {"1m", "30m", "60m"},
        )
        if rows:
            return ensure_required(
                rows,
                ["symbol", "date", "open", "high", "low", "close", "volume"],
                "snowball.kline_history",
            )
    return []


def _extract_name(item: dict, fallback: str) -> str:
    for key in ("name", "n", "display_name", "stock_name"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return fallback


def _extract_sector(item: dict) -> str:
    for key in ("industry_name", "industry", "sector_name", "sector"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return "Unknown"


def _search_seed_queries(market: str) -> list[str]:
    normalized_market = market.upper()
    if normalized_market == "A":
        return _parse_env_keywords("SNOWBALL_A_POOL_SEEDS") or [
            "SH600",
            "SH601",
            "SH603",
            "SH605",
            "SH688",
            "SZ000",
            "SZ001",
            "SZ002",
            "SZ003",
            "SZ300",
            "SZ301",
        ]
    if normalized_market == "HK":
        return _parse_env_keywords("SNOWBALL_HK_POOL_SEEDS") or [
            "HK0",
            "HK1",
            "HK2",
            "HK3",
            "HK6",
            "HK8",
            "HK9",
        ]
    return _parse_env_keywords("SNOWBALL_US_POOL_SEEDS") or ["USA", "USB", "USC", "USD"]




def _has_hk_market_hint(*values) -> bool:
    for value in values:
        text = str(value or "").strip().upper()
        if not text:
            continue
        if any(token in text for token in ("HK", "HKG", "SEHK", "HONG KONG")):
            return True
    return False


def _normalize_search_symbol(item: dict) -> str | None:
    raw_symbol = _pick(item, ("symbol", "ticker", "stock_symbol", "quote_symbol"))
    if raw_symbol not in (None, ""):
        normalized = normalize_symbol(str(raw_symbol))
        if normalized.endswith((".SH", ".SZ", ".HK", ".US")):
            return normalized

    code = _pick(item, ("code", "stock_code", "ticker", "stock_id"))
    if code in (None, ""):
        return None
    code_text = str(code).strip().upper()
    if not code_text:
        return None
    if code_text.startswith(("SH", "SZ", "HK", "US")):
        return normalize_symbol(code_text)

    digits = re.sub(r"\D", "", code_text)
    market_hint = _pick(item, ("market", "exchange", "exch", "region", "market_type", "label", "type"))
    name_hint = _pick(item, ("name", "title"))
    hints = " ".join(
        str(value).upper()
        for value in (market_hint, name_hint)
        if value not in (None, "")
    )
    if len(digits) in {4, 5}:
        return f"{digits.zfill(5)}.HK"
    if len(digits) == 6:
        if digits.startswith("0") and _has_hk_market_hint(market_hint, name_hint, hints):
            return f"{digits[-5:]}.HK"
        if "SH" in hints or digits.startswith(("5", "6", "9")):
            return f"{digits}.SH"
        return f"{digits}.SZ"
    return None


def _normalize_search_row(item: dict) -> dict | None:
    symbol = _normalize_search_symbol(item)
    if not symbol:
        return None
    return {
        "symbol": symbol,
        "name": str(_pick(item, ("name", "title", "label", "stock_name")) or symbol),
        "market": market_from_symbol(symbol),
        "sector": str(_pick(item, ("industry", "industry_name", "sector", "sector_name")) or "Unknown"),
    }


def _daily_kline_row(symbol: str, as_of: date) -> dict | None:
    if ball is None or not _ensure_token():
        return None
    count = max(30, int(os.getenv("SNOWBALL_DAILY_LOOKBACK", "120")))
    for snow_symbol in _snowball_symbol_candidates(symbol):
        payload = _call_kline_with_retry(
            snow_symbol,
            period="day",
            count=count,
            context="snowball kline",
        )
        if payload is None:
            continue
        latest = _latest_kline_row_on_or_before(_extract_kline_rows(payload), as_of)
        if latest is None:
            continue
        best, row_date = latest
        open_val = _safe_float(best.get("open"))
        high_val = _safe_float(best.get("high"))
        low_val = _safe_float(best.get("low"))
        close_val = _safe_float(best.get("close"))
        volume_val = _safe_float(best.get("volume"))
        if None in (open_val, high_val, low_val, close_val, volume_val):
            continue
        return {
            "symbol": normalize_symbol(symbol),
            "date": row_date,
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
            "volume": volume_val,
            "preclose": _safe_float(best.get("prev_close") or best.get("preclose")),
        }
    return None


def _index_specs_by_symbol() -> dict[str, dict]:
    raw = os.getenv(
        "SNOWBALL_INDEX_MAP",
        ",".join(f"{item['symbol']}={item['snowball_symbol']}" for item in _DEFAULT_INDEX_SPECS),
    ).strip()
    specs: dict[str, dict] = {
        str(item["symbol"]): {
            "symbol": str(item["symbol"]),
            "snowball_symbol": str(item["snowball_symbol"]),
            "name": str(item["name"]),
            "market": str(item["market"]),
        }
        for item in _DEFAULT_INDEX_SPECS
    }
    for item in raw.split(","):
        if "=" not in item:
            continue
        local_symbol, snow_symbol = item.split("=", 1)
        canonical = normalize_index_symbol(local_symbol.strip())
        upper_snow_symbol = snow_symbol.strip().upper()
        if not canonical or not upper_snow_symbol:
            continue
        current = specs.get(canonical, {})
        specs[canonical] = {
            "symbol": canonical,
            "snowball_symbol": upper_snow_symbol,
            "name": str(current.get("name") or canonical),
            "market": str(current.get("market") or ("HK" if canonical.startswith("HK") else "A")),
        }
    return specs


def _index_map() -> dict[str, str]:
    return {
        symbol: str(spec["snowball_symbol"])
        for symbol, spec in _index_specs_by_symbol().items()
        if spec.get("snowball_symbol")
    }


def _select_finance_record(records: list[dict], period: str) -> dict:
    if not records:
        return {}
    target = _to_date(f"{period[:4]}-{period[4:6]}-28") if len(period) >= 6 else None
    if target is None:
        return records[0]
    selected: dict | None = None
    selected_date: date | None = None
    for row in records:
        report_date = _to_date(
            row.get("report_date")
            or row.get("report_date_str")
            or row.get("end_date")
            or row.get("publish_date")
            or row.get("ctime")
        )
        if report_date is None or report_date > target:
            continue
        if selected is None or (selected_date is not None and report_date > selected_date) or selected_date is None:
            selected = row
            selected_date = report_date
    return selected or records[0]


def _pick_numeric(row: dict, *keys: str) -> float | None:
    for key in keys:
        if key not in row:
            continue
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _extract_finance_period(row: dict, fallback_period: str) -> str:
    record_date = _to_date(
        row.get("report_date")
        or row.get("report_date_str")
        or row.get("end_date")
        or row.get("publish_date")
        or row.get("ctime")
    )
    if record_date is None:
        return fallback_period
    return f"{record_date.year:04d}{record_date.month:02d}"


def _financial_row_has_signal(row: dict | None) -> bool:
    if not isinstance(row, dict):
        return False
    for key in ("revenue", "net_income", "cash_flow", "roe", "debt_ratio"):
        value = _safe_float(row.get(key))
        if value is not None and abs(value) > 1e-12:
            return True
    return False


def _parse_kline_history_rows(
    symbol: str,
    rows: list[dict],
    *,
    as_of: date | None = None,
    preserve_time: bool = False,
) -> list[dict]:
    output: list[dict] = []
    normalized = normalize_index_symbol(symbol) if symbol in _index_specs_by_symbol() else normalize_symbol(symbol)
    for row in rows:
        row_time = _to_datetime(row.get("timestamp") or row.get("time") or row.get("date"))
        row_date = row_time.date() if row_time is not None else None
        if row_date is None:
            continue
        if as_of is not None and row_date > as_of:
            continue
        open_val = _safe_float(row.get("open"))
        high_val = _safe_float(row.get("high"))
        low_val = _safe_float(row.get("low"))
        close_val = _safe_float(row.get("close"))
        volume_val = _safe_float(row.get("volume"))
        if None in (open_val, high_val, low_val, close_val, volume_val):
            continue
        output.append(
            {
                "symbol": normalized,
                "date": row_time if preserve_time and row_time is not None else row_date,
                "open": open_val,
                "high": high_val,
                "low": low_val,
                "close": close_val,
                "volume": volume_val,
            }
        )
    output.sort(key=lambda item: (item["date"], item["symbol"]))
    return output


@contextmanager
def snowball_session():
    _ensure_token()
    yield


def get_stock_basic() -> List[dict]:
    return get_stock_basics()


def get_stock_basics(symbols: Iterable[str] | None = None) -> List[dict]:
    requested = [normalize_symbol(str(symbol)) for symbol in (symbols or _stock_universe()) if str(symbol).strip()]
    symbols = _limit_symbols(requested)
    if not symbols:
        return []
    quote_items = _call_quotec(symbols)
    by_symbol: dict[str, dict] = {}
    for item in quote_items:
        raw_symbol = item.get("symbol") or item.get("code") or item.get("ticker")
        if raw_symbol in (None, ""):
            continue
        by_symbol[normalize_symbol(str(raw_symbol))] = item

    rows: list[dict] = []
    for symbol in symbols:
        item = by_symbol.get(symbol, {})
        rows.append(
            {
                "symbol": symbol,
                "name": _extract_name(item, symbol),
                "market": market_from_symbol(symbol),
                "sector": _extract_sector(item),
            }
        )
    return ensure_required(rows, ["symbol", "name", "market", "sector"], "snowball.stock_basic")


def _quote_from_record(symbol: str, record: dict) -> dict:
    normalized = normalize_symbol(symbol)
    current = _safe_float(_pick(record, ("current", "price", "last_price", "close")))
    last_close = _safe_float(_pick(record, ("last_close", "prev_close", "preclose", "close_prev")))
    change = _safe_float(_pick(record, ("chg", "change")))
    if change is None and current is not None and last_close not in (None, 0):
        change = current - last_close
    percent = _safe_float(_pick(record, ("percent", "chg_percent", "change_percent", "pct")))
    if percent is None and change is not None and last_close not in (None, 0):
        percent = change / last_close * 100.0
    return {
        "symbol": normalized,
        "name": _extract_name(record, normalized),
        "sector": _extract_sector(record),
        "current": current,
        "change": change,
        "percent": percent,
        "open": _safe_float(_pick(record, ("open",))),
        "high": _safe_float(_pick(record, ("high",))),
        "low": _safe_float(_pick(record, ("low",))),
        "last_close": last_close,
        "volume": _safe_float(_pick(record, ("volume", "current_volume"))),
        "amount": _safe_float(_pick(record, ("amount", "turnover", "deal_amount"))),
        "turnover_rate": _safe_float(_pick(record, ("turnover_rate", "turn_rate", "turnoverratio"))),
        "amplitude": _safe_float(_pick(record, ("amplitude", "amp_rate"))),
        "timestamp": _to_datetime(
            _pick(record, ("timestamp", "time", "trade_timestamp", "update_time", "current_timestamp"))
        ),
    }


def _quote_detail_from_record(symbol: str, record: dict) -> dict:
    normalized = normalize_symbol(symbol)
    return {
        "symbol": normalized,
        "pe_ttm": _safe_float(_pick(record, ("pe_ttm", "pettm", "pe", "pe_lyr"))),
        "pb": _safe_float(_pick(record, ("pb",))),
        "ps_ttm": _safe_float(_pick(record, ("ps_ttm", "ps", "psr"))),
        "pcf": _safe_float(_pick(record, ("pcf", "pcf_ttm"))),
        "market_cap": _safe_float(
            _pick(record, ("market_capital", "market_cap", "total_market_cap", "market_value"))
        ),
        "float_market_cap": _safe_float(
            _pick(record, ("float_market_capital", "float_market_cap", "float_market_value"))
        ),
        "dividend_yield": _safe_float(_pick(record, ("dividend_yield", "dividend_yield_ttm"))),
        "volume_ratio": _safe_float(_pick(record, ("volume_ratio", "vol_ratio"))),
        "lot_size": _safe_float(_pick(record, ("lot_size", "lot", "volume_unit"))),
    }


def _order_book_levels(record: dict, *, side: str) -> list[dict]:
    direct_keys = ("bids", "bid", "buy", "buy_levels") if side == "bid" else ("asks", "ask", "sell", "sell_levels")
    for key in direct_keys:
        levels = record.get(key)
        if not isinstance(levels, list):
            continue
        rows: list[dict] = []
        for idx, item in enumerate(levels[:5], start=1):
            if not isinstance(item, dict):
                continue
            price = _safe_float(_pick(item, ("price", "p", "current")))
            volume = _safe_float(_pick(item, ("volume", "v", "count", "size", "amount")))
            if price is None and volume is None:
                continue
            rows.append({"level": idx, "price": price, "volume": volume})
        if rows:
            return rows

    rows: list[dict] = []
    for idx in range(1, 6):
        if side == "bid":
            price = _safe_float(_pick(record, (f"bp{idx}", f"bid{idx}", f"buy{idx}", f"bid{idx}_price")))
            volume = _safe_float(
                _pick(record, (f"bc{idx}", f"bid{idx}_volume", f"buy{idx}_volume", f"bv{idx}"))
            )
        else:
            price = _safe_float(_pick(record, (f"sp{idx}", f"ask{idx}", f"sell{idx}", f"ask{idx}_price")))
            volume = _safe_float(
                _pick(record, (f"sc{idx}", f"ask{idx}_volume", f"sell{idx}_volume", f"sv{idx}"))
            )
        if price is None and volume is None:
            continue
        rows.append({"level": idx, "price": price, "volume": volume})
    return rows


def get_stock_quote(symbol: str) -> dict:
    normalized = normalize_symbol(symbol)
    rows = _call_quotec([normalized])
    record = (
        _extract_primary_record(
            {"data": rows},
            symbol=normalized,
            preferred_keys=("current", "price", "volume", "high", "low"),
        )
        if rows
        else {}
    )
    if not record:
        recovered = _call_quotec_single(normalized)
        if recovered:
            record = recovered
    if record:
        return _quote_from_record(normalized, record)
    if normalized.endswith(".HK"):
        hk_quote = _get_ak_hk_spot_quote(normalized, allow_refresh=False)
        if hk_quote:
            return _quote_from_record(normalized, hk_quote)
    return {}


def get_stock_quote_detail(symbol: str) -> dict:
    normalized = normalize_symbol(symbol)
    for snow_symbol in _snowball_symbol_candidates(normalized):
        payload = _call_with_token_retry(
            lambda symbol_code=snow_symbol: ball.quote_detail(symbol_code),
            context="snowball quote_detail",
            ref=f"{normalized}:{snow_symbol}",
        )
        if payload is None:
            continue
        record = _extract_primary_record(
            payload,
            symbol=normalized,
            preferred_keys=("pe_ttm", "pb", "ps_ttm", "pcf", "market_capital", "turnover_rate"),
        )
        if record:
            return _quote_detail_from_record(normalized, record)
    return {}


def get_stock_pankou(symbol: str) -> dict:
    normalized = normalize_symbol(symbol)
    for snow_symbol in _snowball_symbol_candidates(normalized):
        payload = _call_with_token_retry(
            lambda symbol_code=snow_symbol: ball.pankou(symbol_code),
            context="snowball pankou",
            ref=f"{normalized}:{snow_symbol}",
        )
        if payload is None:
            continue
        record = _extract_primary_record(
            payload,
            symbol=normalized,
            preferred_keys=("diff", "ratio", "bp1", "sp1", "bids", "asks"),
        )
        if not record:
            continue
        return {
            "symbol": normalized,
            "diff": _safe_float(_pick(record, ("diff", "difference"))),
            "ratio": _safe_float(_pick(record, ("ratio", "diff_percent", "percent"))),
            "timestamp": _to_datetime(_pick(record, ("timestamp", "time", "update_time"))),
            "bids": _order_book_levels(record, side="bid"),
            "asks": _order_book_levels(record, side="ask"),
        }
    return {}


def search_stocks(keyword: str, market: str | None = None, limit: int = 50) -> List[dict]:
    if ball is None or not keyword.strip():
        return []
    payload = _call_with_token_retry(
        lambda: ball.suggest_stock(keyword.strip()),
        context="snowball suggest",
        ref=keyword.strip(),
    )
    if payload is None:
        return []

    normalized_market = market.upper() if market else None
    candidates: list[dict] = []
    seen: set[str] = set()
    for row in _extract_dict_rows(payload):
        normalized = _normalize_search_row(row)
        if not normalized:
            continue
        symbol = normalized["symbol"]
        if normalized_market and normalized["market"] != normalized_market:
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        candidates.append(normalized)
        if len(candidates) >= limit:
            break

    if not candidates:
        return []

    basics = get_stock_basics([item["symbol"] for item in candidates])
    by_symbol = {row["symbol"]: row for row in basics if row.get("symbol")}
    return [by_symbol.get(item["symbol"], item) for item in candidates[:limit]]


def get_market_stock_pool(market: str, *, limit: int = 100) -> List[dict]:
    normalized_market = market.upper()
    rows: list[dict] = []
    seen: set[str] = set()
    for keyword in _search_seed_queries(normalized_market):
        for item in search_stocks(keyword, market=normalized_market, limit=limit):
            symbol = item.get("symbol")
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            rows.append(item)
            if len(rows) >= limit:
                return rows
    return rows[:limit]


def get_index_daily(as_of: date) -> List[dict]:
    if ball is None or not _ensure_token():
        return []
    rows: list[dict] = []
    missing_symbols: list[str] = []
    for local_symbol, snow_symbol in _index_map().items():
        payload = _call_kline_with_retry(
            snow_symbol,
            period="day",
            count=max(30, int(os.getenv("SNOWBALL_DAILY_LOOKBACK", "120"))),
            context="snowball index kline",
        )
        if payload is None:
            missing_symbols.append(local_symbol)
            continue
        latest = _latest_kline_row_on_or_before(_extract_kline_rows(payload), as_of)
        if latest is None:
            missing_symbols.append(local_symbol)
            continue
        row, row_date = latest
        close_val = _safe_float(row.get("close"))
        if close_val is None:
            missing_symbols.append(local_symbol)
            continue
        preclose = _safe_float(row.get("prev_close") or row.get("preclose"))
        if preclose is None:
            preclose = _safe_float(row.get("open"))
        change = close_val - preclose if preclose is not None else 0.0
        rows.append({"symbol": local_symbol, "date": row_date, "close": close_val, "change": change})

    # Fallback: kline unavailable or no matched bar, use quotec snapshot to keep pipeline alive.
    if missing_symbols:
        quote_items = _call_quotec(missing_symbols)
        quote_map: dict[str, dict] = {}
        for item in quote_items:
            raw_symbol = item.get("symbol") or item.get("code") or item.get("ticker")
            if raw_symbol in (None, ""):
                continue
            quote_map[from_snowball_symbol(str(raw_symbol))] = item

        for symbol in missing_symbols:
            item = quote_map.get(symbol)
            if not item:
                continue
            close_val = _safe_float(
                item.get("current")
                or item.get("close")
                or item.get("price")
                or item.get("last_close")
            )
            if close_val is None:
                continue
            preclose = _safe_float(
                item.get("last_close")
                or item.get("prev_close")
                or item.get("preclose")
                or item.get("open")
            )
            raw_change = _safe_float(item.get("chg") or item.get("change"))
            change = raw_change if raw_change is not None else (close_val - preclose if preclose is not None else 0.0)
            rows.append({"symbol": symbol, "date": as_of, "close": close_val, "change": change})
    return ensure_required(rows, ["symbol", "date", "close", "change"], "snowball.index_daily")


def get_daily_prices(symbols, as_of: date, *, workers: int | None = None) -> List[dict]:
    unique_symbols: list[str] = []
    seen: set[str] = set()
    for symbol in symbols or []:
        normalized = normalize_symbol(str(symbol))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_symbols.append(normalized)
    if not unique_symbols:
        return []

    resolved_workers = max(1, int(workers if workers is not None else os.getenv("SNOWBALL_WORKERS", "8")))
    rows: list[dict] = []
    if resolved_workers <= 1:
        for symbol in unique_symbols:
            row = _daily_kline_row(symbol, as_of)
            if row:
                rows.append(row)
        return ensure_required(rows, ["symbol", "date", "open", "high", "low", "close", "volume"], "snowball.daily")

    LOGGER.info("snowball daily workers=%s total=%s date=%s", resolved_workers, len(unique_symbols), as_of)
    with ThreadPoolExecutor(max_workers=resolved_workers) as executor:
        future_map = {executor.submit(_daily_kline_row, symbol, as_of): symbol for symbol in unique_symbols}
        done = 0
        for future in as_completed(future_map):
            done += 1
            symbol = future_map[future]
            try:
                row = future.result()
                if row:
                    rows.append(row)
            except Exception as exc:
                LOGGER.warning("snowball daily failed [%s]: %s", symbol, exc)
            if done % 200 == 0 or done >= len(unique_symbols):
                LOGGER.info("snowball daily progress %s/%s for %s", done, len(unique_symbols), as_of)
    return ensure_required(rows, ["symbol", "date", "open", "high", "low", "close", "volume"], "snowball.daily")


def get_daily_history(symbol: str, *, count: int = 480, as_of: date | None = None) -> List[dict]:
    return get_kline_history(symbol, period="day", count=count, as_of=as_of, is_index=False)


def get_kline_history(
    symbol: str,
    *,
    period: str = "day",
    count: int = 284,
    as_of: date | None = None,
    is_index: bool = False,
) -> List[dict]:
    normalized = normalize_index_symbol(symbol) if is_index else normalize_symbol(symbol)
    if not is_index and normalized.endswith(".HK"):
        snow_rows = _fetch_snowball_kline_history(
            normalized,
            period=period,
            count=max(30, count),
            as_of=as_of,
            is_index=False,
        )
        # Prefer Snowball for HK; if it only returns one bar, fallback to AkShare for stability.
        if snow_rows and (period in {"1m", "30m", "60m"} or len(snow_rows) > 1):
            return snow_rows
        ak_rows = _fetch_ak_hk_kline_history(
            normalized,
            period=period,
            count=max(30, count),
            as_of=as_of,
        )
        if ak_rows:
            return ensure_required(
                ak_rows,
                ["symbol", "date", "open", "high", "low", "close", "volume"],
                "snowball.kline_history",
            )
        return snow_rows
    return _fetch_snowball_kline_history(
        normalized,
        period=period,
        count=max(30, count),
        as_of=as_of,
        is_index=is_index,
    )


def get_index_history(symbol: str, *, count: int = 480, as_of: date | None = None) -> List[dict]:
    return get_kline_history(symbol, period="day", count=count, as_of=as_of, is_index=True)


def get_monthly_prices(symbols, as_of: date) -> List[dict]:
    if ball is None or not _ensure_token():
        return []
    rows: list[dict] = []
    lookback = max(12, int(os.getenv("SNOWBALL_MONTHLY_LOOKBACK", "60")))
    for symbol in symbols or []:
        normalized = normalize_symbol(str(symbol))
        if not normalized:
            continue
        for snow_symbol in _snowball_symbol_candidates(normalized):
            payload = _call_kline_with_retry(
                snow_symbol,
                period="month",
                count=lookback,
                context="snowball monthly kline",
            )
            if payload is None:
                continue
            latest = None
            latest_date = None
            for row in _extract_kline_rows(payload):
                row_date = _to_date(row.get("timestamp") or row.get("time") or row.get("date"))
                if row_date is None or row_date > as_of:
                    continue
                if latest is None or (latest_date is not None and row_date > latest_date) or latest_date is None:
                    latest = row
                    latest_date = row_date
            if latest is None or latest_date is None:
                continue
            open_val = _safe_float(latest.get("open"))
            high_val = _safe_float(latest.get("high"))
            low_val = _safe_float(latest.get("low"))
            close_val = _safe_float(latest.get("close"))
            volume_val = _safe_float(latest.get("volume"))
            if None in (open_val, high_val, low_val, close_val, volume_val):
                continue
            rows.append(
                {
                    "symbol": normalized,
                    "date": latest_date,
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "close": close_val,
                    "volume": volume_val,
                }
            )
            break
    return ensure_required(rows, ["symbol", "date", "open", "high", "low", "close", "volume"], "snowball.monthly")


def get_financials(symbol: str, period: str) -> dict:
    if ball is None or not _ensure_token():
        return {}
    normalized_symbol = normalize_symbol(symbol)
    income_payload = None
    balance_payload = None
    cash_payload = None
    indicator_payload = None

    for snow_symbol in _snowball_symbol_candidates(normalized_symbol):
        candidate_income = _call_with_token_retry(
            lambda symbol_code=snow_symbol: ball.income(symbol_code, 0, 8),
            context="snowball income",
            ref=f"{normalized_symbol}:{snow_symbol}",
        )
        candidate_balance = _call_with_token_retry(
            lambda symbol_code=snow_symbol: ball.balance(symbol_code, 0, 8),
            context="snowball balance",
            ref=f"{normalized_symbol}:{snow_symbol}",
        )
        candidate_cash = _call_with_token_retry(
            lambda symbol_code=snow_symbol: ball.cash_flow(symbol_code, 0, 8),
            context="snowball cash_flow",
            ref=f"{normalized_symbol}:{snow_symbol}",
        )
        candidate_indicator = _call_with_token_retry(
            lambda symbol_code=snow_symbol: ball.indicator(symbol_code, 0, 8),
            context="snowball indicator",
            ref=f"{normalized_symbol}:{snow_symbol}",
        )
        if any(
            _extract_payload_items(payload)
            for payload in (candidate_income, candidate_balance, candidate_cash, candidate_indicator)
            if payload is not None
        ):
            income_payload = candidate_income
            balance_payload = candidate_balance
            cash_payload = candidate_cash
            indicator_payload = candidate_indicator
            break

    if all(payload is None for payload in (income_payload, balance_payload, cash_payload, indicator_payload)):
        return {}

    income_row = _select_finance_record(_extract_payload_items(income_payload), period)
    balance_row = _select_finance_record(_extract_payload_items(balance_payload), period)
    cash_row = _select_finance_record(_extract_payload_items(cash_payload), period)
    indicator_row = _select_finance_record(_extract_payload_items(indicator_payload), period)

    revenue = _pick_numeric(
        income_row,
        "total_revenue",
        "total_revenue_atsopc",
        "operating_revenue",
        "revenue",
    ) or 0.0
    net_income = _pick_numeric(
        income_row,
        "net_profit_atsopc",
        "net_profit",
        "n_income",
    ) or 0.0
    cash_flow = _pick_numeric(
        cash_row,
        "ncf_from_oa",
        "net_cash_flows_operate",
        "ncf_operate_a",
    ) or 0.0
    roe = _pick_numeric(
        indicator_row,
        "avg_roe",
        "roe_avg",
        "weighted_roe",
        "roe",
    ) or 0.0
    debt_ratio = _pick_numeric(
        balance_row,
        "asset_liab_ratio",
        "debt_to_asset",
        "liability_to_asset",
        "debt_asset_ratio",
    )
    if debt_ratio is None:
        total_liab = _pick_numeric(balance_row, "total_liab", "total_liabilities")
        total_assets = _pick_numeric(balance_row, "total_assets", "total_asset")
        if total_liab is not None and total_assets not in (None, 0):
            debt_ratio = total_liab / total_assets
    debt_ratio = debt_ratio or 0.0
    if debt_ratio > 1:
        debt_ratio = debt_ratio / 100.0

    rows = ensure_required(
        [
            {
                "symbol": normalize_symbol(symbol),
                "period": _extract_finance_period(
                    income_row or balance_row or cash_row or indicator_row,
                    period,
                ),
                "revenue": float(revenue),
                "net_income": float(net_income),
                "cash_flow": float(cash_flow),
                "roe": float(roe),
                "debt_ratio": float(debt_ratio),
            }
        ],
        ["symbol", "period", "revenue", "net_income", "cash_flow", "roe", "debt_ratio"],
        "snowball.financials",
    )
    if not rows:
        return {}
    return rows[0] if _financial_row_has_signal(rows[0]) else {}


def get_recent_financials(symbol: str, *, count: int = 8, as_of: date | None = None) -> List[dict]:
    target = as_of or date.today()
    month = ((target.month - 1) // 3 + 1) * 3
    quarter_end = date(target.year, month, 1)
    if month == 12:
        quarter_end = quarter_end.replace(day=31)
    else:
        quarter_end = date(quarter_end.year, quarter_end.month + 1, 1) - timedelta(days=1)
    if quarter_end > target:
        month -= 3
        if month <= 0:
            month += 12
            year = target.year - 1
        else:
            year = target.year
        quarter_end = date(year, month, 1)
        if month == 12:
            quarter_end = quarter_end.replace(day=31)
        else:
            quarter_end = date(quarter_end.year, quarter_end.month + 1, 1) - timedelta(days=1)

    periods: list[str] = []
    current = quarter_end
    for _ in range(max(1, count)):
        periods.append(f"{current.year:04d}{current.month:02d}")
        month = current.month - 3
        year = current.year
        if month <= 0:
            month += 12
            year -= 1
        current = date(year, month, 1)
        if month == 12:
            current = current.replace(day=31)
        else:
            current = date(current.year, current.month + 1, 1) - timedelta(days=1)

    deduped: dict[str, dict] = {}
    for period in periods:
        row = get_financials(symbol, period)
        actual_period = row.get("period") if row else None
        if row and actual_period:
            deduped[str(actual_period)] = row
    return sorted(deduped.values(), key=lambda item: item["period"], reverse=True)


def _extract_disclosure_items(payload, *, source: str, limit: int) -> List[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for record in _extract_dict_rows(payload):
        title = _pick(record, ("title", "name", "report_name", "notice_title", "forecast_title"))
        if title in (None, ""):
            continue
        published_at = _to_datetime(
            _pick(record, ("publish_date", "pub_date", "report_date", "date", "ctime", "timestamp", "update_time"))
        )
        link = str(_pick(record, ("url", "link", "pdf_url", "article_url")) or "")
        summary = str(_pick(record, ("summary", "abstract", "content", "forecast_content", "forecast_summary")) or "")
        institution = str(_pick(record, ("org_name", "institution_name", "broker_name", "author", "source")) or "")
        rating = str(_pick(record, ("rating", "investment_rating", "rate", "forecast_type", "forecast_category")) or "")
        dedupe_key = (str(title), published_at.isoformat() if published_at else "", link)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        rows.append(
            {
                "title": str(title),
                "published_at": published_at,
                "link": link,
                "summary": summary,
                "institution": institution,
                "rating": rating,
                "source": source,
            }
        )
    rows.sort(key=lambda item: item["published_at"] or datetime.min, reverse=True)
    return rows[:limit]


def get_stock_reports(symbol: str, *, limit: int = 10) -> List[dict]:
    normalized = normalize_symbol(symbol)
    market = market_from_symbol(normalized)
    if market == "A":
        ak_rows = _build_ak_a_margin_research_rows(normalized, limit=limit)
        if ak_rows:
            return ak_rows
    elif market == "HK":
        ak_rows = _build_ak_hk_profit_forecast_rows(normalized, limit=limit)
        if ak_rows:
            return ak_rows

    primary = to_snowball_symbol(normalized)
    payload = _call_with_token_retry(
        lambda: ball.report(primary),
        context="snowball report",
        ref=normalized,
    )
    if payload is not None:
        rows = _extract_disclosure_items(payload, source="雪球研报", limit=limit)
        if rows:
            return rows
    for snow_symbol in _snowball_symbol_candidates(normalized):
        if snow_symbol == primary:
            continue
        payload = _call_with_token_retry(
            lambda symbol_code=snow_symbol: ball.report(symbol_code),
            context="snowball report",
            ref=f"{normalized}:{snow_symbol}",
        )
        if payload is None:
            continue
        rows = _extract_disclosure_items(payload, source="雪球研报", limit=limit)
        if rows:
            return rows
    return []

def get_stock_earning_forecasts(symbol: str, *, limit: int = 10) -> List[dict]:
    normalized = normalize_symbol(symbol)
    if market_from_symbol(normalized) == "HK":
        ak_rows = _build_ak_hk_profit_forecast_rows(normalized, limit=limit)
        if ak_rows:
            return ak_rows

    primary = to_snowball_symbol(normalized)
    payload = _call_with_token_retry(
        lambda: ball.earningforecast(primary),
        context="snowball earningforecast",
        ref=normalized,
    )
    if payload is not None:
        rows = _extract_disclosure_items(payload, source="雪球业绩预告", limit=limit)
        if rows:
            return rows
    for snow_symbol in _snowball_symbol_candidates(normalized):
        if snow_symbol == primary:
            continue
        payload = _call_with_token_retry(
            lambda symbol_code=snow_symbol: ball.earningforecast(symbol_code),
            context="snowball earningforecast",
            ref=f"{normalized}:{snow_symbol}",
        )
        if payload is None:
            continue
        rows = _extract_disclosure_items(payload, source="雪球业绩预告", limit=limit)
        if rows:
            return rows
    return []
