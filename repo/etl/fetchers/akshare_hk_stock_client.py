from __future__ import annotations

from contextlib import contextmanager
import math
import os
import random
import time
from typing import Iterable

from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover - import guard
    ak = None
    LOGGER.warning("akshare import failed for hk stock universe: %s", exc)

try:
    import pandas as pd  # type: ignore
except Exception as exc:  # pragma: no cover - import guard
    pd = None
    LOGGER.warning("pandas import failed for hk stock universe: %s", exc)

try:
    import requests  # type: ignore
except Exception as exc:  # pragma: no cover - import guard
    requests = None
    LOGGER.warning("requests import failed for hk stock universe: %s", exc)

HK_AKSHARE_FUNCTIONS = (
    "stock_hk_spot_em",
    "stock_hk_spot",
    "stock_hk_main_board_spot_em",
)

CODE_COLUMN_CANDIDATES = ("代码", "code", "symbol", "证券代码", "股票代码", "代号", "编号")
NAME_COLUMN_CANDIDATES = ("名称", "name", "股票名称", "证券简称", "简称", "名称缩写")
SECTOR_COLUMN_CANDIDATES = ("行业", "industry", "所属行业", "行业板块", "板块", "sector")
PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
AKSHARE_HK_DISABLE_PROXY = os.getenv("AKSHARE_HK_DISABLE_PROXY", "1").strip().lower() not in {"0", "false", "no"}
AKSHARE_HK_PAGE_SIZE = max(100, int(os.getenv("AKSHARE_HK_PAGE_SIZE", "500")))
AKSHARE_HK_REQUEST_TIMEOUT_SECONDS = max(5, int(os.getenv("AKSHARE_HK_REQUEST_TIMEOUT_SECONDS", "20")))
AKSHARE_HK_PAGE_MAX_RETRIES = max(1, int(os.getenv("AKSHARE_HK_PAGE_MAX_RETRIES", "6")))
AKSHARE_HK_PAGE_DELAY_SECONDS = max(0.0, float(os.getenv("AKSHARE_HK_PAGE_DELAY_SECONDS", "0.35")))
AKSHARE_HK_PAGE_LOG_INTERVAL = max(1, int(os.getenv("AKSHARE_HK_PAGE_LOG_INTERVAL", "5")))
EASTMONEY_HK_FIELDS = (
    "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,"
    "f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152"
)
EASTMONEY_HK_ENDPOINTS = {
    "stock_hk_spot_em": {
        "url": "https://72.push2.eastmoney.com/api/qt/clist/get",
        "fs": "m:128 t:3,m:128 t:4,m:128 t:1,m:128 t:2",
    },
    "stock_hk_main_board_spot_em": {
        "url": "https://81.push2.eastmoney.com/api/qt/clist/get",
        "fs": "m:128 t:3",
    },
}
EASTMONEY_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Connection": "close",
    "Referer": "https://quote.eastmoney.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    ),
}


def _pick_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    column_map = {str(item).strip().lower(): str(item) for item in columns}
    for candidate in candidates:
        value = column_map.get(str(candidate).strip().lower())
        if value:
            return value
    return None


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_hk_symbol(value: object) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    digits = "".join(char for char in text if char.isdigit())
    if not digits:
        return ""
    return f"{digits.zfill(5)}.HK"


def _row_score(row: dict) -> int:
    score = 0
    symbol = str(row.get("symbol") or "")
    name = str(row.get("name") or "")
    sector = str(row.get("sector") or "")
    if name and name != symbol:
        score += 2
    if sector and sector != "Unknown":
        score += 1
    return score


@contextmanager
def _proxy_bypass_context():
    if not AKSHARE_HK_DISABLE_PROXY:
        yield
        return

    backup = {key: os.environ.get(key) for key in PROXY_ENV_KEYS}
    no_proxy_backup = os.environ.get("NO_PROXY")
    no_proxy_lower_backup = os.environ.get("no_proxy")
    try:
        for key in PROXY_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"
        yield
    finally:
        for key, value in backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if no_proxy_backup is None:
            os.environ.pop("NO_PROXY", None)
        else:
            os.environ["NO_PROXY"] = no_proxy_backup
        if no_proxy_lower_backup is None:
            os.environ.pop("no_proxy", None)
        else:
            os.environ["no_proxy"] = no_proxy_lower_backup


def _request_eastmoney_page_json(function_name: str, url: str, params: dict) -> dict:
    if requests is None:
        raise RuntimeError("requests is unavailable")

    last_exception: Exception | None = None
    for attempt in range(1, AKSHARE_HK_PAGE_MAX_RETRIES + 1):
        try:
            with _proxy_bypass_context():
                response = requests.get(
                    url,
                    params=params,
                    headers=EASTMONEY_HEADERS,
                    timeout=AKSHARE_HK_REQUEST_TIMEOUT_SECONDS,
                )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") or {}
            if not isinstance(data.get("diff"), list):
                raise ValueError(f"eastmoney hk page payload missing diff: {payload}")
            return payload
        except Exception as exc:
            last_exception = exc
            if attempt >= AKSHARE_HK_PAGE_MAX_RETRIES:
                break
            delay_seconds = min(12.0, (1.6 ** (attempt - 1)) + random.uniform(0.4, 1.0))
            LOGGER.warning(
                "akshare hk universe page retry [%s] page=%s attempt=%s/%s delay=%.2fs: %s",
                function_name,
                params.get("pn"),
                attempt,
                AKSHARE_HK_PAGE_MAX_RETRIES,
                delay_seconds,
                exc,
            )
            time.sleep(delay_seconds)
    raise last_exception or RuntimeError(f"eastmoney hk page fetch failed [{function_name}]")


