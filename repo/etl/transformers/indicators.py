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


def _sanitize_series(series: Iterable[float]) -> List[Optional[float]]:
    return [_to_float(value) for value in series]


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def calc_ma(series: Iterable[float], window: int) -> List[float]:
    """Calculate moving average with missing-value handling."""
    values = _sanitize_series(series)
    if window <= 0:
        return []
    result: List[float] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        window_vals = [v for v in values[start : i + 1] if v is not None]
        if not window_vals:
            result.append(0.0)
        else:
            result.append(sum(window_vals) / len(window_vals))
    return result


def calc_rsi(series: Iterable[float], window: int = 14) -> List[float]:
    """Calculate RSI (Wilder smoothing) with edge-case handling."""
    values = _sanitize_series(series)
    n = len(values)
    if n == 0:
        return []
    if window <= 0:
        return [0.0 for _ in values]

    rsis: List[float] = [50.0 for _ in values]
    if n < 2:
        return rsis

    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, n):
        prev = values[i - 1]
        curr = values[i]
        if prev is None or curr is None:
            gains.append(0.0)
            losses.append(0.0)
            continue
        diff = curr - prev
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))

    init_period = min(window, len(gains))
    if init_period == 0:
        return rsis

    avg_gain = sum(gains[:init_period]) / init_period
    avg_loss = sum(losses[:init_period]) / init_period

    for i in range(1, init_period + 1):
        g = sum(gains[:i]) / i
        l = sum(losses[:i]) / i
        if l == 0 and g == 0:
            rsis[i] = 50.0
        elif l == 0:
            rsis[i] = 100.0
        else:
            rs = g / l
            rsis[i] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(init_period + 1, n):
        gain = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = (avg_gain * (window - 1) + gain) / window
        avg_loss = (avg_loss * (window - 1) + loss) / window
        if avg_loss == 0 and avg_gain == 0:
            rsi_value = 50.0
        elif avg_loss == 0:
            rsi_value = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_value = 100.0 - (100.0 / (1.0 + rs))
        rsis[i] = _clip(rsi_value, 0.0, 100.0)

    return rsis


def calc_volatility(returns: Iterable[float], annualization_factor: float = 1.0) -> float:
    """Calculate volatility for a return series with optional annualization."""
    values = [v for v in _sanitize_series(returns) if v is not None]
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    if variance < 0:
        variance = 0.0
    return (variance ** 0.5) * math.sqrt(max(annualization_factor, 0.0))


def calc_max_drawdown(series: Iterable[float]) -> float:
    """Calculate max drawdown for a price series with non-positive guards."""
    values = [v for v in _sanitize_series(series) if v is not None and v > 0]
    if not values:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        if peak <= 0:
            continue
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    return _clip(max_dd, 0.0, 1.0)
