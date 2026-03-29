from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.services.cache_utils import build_cache_key
from app.services.index_constituent_service import list_index_constituents
from etl.fetchers.snowball_client import get_stock_quotes, index_market, index_name, normalize_index_symbol
from etl.utils.sector_taxonomy import UNKNOWN_SECTOR, normalize_sector_name

INDEX_INSIGHT_CACHE_TTL = 300
INDEX_INSIGHT_CACHE_VERSION = "v1"
INDEX_INSIGHT_MAX_CONSTITUENTS = 1000


def _coerce_float(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _constituent_sort_key(item: dict, field: str, reverse: bool) -> tuple:
    value = item.get(field)
    if value is None:
        fallback = float("-inf") if reverse else float("inf")
        return (1, fallback)
    return (0, float(value))


def _build_constituent_snapshot(db: Session, symbol: str, as_of: date | None = None) -> list[dict]:
    items, _ = list_index_constituents(
        db,
        symbol,
        as_of=as_of,
        limit=INDEX_INSIGHT_MAX_CONSTITUENTS,
        offset=0,
    )
    if not items:
        return []

    quotes = get_stock_quotes([str(item.get("symbol") or "") for item in items if item.get("symbol")])
    by_symbol = {str(item.get("symbol")): item for item in quotes if isinstance(item, dict) and item.get("symbol")}

    output: list[dict] = []
    for raw in items:
        row = dict(raw)
        quote = by_symbol.get(str(row.get("symbol")), {})
        row["name"] = str(row.get("name") or quote.get("name") or row.get("symbol") or "")
        row["market"] = str(row.get("market") or quote.get("market") or "")
        sector = normalize_sector_name(row.get("sector") or quote.get("sector"), market=row.get("market"))
        row["sector"] = sector if sector != UNKNOWN_SECTOR else None
        row["current"] = _coerce_float(quote.get("current"))
        row["change"] = _coerce_float(quote.get("change"))
        row["percent"] = _coerce_float(quote.get("percent"))
        weight = _coerce_float(row.get("weight"))
        contribution_change = _coerce_float(row.get("contribution_change"))
        if contribution_change is not None:
            row["contribution_score"] = contribution_change
        elif weight is not None and row["percent"] is not None:
            row["contribution_score"] = weight * row["percent"]
        else:
            row["contribution_score"] = None
        output.append(row)
    return output


def get_index_insight(db: Session, symbol: str, as_of: date | None = None) -> dict:
    canonical = normalize_index_symbol(symbol)
    cache_key = build_cache_key("index:insight", version=INDEX_INSIGHT_CACHE_VERSION, symbol=canonical, as_of=as_of)
    cached = get_json(cache_key)
    if isinstance(cached, dict) and cached.get("summary"):
        return cached

    constituents = _build_constituent_snapshot(db, canonical, as_of=as_of)
    as_of_value = None
    if constituents:
        dates = [item.get("date") for item in constituents if item.get("date") is not None]
        as_of_value = max(dates) if dates else as_of

    weights = sorted((_coerce_float(item.get("weight")) or 0.0 for item in constituents), reverse=True)
    priced_total = 0
    rising_count = 0
    falling_count = 0
    flat_count = 0
    sector_buckets: dict[str, dict] = defaultdict(
        lambda: {
            "weight": 0.0,
            "symbol_count": 0,
            "percent_sum": 0.0,
            "percent_weight": 0.0,
            "leader": None,
        }
    )

    for item in constituents:
        change = _coerce_float(item.get("change"))
        percent = _coerce_float(item.get("percent"))
        weight = _coerce_float(item.get("weight")) or 0.0
        if percent is not None or change is not None:
            priced_total += 1
        direction = percent if percent is not None else change
        if direction is not None:
            if direction > 0:
                rising_count += 1
            elif direction < 0:
                falling_count += 1
            else:
                flat_count += 1

        sector_name = str(item.get("sector") or "未分类")
        bucket = sector_buckets[sector_name]
        bucket["weight"] += weight
        bucket["symbol_count"] += 1
        if percent is not None:
            bucket["percent_sum"] += percent * (weight if weight > 0 else 1.0)
            bucket["percent_weight"] += weight if weight > 0 else 1.0
        leader = bucket["leader"]
        candidate_score = abs(_coerce_float(item.get("contribution_score")) or 0.0)
        leader_score = abs(_coerce_float(leader.get("contribution_score")) or 0.0) if isinstance(leader, dict) else -1.0
        if leader is None or candidate_score > leader_score:
            bucket["leader"] = item

    sector_breakdown = []
    for sector_name, bucket in sector_buckets.items():
        leader = bucket["leader"] or {}
        percent_weight = bucket["percent_weight"] or 0.0
        avg_percent = bucket["percent_sum"] / percent_weight if percent_weight > 0 else None
        sector_breakdown.append(
            {
                "sector": sector_name,
                "weight": bucket["weight"],
                "symbol_count": bucket["symbol_count"],
                "avg_percent": avg_percent,
                "leader_symbol": leader.get("symbol"),
                "leader_name": leader.get("name"),
            }
        )
    sector_breakdown.sort(key=lambda item: (float(item.get("weight") or 0.0), int(item.get("symbol_count") or 0)), reverse=True)

    top_weights = sorted(
        constituents,
        key=lambda item: _constituent_sort_key(item, "weight", True),
        reverse=True,
    )[:10]
    top_contributors = sorted(
        [item for item in constituents if item.get("contribution_score") is not None],
        key=lambda item: _constituent_sort_key(item, "contribution_score", True),
        reverse=True,
    )[:10]
    top_detractors = sorted(
        [item for item in constituents if item.get("contribution_score") is not None],
        key=lambda item: _constituent_sort_key(item, "contribution_score", False),
    )[:10]

    payload = {
        "summary": {
            "symbol": canonical,
            "name": index_name(canonical),
            "market": index_market(canonical),
            "as_of": as_of_value,
            "constituent_total": len(constituents),
            "priced_total": priced_total,
            "weight_coverage": sum(weights),
            "top5_weight": sum(weights[:5]),
            "top10_weight": sum(weights[:10]),
            "rising_count": rising_count,
            "falling_count": falling_count,
            "flat_count": flat_count,
        },
        "top_weights": top_weights,
        "top_contributors": top_contributors,
        "top_detractors": top_detractors,
        "sector_breakdown": sector_breakdown[:12],
        "constituents": constituents,
    }
    if constituents:
        set_json(cache_key, payload, ttl=INDEX_INSIGHT_CACHE_TTL)
    return payload

