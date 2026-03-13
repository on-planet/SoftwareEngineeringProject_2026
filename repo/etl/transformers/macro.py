from __future__ import annotations

import math
from typing import Iterable, List, Optional


def _to_float(value: float | int | None) -> Optional[float]:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):
        return None
    return num


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _percentile(sorted_values: List[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if pct <= 0:
        return sorted_values[0]
    if pct >= 100:
        return sorted_values[-1]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1


def normalize_macro_value(
    series: Iterable[float],
    *,
    lower_pct: float = 5.0,
    upper_pct: float = 95.0,
    invert: bool = False,
) -> List[float]:
    """Normalize macro indicator series with winsorization and direction control."""
    values = [_to_float(value) for value in series]
    valid = [v for v in values if v is not None]
    if not valid:
        return []
    sorted_vals = sorted(valid)
    low = _percentile(sorted_vals, lower_pct)
    high = _percentile(sorted_vals, upper_pct)
    if high == low:
        normalized = [0.0 for _ in values]
    else:
        normalized = []
        for v in values:
            if v is None:
                normalized.append(0.0)
                continue
            clipped = _clip(v, low, high)
            score = (clipped - low) / (high - low)
            normalized.append(score)

    if invert:
        normalized = [1.0 - v for v in normalized]
    return [_clip(v, 0.0, 1.0) for v in normalized]


def normalize_macro_rows(
    rows: Iterable[dict],
    *,
    lower_pct: float = 5.0,
    upper_pct: float = 95.0,
    invert: bool = False,
) -> List[dict]:
    values = [_to_float(row.get("value")) for row in rows]
    normalized_values = normalize_macro_value(
        [v for v in values if v is not None],
        lower_pct=lower_pct,
        upper_pct=upper_pct,
        invert=invert,
    )
    normalized: List[dict] = []
    idx = 0
    for row, raw in zip(rows, values):
        if raw is None:
            score = 0.0
        else:
            score = normalized_values[idx]
            idx += 1
        normalized.append(
            {
                "key": row.get("key"),
                "date": row.get("date"),
                "value": float(raw or 0.0),
                "score": float(score),
            }
        )
    return normalized
