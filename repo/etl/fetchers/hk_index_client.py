from __future__ import annotations

from datetime import date, datetime
from typing import Iterable
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)

_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
}

_HK_INDEX_SERIES = {
    "HKHSI": {"series_code": "hsi", "index_name": "Hang Seng Index"},
    "HKHSCEI": {"series_code": "hscei", "index_name": "Hang Seng China Enterprises Index"},
    "HKHSTECH": {"series_code": "hstech", "index_name": "Hang Seng TECH Index"},
}

_HK_INDEX_ALIASES = {
    "HKHSI": "HKHSI",
    "HSI": "HKHSI",
    "HKHSCEI": "HKHSCEI",
    "HSCEI": "HKHSCEI",
    "HKHSTECH": "HKHSTECH",
    "HSTECH": "HKHSTECH",
}


def normalize_hk_index_symbol(symbol: str) -> str:
    upper = symbol.strip().upper()
    return _HK_INDEX_ALIASES.get(upper, upper)


def supported_hk_index_symbols() -> list[str]:
    return list(_HK_INDEX_SERIES.keys())


def _fetch_json(url: str) -> dict:
    request = Request(url, headers=_REQUEST_HEADERS)
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _payload_date(payload: dict) -> date:
    request_date = str(payload.get("requestDate") or "").strip()
    if request_date:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(request_date[:19], fmt).date()
            except ValueError:
                continue
    return date.today()


def _select_index_node(nodes: Iterable[dict], index_name: str) -> dict | None:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if str(node.get("indexName") or "").strip() == index_name:
            return node
        nested = _select_index_node(node.get("subIndexList") or [], index_name)
        if nested is not None:
            return nested
    return None


def _row_symbol(record: dict) -> str | None:
    for key in ("hCode", "oCode", "rCode", "tCode", "aCode", "bCode", "code"):
        raw = str(record.get(key) or "").strip()
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits:
            return f"{digits.zfill(5)}.HK"
    return None


def get_hk_index_constituents(symbol: str) -> list[dict]:
    canonical = normalize_hk_index_symbol(symbol)
    spec = _HK_INDEX_SERIES.get(canonical)
    if spec is None:
        return []

    url = f"https://www.hsi.com.hk/data/eng/rt/index-series/{spec['series_code']}/constituents.do"
    try:
        payload = _fetch_json(url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        LOGGER.warning("hang seng constituents fetch failed [%s]: %s", canonical, exc)
        return []

    if payload.get("exceptions"):
        LOGGER.warning("hang seng constituents returned exceptions [%s]: %s", canonical, payload["exceptions"])
        return []

    series_list = payload.get("indexSeriesList")
    if not isinstance(series_list, list) or not series_list:
        return []

    series = series_list[0]
    index_node = _select_index_node(series.get("indexList") or [], spec["index_name"])
    if index_node is None:
        LOGGER.warning("hang seng constituents missing target index [%s]", canonical)
        return []

    as_of = _payload_date(payload)
    rows: list[dict] = []
    constituents = index_node.get("constituentContent") or []
    if not isinstance(constituents, list):
        return []
    for rank, record in enumerate(constituents, start=1):
        if not isinstance(record, dict):
            continue
        if str(record.get("isDummy") or "").strip().upper() == "Y":
            continue
        stock_symbol = _row_symbol(record)
        if not stock_symbol:
            continue
        contribution_raw = record.get("contributionChange")
        contribution = None
        try:
            if contribution_raw not in (None, ""):
                contribution = float(contribution_raw)
        except (TypeError, ValueError):
            contribution = None
        rows.append(
            {
                "index_symbol": canonical,
                "symbol": stock_symbol,
                "date": as_of,
                "weight": None,
                "name": str(record.get("constituentName") or stock_symbol),
                "market": "HK",
                "rank": rank,
                "contribution_change": contribution,
                "source": "Hang Seng Indexes",
            }
        )
    return rows
