from __future__ import annotations

from datetime import date

from app.core.cache import get_json, set_json
from app.services.cache_utils import build_cache_key
from etl.fetchers.hk_index_client import get_hk_index_constituents, supported_hk_index_symbols
from etl.fetchers.snowball_client import (
    get_index_daily,
    get_stock_basics,
    normalize_index_symbol,
    supported_index_specs,
)

LIVE_INDEX_CACHE_TTL = 300
LIVE_INDEX_CACHE_VERSION = "v2"


def list_live_indices(*, as_of: date | None = None, sort: str = "desc") -> list[dict]:
    cache_key = build_cache_key("live:index:list", version=LIVE_INDEX_CACHE_VERSION, as_of=as_of, sort=sort)
    cached = get_json(cache_key)
    if isinstance(cached, list):
        return cached

    rows = {
        str(item.get("symbol")): item
        for item in get_index_daily(as_of or date.today())
        if isinstance(item, dict) and item.get("symbol")
    }
    items: list[dict] = []
    for spec in supported_index_specs():
        symbol = str(spec["symbol"])
        row = rows.get(symbol)
        if not row:
            continue
        items.append(
            {
                "symbol": symbol,
                "name": str(spec.get("name") or symbol),
                "market": str(spec.get("market") or ""),
                "date": row.get("date"),
                "close": row.get("close"),
                "change": row.get("change"),
            }
        )
    items.sort(key=lambda item: str(item.get("symbol") or ""), reverse=sort == "desc")
    set_json(cache_key, items, ttl=LIVE_INDEX_CACHE_TTL)
    return items


def list_live_index_constituents(
    symbol: str,
    *,
    as_of: date | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[dict], int]:
    canonical = normalize_index_symbol(symbol)
    cache_key = build_cache_key(
        "live:index:constituents",
        version=LIVE_INDEX_CACHE_VERSION,
        symbol=canonical,
        as_of=as_of,
        limit=limit,
        offset=offset,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        return cached["items"], cached["total"]

    rows: list[dict] = []
    if canonical in supported_hk_index_symbols():
        rows = get_hk_index_constituents(canonical)
        basics = get_stock_basics([row["symbol"] for row in rows if row.get("symbol")])
        by_symbol = {str(item.get("symbol")): item for item in basics if isinstance(item, dict) and item.get("symbol")}
        for row in rows:
            basic = by_symbol.get(str(row.get("symbol")), {})
            if basic.get("name") and basic.get("name") != basic.get("symbol"):
                row["name"] = basic["name"]
            if basic.get("market"):
                row["market"] = basic["market"]

    total = len(rows)
    items = rows[offset : offset + limit]
    set_json(cache_key, {"items": items, "total": total}, ttl=LIVE_INDEX_CACHE_TTL)
    return items, total
