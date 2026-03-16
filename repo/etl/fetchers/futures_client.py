from __future__ import annotations

from datetime import date, datetime
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)

SHFE_BASE_URL = os.getenv("SHFE_BASE_URL", "https://www.shfe.com.cn").rstrip("/")
SHFE_TIMEOUT_SECONDS = int(os.getenv("SHFE_TIMEOUT_SECONDS", "20"))
SHFE_REPORT_REFERER = f"{SHFE_BASE_URL}/reports/tradedata/dailyandweeklydata/"
SHFE_USER_AGENT = os.getenv(
    "SHFE_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)

TARGET_PRODUCTS: dict[str, dict[str, str]] = {
    "cu_f": {"symbol": "CU", "name": "铜"},
    "au_f": {"symbol": "AU", "name": "黄金"},
    "ag_f": {"symbol": "AG", "name": "白银"},
    "ao_f": {"symbol": "AO", "name": "氧化铝"},
    "sc_f": {"symbol": "SC", "name": "原油"},
    "fu_f": {"symbol": "FU", "name": "燃料油"},
}


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


def _parse_report_date(value: object, fallback: date) -> date:
    text = str(value or "").strip()
    if len(text) >= 8 and text[:8].isdigit():
        try:
            return datetime.strptime(text[:8], "%Y%m%d").date()
        except Exception:
            return fallback
    return fallback


def _delivery_rank(value: object) -> int:
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    return 99_999_999


def _extract_contract_month(row: dict) -> str:
    delivery_month = str(row.get("DELIVERYMONTH") or "").strip()
    if len(delivery_month) == 4 and delivery_month.isdigit():
        return delivery_month
    instrument_id = str(row.get("INSTRUMENTID") or "").strip().lower()
    matched = re.search(r"(\d{4})$", instrument_id)
    if matched:
        return matched.group(1)
    return ""


def _is_contract_row(row: dict) -> bool:
    product_id = str(row.get("PRODUCTID") or "").strip().lower()
    contract_month = _extract_contract_month(row)
    if product_id not in TARGET_PRODUCTS:
        return False
    if not contract_month:
        return False
    if product_id.endswith("_tas"):
        return False
    return True


def _select_main_contract(rows: list[dict]) -> dict | None:
    candidates = [row for row in rows if _is_contract_row(row)]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            _safe_float(row.get("VOLUME")) or -1.0,
            _safe_float(row.get("OPENINTEREST")) or -1.0,
            -_delivery_rank(_extract_contract_month(row)),
        ),
    )


def _normalize_row(product_id: str, row: dict, row_date: date) -> dict | None:
    target = TARGET_PRODUCTS[product_id]
    close = _safe_float(row.get("CLOSEPRICE"))
    settlement = _safe_float(row.get("SETTLEMENTPRICE"))
    close_value = close if close is not None else settlement
    if close_value is None:
        return None

    open_price = _safe_float(row.get("OPENPRICE"))
    high = _safe_float(row.get("HIGHESTPRICE"))
    low = _safe_float(row.get("LOWESTPRICE"))
    volume = _safe_float(row.get("VOLUME"))
    settlement_price = _safe_float(row.get("SETTLEMENTPRICE"))
    open_interest = _safe_float(row.get("OPENINTEREST"))
    turnover = _safe_float(row.get("TURNOVER"))

    return {
        "symbol": target["symbol"],
        "name": target["name"],
        "date": row_date,
        "contract_month": _extract_contract_month(row) or None,
        "open": open_price if open_price is not None else close_value,
        "high": high if high is not None else close_value,
        "low": low if low is not None else close_value,
        "close": close_value,
        "settlement": settlement_price if settlement_price is not None else close_value,
        "open_interest": open_interest,
        "turnover": turnover,
        "volume": volume,
        "source": "SHFE",
    }


