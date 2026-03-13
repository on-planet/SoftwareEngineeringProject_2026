from __future__ import annotations


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def pct_change(current: float, previous: float, default: float = 0.0) -> float:
    if previous == 0:
        return default
    return (current - previous) / previous
