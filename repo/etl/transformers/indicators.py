from __future__ import annotations

import math
from typing import Iterable


def _to_float(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _sanitize_series(series: Iterable[float | int | None]) -> list[float | None]:
    return [_to_float(value) for value in series]


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _rolling_window(values: list[float | None], end_index: int, window: int) -> list[float]:
    start = max(0, end_index - window + 1)
    return [value for value in values[start : end_index + 1] if value is not None]


def _rolling_mean(values: list[float | None], window: int) -> list[float]:
    if window <= 0:
        return [0.0 for _ in values]
    output: list[float] = []
    for idx in range(len(values)):
        window_vals = _rolling_window(values, idx, window)
        output.append(sum(window_vals) / len(window_vals) if window_vals else 0.0)
    return output


def _rolling_std(values: list[float | None], window: int) -> list[float]:
    if window <= 0:
        return [0.0 for _ in values]
    output: list[float] = []
    for idx in range(len(values)):
        window_vals = _rolling_window(values, idx, window)
        if len(window_vals) < 2:
            output.append(0.0)
            continue
        mean = sum(window_vals) / len(window_vals)
        variance = sum((value - mean) ** 2 for value in window_vals) / len(window_vals)
        output.append(math.sqrt(max(variance, 0.0)))
    return output


def calc_ma(series: Iterable[float | int | None], window: int) -> list[float]:
    values = _sanitize_series(series)
    return _rolling_mean(values, window)


def calc_sma(series: Iterable[float | int | None], window: int) -> list[float]:
    return calc_ma(series, window)


def calc_ema(series: Iterable[float | int | None], window: int) -> list[float]:
    values = _sanitize_series(series)
    if not values:
        return []
    if window <= 0:
        return [0.0 for _ in values]
    alpha = 2.0 / (window + 1.0)
    output: list[float] = []
    ema = 0.0
    initialized = False
    for value in values:
        if value is None:
            output.append(ema if initialized else 0.0)
            continue
        if not initialized:
            ema = value
            initialized = True
        else:
            ema = alpha * value + (1.0 - alpha) * ema
        output.append(ema)
    return output


def calc_wma(series: Iterable[float | int | None], window: int) -> list[float]:
    values = _sanitize_series(series)
    if window <= 0:
        return [0.0 for _ in values]
    output: list[float] = []
    for idx in range(len(values)):
        start = max(0, idx - window + 1)
        window_vals = values[start : idx + 1]
        valid_vals = [value for value in window_vals if value is not None]
        if not valid_vals:
            output.append(0.0)
            continue
        weights: list[float] = []
        aligned_vals: list[float] = []
        weight = 1.0
        for value in window_vals:
            if value is None:
                continue
            weights.append(weight)
            aligned_vals.append(value)
            weight += 1.0
        denominator = sum(weights) or 1.0
        output.append(sum(value * weight for value, weight in zip(aligned_vals, weights)) / denominator)
    return output


def calc_rsi(series: Iterable[float | int | None], window: int = 14) -> list[float]:
    values = _sanitize_series(series)
    count = len(values)
    if count == 0:
        return []
    if window <= 0:
        return [50.0 for _ in values]

    rsis = [50.0 for _ in values]
    if count < 2:
        return rsis

    gains: list[float] = []
    losses: list[float] = []
    for idx in range(1, count):
        prev = values[idx - 1]
        curr = values[idx]
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

    for idx in range(1, init_period + 1):
        gain = sum(gains[:idx]) / idx
        loss = sum(losses[:idx]) / idx
        if loss == 0 and gain == 0:
            rsis[idx] = 50.0
        elif loss == 0:
            rsis[idx] = 100.0
        else:
            rs = gain / loss
            rsis[idx] = 100.0 - (100.0 / (1.0 + rs))

    for idx in range(init_period + 1, count):
        gain = gains[idx - 1]
        loss = losses[idx - 1]
        avg_gain = (avg_gain * (window - 1) + gain) / window
        avg_loss = (avg_loss * (window - 1) + loss) / window
        if avg_loss == 0 and avg_gain == 0:
            rsi_value = 50.0
        elif avg_loss == 0:
            rsi_value = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_value = 100.0 - (100.0 / (1.0 + rs))
        rsis[idx] = _clip(rsi_value, 0.0, 100.0)

    return rsis


def calc_macd(
    series: Iterable[float | int | None],
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, list[float]]:
    values = _sanitize_series(series)
    fast_line = calc_ema(values, fast)
    slow_line = calc_ema(values, slow)
    macd_line = [fast_value - slow_value for fast_value, slow_value in zip(fast_line, slow_line)]
    signal_line = calc_ema(macd_line, signal)
    histogram = [macd_value - signal_value for macd_value, signal_value in zip(macd_line, signal_line)]
    return {"macd": macd_line, "signal": signal_line, "hist": histogram}


def calc_bollinger_bands(
    series: Iterable[float | int | None],
    window: int = 20,
    *,
    num_std: float = 2.0,
) -> dict[str, list[float]]:
    values = _sanitize_series(series)
    middle = calc_sma(values, window)
    stds = _rolling_std(values, window)
    upper = [mid + num_std * std for mid, std in zip(middle, stds)]
    lower = [mid - num_std * std for mid, std in zip(middle, stds)]
    return {"middle": middle, "upper": upper, "lower": lower}


def calc_kdj(
    highs: Iterable[float | int | None],
    lows: Iterable[float | int | None],
    closes: Iterable[float | int | None],
    window: int = 9,
) -> dict[str, list[float]]:
    high_values = _sanitize_series(highs)
    low_values = _sanitize_series(lows)
    close_values = _sanitize_series(closes)
    count = min(len(high_values), len(low_values), len(close_values))
    if count == 0:
        return {"k": [], "d": [], "j": []}
    k_values: list[float] = []
    d_values: list[float] = []
    j_values: list[float] = []
    k_prev = 50.0
    d_prev = 50.0
    for idx in range(count):
        high_window = _rolling_window(high_values, idx, window)
        low_window = _rolling_window(low_values, idx, window)
        close_value = close_values[idx]
        if not high_window or not low_window or close_value is None:
            rsv = 50.0
        else:
            highest = max(high_window)
            lowest = min(low_window)
            if highest == lowest:
                rsv = 50.0
            else:
                rsv = (close_value - lowest) / (highest - lowest) * 100.0
        k_prev = (2.0 * k_prev + rsv) / 3.0
        d_prev = (2.0 * d_prev + k_prev) / 3.0
        j_value = 3.0 * k_prev - 2.0 * d_prev
        k_values.append(_clip(k_prev, 0.0, 100.0))
        d_values.append(_clip(d_prev, 0.0, 100.0))
        j_values.append(j_value)
    return {"k": k_values, "d": d_values, "j": j_values}


def _true_ranges(
    highs: list[float | None],
    lows: list[float | None],
    closes: list[float | None],
) -> list[float]:
    output: list[float] = []
    previous_close: float | None = None
    for high, low, close in zip(highs, lows, closes):
        if high is None or low is None:
            output.append(0.0)
            previous_close = close if close is not None else previous_close
            continue
        if previous_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - previous_close), abs(low - previous_close))
        output.append(max(tr, 0.0))
        previous_close = close if close is not None else previous_close
    return output


