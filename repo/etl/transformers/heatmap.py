from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List


def build_heatmap(rows: Iterable[dict]) -> List[dict]:
    """Aggregate close/change by sector + market into heatmap rows."""
    bucket: Dict[tuple[str, str | None], dict] = defaultdict(
        lambda: {"closes": [], "changes": [], "close_sum": 0.0, "change_sum": 0.0, "count": 0}
    )
    for row in rows:
        sector = row.get("sector") or "未知"
        market = row.get("market")
        close = float(row.get("close", 0) or 0)
        change = float(row.get("change", 0) or 0)
        payload = bucket[(sector, market)]
        payload["closes"].append(close)
        payload["changes"].append(change)
        payload["close_sum"] += close
        payload["change_sum"] += change
        payload["count"] += 1
    result = []
    for (sector, market), payload in bucket.items():
        closes = payload["closes"]
        changes = payload["changes"]
        avg_close = sum(closes) / len(closes) if closes else 0.0
        avg_change = sum(changes) / len(changes) if changes else 0.0
        result.append(
            {
                "sector": sector,
                "market": market,
                "avg_close": avg_close,
                "avg_change": avg_change,
                "close_sum": payload["close_sum"],
                "change_sum": payload["change_sum"],
                "count": payload["count"],
            }
        )
    return result


def normalize_daily_rows(rows: Iterable[dict]) -> List[dict]:
    """Normalize daily price rows into consistent numeric types."""
    normalized: List[dict] = []
    for row in rows:
        normalized.append(
            {
                "symbol": row.get("symbol"),
                "date": row.get("date"),
                "open": float(row.get("open", 0) or 0),
                "high": float(row.get("high", 0) or 0),
                "low": float(row.get("low", 0) or 0),
                "close": float(row.get("close", 0) or 0),
                "volume": float(row.get("volume", 0) or 0),
            }
        )
    return normalized
