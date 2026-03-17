from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import List
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)

BASE_URL = "https://api.worldbank.org/v2"
WORLD_BANK_TIMEOUT = max(3, int(os.getenv("WORLD_BANK_TIMEOUT", "12")))
WORLD_BANK_RETRIES = max(0, int(os.getenv("WORLD_BANK_RETRIES", "0")))


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y").date()
    except ValueError:
        return None


def _fetch_json(url: str, *, timeout: int = WORLD_BANK_TIMEOUT, retries: int = WORLD_BANK_RETRIES) -> list:
    for attempt in range(retries + 1):
        try:
            with urlopen(url, timeout=timeout) as resp:
                payload = resp.read().decode("utf-8")
            return json.loads(payload)
        except (HTTPError, URLError, TimeoutError) as exc:
            LOGGER.warning("WorldBank request failed: %s", exc)
            if attempt >= retries:
                return []
        except Exception as exc:
            LOGGER.warning("WorldBank request failed: %s", exc)
            return []
    return []


def get_indicator_series(country: str, indicator: str, start: date, end: date) -> List[dict]:
    """Fetch World Bank indicator series for given country and range."""
    rows: List[dict] = []
    params = {
        "format": "json",
        "per_page": "1000",
        "date": f"{start.year}:{end.year}",
    }
    page = 1
    pages = 1
    while page <= pages:
        params["page"] = str(page)
        query = urlencode(params)
        url = f"{BASE_URL}/country/{country}/indicator/{indicator}?{query}"
        data = _fetch_json(url)
        if not isinstance(data, list) or len(data) < 2:
            break
        meta = data[0] or {}
        try:
            pages = int(meta.get("pages") or 1)
        except Exception:
            pages = 1
        for record in data[1] or []:
            row_date = _to_date(record.get("date"))
            value = record.get("value")
            if row_date is None or value is None:
                continue
            rows.append({"country": country, "indicator": indicator, "date": row_date, "value": value})
        page += 1
    return ensure_required(rows, ["country", "indicator", "date", "value"], "worldbank.indicator")