def calc_atr(
    highs: Iterable[float | int | None],
    lows: Iterable[float | int | None],
    closes: Iterable[float | int | None],
    window: int = 14,
) -> list[float]:
    high_values = _sanitize_series(highs)
    low_values = _sanitize_series(lows)
    close_values = _sanitize_series(closes)
    true_ranges = _true_ranges(high_values, low_values, close_values)
    return calc_ema(true_ranges, max(1, window))


def calc_cci(
    highs: Iterable[float | int | None],
    lows: Iterable[float | int | None],
    closes: Iterable[float | int | None],
    window: int = 20,
) -> list[float]:
    high_values = _sanitize_series(highs)
    low_values = _sanitize_series(lows)
    close_values = _sanitize_series(closes)
    typical_prices: list[float | None] = []
    for high, low, close in zip(high_values, low_values, close_values):
        if high is None or low is None or close is None:
            typical_prices.append(None)
            continue
        typical_prices.append((high + low + close) / 3.0)
    moving_avg = calc_sma(typical_prices, window)
    output: list[float] = []
    for idx, typical in enumerate(typical_prices):
        if typical is None:
            output.append(0.0)
            continue
        window_vals = _rolling_window(typical_prices, idx, window)
        if not window_vals:
            output.append(0.0)
            continue
        mean_dev = sum(abs(value - moving_avg[idx]) for value in window_vals) / len(window_vals)
        if mean_dev == 0:
            output.append(0.0)
            continue
        output.append((typical - moving_avg[idx]) / (0.015 * mean_dev))
    return output


