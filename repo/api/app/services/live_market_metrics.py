from __future__ import annotations

from datetime import datetime
from typing import Iterable

from app.schemas.kline import KlinePoint
from app.schemas.risk_series import RiskPoint
from etl.transformers.fundamentals import calc_fundamental_score, calc_growth, calc_profit_quality, calc_risk
from etl.transformers.indicators import (
    calc_adx,
    calc_atr,
    calc_bollinger_bands,
    calc_cci,
    calc_ema,
    calc_kdj,
    calc_ma,
    calc_macd,
    calc_max_drawdown,
    calc_mfi,
    calc_momentum,
    calc_obv,
    calc_roc,
    calc_rsi,
    calc_volatility,
    calc_wma,
    calc_wr,
)

IndicatorParams = dict[str, int | float | str]
IndicatorPayload = dict[str, list[float]]


def build_fundamental_payload(
    symbol: str,
    rows: list[dict],
    *,
    as_of: datetime | None = None,
) -> dict:
    current = rows[0]
    previous = rows[1] if len(rows) > 1 else rows[0]
    profit_quality = calc_profit_quality(current.get("net_income", 0), current.get("cash_flow", 0))
    growth = calc_growth(current.get("revenue", 0), previous.get("revenue", 0) or current.get("revenue", 0))
    risk = calc_risk(current.get("debt_ratio", 0), (current.get("debt_ratio", 0) or 0) * 100.0, 100.0)
    score = calc_fundamental_score(profit_quality, growth, risk)
    return {
        "symbol": symbol,
        "score": float(score),
        "summary": (
            f"{symbol} 综合得分 {score:.1f}。"
            f"盈利质量 {profit_quality:.2f}，成长性 {growth:.2f}，风险项 {risk:.2f}。"
        ),
        "updated_at": as_of or datetime.now(),
    }


def indicator_lines_and_params(indicator: str, window: int) -> tuple[list[str], IndicatorParams]:
    if indicator in {"ma", "sma", "ema", "wma", "rsi", "atr", "cci", "wr", "roc", "mom", "mfi"}:
        return [indicator], {"window": window}
    if indicator == "obv":
        return ["obv"], {}
    if indicator == "macd":
        return ["macd", "signal", "hist"], {"fast": 12, "slow": 26, "signal": 9}
    if indicator == "boll":
        return ["middle", "upper", "lower"], {"window": window, "stddev": 2.0}
    if indicator == "kdj":
        return ["k", "d", "j"], {"window": window, "k_smooth": 3, "d_smooth": 3}
    if indicator == "adx":
        return ["adx", "plus_di", "minus_di"], {"window": window}
    return [indicator], {"window": window}


def build_indicator_payload(indicator: str, rows: list[dict], window: int) -> tuple[list[str], IndicatorParams, IndicatorPayload]:
    closes = [float(row.get("close") or 0.0) for row in rows]
    highs = [float(row.get("high") or 0.0) for row in rows]
    lows = [float(row.get("low") or 0.0) for row in rows]
    volumes = [float(row.get("volume") or 0.0) for row in rows]
    lines, params = indicator_lines_and_params(indicator, window)

    if indicator in {"ma", "sma"}:
        values = calc_ma(closes, window)
        return lines, params, {"ma" if indicator == "ma" else "sma": values}
    if indicator == "ema":
        return lines, params, {"ema": calc_ema(closes, window)}
    if indicator == "wma":
        return lines, params, {"wma": calc_wma(closes, window)}
    if indicator == "rsi":
        return lines, params, {"rsi": calc_rsi(closes, window)}
    if indicator == "macd":
        return lines, params, calc_macd(closes, fast=12, slow=26, signal=9)
    if indicator == "boll":
        return lines, params, calc_bollinger_bands(closes, window, num_std=2.0)
    if indicator == "kdj":
        return lines, params, calc_kdj(highs, lows, closes, window)
    if indicator == "atr":
        return lines, params, {"atr": calc_atr(highs, lows, closes, window)}
    if indicator == "cci":
        return lines, params, {"cci": calc_cci(highs, lows, closes, window)}
    if indicator == "wr":
        return lines, params, {"wr": calc_wr(highs, lows, closes, window)}
    if indicator == "obv":
        return lines, params, {"obv": calc_obv(closes, volumes)}
    if indicator == "roc":
        return lines, params, {"roc": calc_roc(closes, window)}
    if indicator == "mom":
        return lines, params, {"mom": calc_momentum(closes, window)}
    if indicator == "adx":
        return lines, params, calc_adx(highs, lows, closes, window)
    if indicator == "mfi":
        return lines, params, {"mfi": calc_mfi(highs, lows, closes, volumes, window)}
    return [indicator], {"window": window}, {indicator: calc_ma(closes, window)}


def build_risk_snapshot_payload(symbol: str, points: Iterable[KlinePoint]) -> dict | None:
    items = list(points)
    if not items:
        return None
    closes = [float(point.close) for point in items]
    returns = [
        (closes[idx] - closes[idx - 1]) / closes[idx - 1]
        for idx in range(1, len(closes))
        if closes[idx - 1]
    ]
    return {
        "symbol": symbol,
        "max_drawdown": calc_max_drawdown(closes),
        "volatility": calc_volatility(returns),
        "as_of": items[-1].date,
    }


def build_risk_series(points: Iterable[KlinePoint], *, window: int) -> list[RiskPoint]:
    items = list(points)
    closes = [float(point.close) for point in items]
    returns = [
        (closes[idx] - closes[idx - 1]) / closes[idx - 1]
        for idx in range(1, len(closes))
        if closes[idx - 1]
    ]
    output: list[RiskPoint] = []
    for idx, point in enumerate(items):
        window_start = max(0, idx - window + 1)
        window_prices = closes[window_start : idx + 1]
        window_returns = returns[window_start:idx] if idx > 0 else []
        output.append(
            RiskPoint(
                date=point.date,
                max_drawdown=calc_max_drawdown(window_prices),
                volatility=calc_volatility(window_returns),
            )
        )
    return output
