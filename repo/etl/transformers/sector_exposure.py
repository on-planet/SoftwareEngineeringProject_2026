from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List


def build_sector_exposure(rows: Iterable[dict]) -> List[dict]:
    """Aggregate sector exposure from daily price rows.

    Expect rows: {sector, close}
    """
    bucket = defaultdict(float)
    for row in rows:
        sector = row.get("sector") or "未知"
        value = float(row.get("close") or 0)
        bucket[sector] += value
    total = sum(bucket.values())
    result = []
    for sector, value in bucket.items():
        weight = (value / total) if total else 0.0
        result.append({"sector": sector, "value": value, "weight": weight})
    return result