def calc_wr(
    highs: Iterable[float | int | None],
    lows: Iterable[float | int | None],
    closes: Iterable[float | int | None],
    window: int = 14,
) -> list[float]:
    high_values = _sanitize_series(highs)
    low_values = _sanitize_series(lows)
    close_values = _sanitize_series(closes)
    output: list[float] = []
    for idx, close_value in enumerate(close_values):
        high_window = _rolling_window(high_values, idx, window)
        low_window = _rolling_window(low_values, idx, window)
        if close_value is None or not high_window or not low_window:
            output.append(0.0)
            continue
        highest = max(high_window)
        lowest = min(low_window)
        if highest == lowest:
            output.append(0.0)
            continue
        value = -100.0 * (highest - close_value) / (highest - lowest)
        output.append(_clip(value, -100.0, 0.0))
    return output


def calc_obv(
    closes: Iterable[float | int | None],
    volumes: Iterable[float | int | None],
) -> list[float]:
    close_values = _sanitize_series(closes)
    volume_values = _sanitize_series(volumes)
    if not close_values:
        return []
    output: list[float] = []
    obv = 0.0
    previous_close: float | None = None
    for close_value, volume_value in zip(close_values, volume_values):
        volume = volume_value or 0.0
        if previous_close is None or close_value is None:
            previous_close = close_value if close_value is not None else previous_close
            output.append(obv)
            continue
        if close_value > previous_close:
            obv += volume
        elif close_value < previous_close:
            obv -= volume
        output.append(obv)
        previous_close = close_value
    while len(output) < len(close_values):
        output.append(obv)
    return output


def calc_roc(series: Iterable[float | int | None], window: int = 12) -> list[float]:
    values = _sanitize_series(series)
    output: list[float] = []
    for idx, value in enumerate(values):
        if idx < window or value is None:
            output.append(0.0)
            continue
        previous = values[idx - window]
        if previous in (None, 0):
            output.append(0.0)
            continue
        output.append((value - previous) / previous * 100.0)
    return output


def calc_momentum(series: Iterable[float | int | None], window: int = 10) -> list[float]:
    values = _sanitize_series(series)
    output: list[float] = []
    for idx, value in enumerate(values):
        if idx < window or value is None:
            output.append(0.0)
            continue
        previous = values[idx - window]
        if previous is None:
            output.append(0.0)
            continue
        output.append(value - previous)
    return output