def _fetch_eastmoney_paginated_frame(function_name: str):
    if pd is None:
        return None
    config = EASTMONEY_HK_ENDPOINTS.get(function_name)
    if config is None:
        return None

    params = {
        "pn": "1",
        "pz": str(AKSHARE_HK_PAGE_SIZE),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": str(config["fs"]),
        "fields": EASTMONEY_HK_FIELDS,
    }
    payload = _request_eastmoney_page_json(function_name, str(config["url"]), params)
    data = payload.get("data") or {}
    first_page_rows = data.get("diff") or []
    total = max(len(first_page_rows), int(data.get("total") or 0))
    per_page = max(1, len(first_page_rows) or AKSHARE_HK_PAGE_SIZE)
    total_pages = max(1, math.ceil(total / per_page))
    records = [{"代码": item.get("f12"), "名称": item.get("f14")} for item in first_page_rows if isinstance(item, dict)]

    LOGGER.info(
        "akshare hk universe paging [%s] total_pages=%s page_size=%s total=%s",
        function_name,
        total_pages,
        per_page,
        total,
    )
    for page in range(2, total_pages + 1):
        if AKSHARE_HK_PAGE_DELAY_SECONDS > 0:
            time.sleep(AKSHARE_HK_PAGE_DELAY_SECONDS + random.uniform(0.0, 0.35))
        params["pn"] = str(page)
        page_payload = _request_eastmoney_page_json(function_name, str(config["url"]), params)
        page_rows = (page_payload.get("data") or {}).get("diff") or []
        records.extend({"代码": item.get("f12"), "名称": item.get("f14")} for item in page_rows if isinstance(item, dict))
        if page == total_pages or page % AKSHARE_HK_PAGE_LOG_INTERVAL == 0:
            LOGGER.info("akshare hk universe paging progress [%s] %s/%s", function_name, page, total_pages)

    return pd.DataFrame.from_records(records, columns=["代码", "名称"])


def _normalize_frame(df) -> list[dict]:
    if pd is None or df is None or getattr(df, "empty", True):
        return []
    code_col = _pick_column(df.columns, CODE_COLUMN_CANDIDATES)
    name_col = _pick_column(df.columns, NAME_COLUMN_CANDIDATES)
    sector_col = _pick_column(df.columns, SECTOR_COLUMN_CANDIDATES)
    if code_col is None:
        LOGGER.warning("akshare hk stock frame missing code column: columns=%s", list(df.columns))
        return []

    rows: list[dict] = []
    normalized_df = df.where(pd.notna(df), None)
    for record in normalized_df.to_dict(orient="records"):
        symbol = _normalize_hk_symbol(record.get(code_col))
        if not symbol:
            continue
        name = _normalize_text(record.get(name_col)) if name_col else ""
        sector = _normalize_text(record.get(sector_col)) if sector_col else ""
        rows.append(
            {
                "symbol": symbol,
                "name": name or symbol,
                "market": "HK",
                "sector": sector or "Unknown",
            }
        )

    by_symbol: dict[str, dict] = {}
    for row in rows:
        current = by_symbol.get(row["symbol"])
        if current is None or _row_score(row) >= _row_score(current):
            by_symbol[row["symbol"]] = row
    return sorted(by_symbol.values(), key=lambda item: item["symbol"])


def _call_provider_function(function_name: str):
    if function_name in EASTMONEY_HK_ENDPOINTS:
        try:
            df = _fetch_eastmoney_paginated_frame(function_name)
            if df is not None and not getattr(df, "empty", True):
                return df
        except Exception as exc:
            LOGGER.warning("custom akshare hk universe fetch failed [%s]: %s", function_name, exc)

    if ak is None:
        return None
    func = getattr(ak, function_name, None)
    if func is None:
        return None
    try:
        with _proxy_bypass_context():
            return func()
    except Exception as exc:
        LOGGER.warning("akshare hk universe fetch failed [%s]: %s", function_name, exc)
        return None


def fetch_hk_stock_universe_rows() -> list[dict]:
    merged: dict[str, dict] = {}
    for function_name in HK_AKSHARE_FUNCTIONS:
        df = _call_provider_function(function_name)
        rows = _normalize_frame(df)
        if not rows:
            continue
        for row in rows:
            current = merged.get(row["symbol"])
            if current is None or _row_score(row) >= _row_score(current):
                merged[row["symbol"]] = row
    output = sorted(merged.values(), key=lambda item: item["symbol"])
    if output:
        LOGGER.info("akshare hk universe loaded rows=%s", len(output))
    else:
        LOGGER.warning("akshare hk universe returned 0 rows")
    return output
