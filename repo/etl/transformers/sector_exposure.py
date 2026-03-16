from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from etl.utils.sector_taxonomy import UNKNOWN_SECTOR, normalize_sector_name


def build_sector_exposure(
    rows: Iterable[dict],
    *,
    basis: str = "market_value",
) -> dict:
    bucket: dict[str, dict[str, float]] = defaultdict(lambda: {"value": 0.0, "symbol_count": 0.0})
    total_symbols = 0
    covered_symbols = 0
    classified_symbols = 0
    unknown_symbols = 0
    total_value = 0.0

    for row in rows:
        sector = normalize_sector_name(row.get("sector"), market=row.get("market"))
        total_symbols += 1
        if sector == UNKNOWN_SECTOR:
            unknown_symbols += 1
        else:
            classified_symbols += 1

        value = row.get("value")
        try:
            numeric_value = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            numeric_value = 0.0
        if numeric_value <= 0:
            continue

        covered_symbols += 1
        bucket[sector]["value"] += numeric_value
        bucket[sector]["symbol_count"] += 1.0
        total_value += numeric_value

    items: list[dict] = []
    for sector, payload in bucket.items():
        value = float(payload["value"])
        items.append(
            {
                "sector": sector,
                "value": value,
                "weight": (value / total_value) if total_value else 0.0,
                "symbol_count": int(payload["symbol_count"]),
            }
        )
    items.sort(key=lambda item: item["value"], reverse=True)

    unknown_value = next((item["value"] for item in items if item["sector"] == UNKNOWN_SECTOR), 0.0)
    return {
        "basis": basis,
        "total_value": total_value,
        "total_symbol_count": total_symbols,
        "covered_symbol_count": covered_symbols,
        "classified_symbol_count": classified_symbols,
        "unknown_symbol_count": unknown_symbols,
        "unknown_value": unknown_value,
        "coverage": (covered_symbols / total_symbols) if total_symbols else 0.0,
        "items": items,
    }