def calc_adx(
    highs: Iterable[float | int | None],
    lows: Iterable[float | int | None],
    closes: Iterable[float | int | None],
    window: int = 14,
) -> dict[str, list[float]]:
    high_values = _sanitize_series(highs)
    low_values = _sanitize_series(lows)
    close_values = _sanitize_series(closes)
    count = min(len(high_values), len(low_values), len(close_values))
    if count == 0:
        return {"adx": [], "plus_di": [], "minus_di": []}

    plus_dm = [0.0]
    minus_dm = [0.0]
    for idx in range(1, count):
        current_high = high_values[idx]
        current_low = low_values[idx]
        previous_high = high_values[idx - 1]
        previous_low = low_values[idx - 1]
        if None in (current_high, current_low, previous_high, previous_low):
            plus_dm.append(0.0)
            minus_dm.append(0.0)
            continue
        up_move = current_high - previous_high
        down_move = previous_low - current_low
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

    tr = _true_ranges(high_values[:count], low_values[:count], close_values[:count])
    atr = calc_ema(tr, max(1, window))
    plus_di: list[float] = []
    minus_di: list[float] = []
    smoothed_plus = calc_ema(plus_dm, max(1, window))
    smoothed_minus = calc_ema(minus_dm, max(1, window))
    for idx in range(count):
        atr_value = atr[idx] if idx < len(atr) else 0.0
        if atr_value == 0:
            plus_di.append(0.0)
            minus_di.append(0.0)
            continue
        plus_di.append(100.0 * smoothed_plus[idx] / atr_value)
        minus_di.append(100.0 * smoothed_minus[idx] / atr_value)

    dx: list[float] = []
    for plus_value, minus_value in zip(plus_di, minus_di):
        denominator = plus_value + minus_value
        if denominator == 0:
            dx.append(0.0)
            continue
        dx.append(abs(plus_value - minus_value) / denominator * 100.0)
    adx = calc_ema(dx, max(1, window))
    return {"adx": adx, "plus_di": plus_di, "minus_di": minus_di}


def calc_mfi(
    highs: Iterable[float | int | None],
    lows: Iterable[float | int | None],
    closes: Iterable[float | int | None],
    volumes: Iterable[float | int | None],
    window: int = 14,
) -> list[float]:
    high_values = _sanitize_series(highs)
    low_values = _sanitize_series(lows)
    close_values = _sanitize_series(closes)
    volume_values = _sanitize_series(volumes)
    typical_prices: list[float | None] = []
    for high, low, close in zip(high_values, low_values, close_values):
        if high is None or low is None or close is None:
            typical_prices.append(None)
            continue
        typical_prices.append((high + low + close) / 3.0)

    positive_flow = [0.0]
    negative_flow = [0.0]
    for idx in range(1, len(typical_prices)):
        current_price = typical_prices[idx]
        previous_price = typical_prices[idx - 1]
        volume = volume_values[idx] or 0.0
        if current_price is None or previous_price is None:
            positive_flow.append(0.0)
            negative_flow.append(0.0)
            continue
        raw_flow = current_price * volume
        if current_price > previous_price:
            positive_flow.append(raw_flow)
            negative_flow.append(0.0)
        elif current_price < previous_price:
            positive_flow.append(0.0)
            negative_flow.append(raw_flow)
        else:
            positive_flow.append(0.0)
            negative_flow.append(0.0)

    output: list[float] = []
    for idx in range(len(typical_prices)):
        pos_sum = sum(positive_flow[max(0, idx - window + 1) : idx + 1])
        neg_sum = sum(negative_flow[max(0, idx - window + 1) : idx + 1])
        if neg_sum == 0 and pos_sum == 0:
            output.append(50.0)
        elif neg_sum == 0:
            output.append(100.0)
        else:
            money_ratio = pos_sum / neg_sum
            output.append(100.0 - (100.0 / (1.0 + money_ratio)))
    return output


def calc_volatility(returns: Iterable[float], annualization_factor: float = 1.0) -> float:
    values = [value for value in _sanitize_series(returns) if value is not None]
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    if variance < 0:
        variance = 0.0
    return math.sqrt(variance) * math.sqrt(max(annualization_factor, 0.0))


def calc_max_drawdown(series: Iterable[float]) -> float:
    values = [value for value in _sanitize_series(series) if value is not None and value > 0]
    if not values:
        return 0.0
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        if value > peak:
            peak = value
        if peak <= 0:
            continue
        drawdown = (peak - value) / peak
        max_drawdown = max(max_drawdown, drawdown)
    return _clip(max_drawdown, 0.0, 1.0)