def _daily_url(as_of: date) -> str:
    stamp = int(datetime.now().timestamp() * 1000)
    return f"{SHFE_BASE_URL}/data/tradedata/future/dailydata/kx{as_of:%Y%m%d}.dat?params={stamp}"


def _weekly_url(as_of: date) -> str:
    stamp = int(datetime.now().timestamp() * 1000)
    return f"{SHFE_BASE_URL}/data/tradedata/future/weeklydata/{as_of:%Y%m%d}.dat?params={stamp}"


def _fetch_payload(url: str, context: str) -> dict | None:
    request = Request(
        url,
        headers={
            "User-Agent": SHFE_USER_AGENT,
            "Referer": SHFE_REPORT_REFERER,
            "Accept": "application/json,text/plain,*/*",
        },
    )
    try:
        with urlopen(request, timeout=SHFE_TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        if exc.code == 404:
            LOGGER.info("%s missing [%s]", context, url)
            return None
        LOGGER.warning("%s http error [%s]: %s", context, url, exc)
        return None
    except URLError as exc:
        LOGGER.warning("%s url error [%s]: %s", context, url, exc)
        return None
    except Exception as exc:  # pragma: no cover - runtime/network dependent
        LOGGER.warning("%s fetch failed [%s]: %s", context, url, exc)
        return None

    try:
        data = json.loads(payload)
    except Exception as exc:
        LOGGER.warning("%s json decode failed [%s]: %s", context, url, exc)
        return None
    if not isinstance(data, dict):
        return None
    return data


def _fetch_daily_payload(as_of: date) -> dict | None:
    return _fetch_payload(_daily_url(as_of), f"shfe futures daily [{as_of}]")


def _fetch_weekly_payload(as_of: date) -> dict | None:
    return _fetch_payload(_weekly_url(as_of), f"shfe futures weekly [{as_of}]")


def get_futures_daily(as_of: date) -> list[dict]:
    payload = _fetch_daily_payload(as_of)
    if not payload:
        return []

    instruments = payload.get("o_curinstrument")
    if not isinstance(instruments, list) or not instruments:
        LOGGER.info("shfe futures daily empty for %s", as_of)
        return []

    row_date = _parse_report_date(payload.get("report_date") or payload.get("update_date"), as_of)
    grouped: dict[str, list[dict]] = {product_id: [] for product_id in TARGET_PRODUCTS}
    for row in instruments:
        if not isinstance(row, dict):
            continue
        product_id = str(row.get("PRODUCTID") or "").strip().lower()
        if product_id in grouped:
            grouped[product_id].append(row)

    rows: list[dict] = []
    for product_id in TARGET_PRODUCTS:
        main_row = _select_main_contract(grouped[product_id])
        if main_row is None:
            continue
        normalized = _normalize_row(product_id, main_row, row_date)
        if normalized is not None:
            rows.append(normalized)

    return ensure_required(rows, ["symbol", "date"], "futures.daily")


def get_futures_weekly(as_of: date) -> list[dict]:
    payload = _fetch_weekly_payload(as_of)
    if not payload:
        return []

    instruments = payload.get("o_cursor")
    if not isinstance(instruments, list) or not instruments:
        LOGGER.info("shfe futures weekly empty for %s", as_of)
        return []

    row_date = _parse_report_date(payload.get("report_date") or payload.get("update_date"), as_of)
    grouped: dict[str, list[dict]] = {product_id: [] for product_id in TARGET_PRODUCTS}
    for row in instruments:
        if not isinstance(row, dict):
            continue
        product_id = str(row.get("PRODUCTID") or "").strip().lower()
        if product_id in grouped:
            grouped[product_id].append(row)

    rows: list[dict] = []
    for product_id in TARGET_PRODUCTS:
        main_row = _select_main_contract(grouped[product_id])
        if main_row is None:
            continue
        normalized = _normalize_row(product_id, main_row, row_date)
        if normalized is not None:
            rows.append(normalized)

    return ensure_required(rows, ["symbol", "date"], "futures.weekly")
