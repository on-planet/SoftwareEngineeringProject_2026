from __future__ import annotations

import math
from datetime import date, datetime
from typing import Iterable, List


def _to_float(value: float | int | None) -> float:
    if value is None:
        return 0.0
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(num):
        return 0.0
    return num


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _minmax(value: float, low: float, high: float) -> float:
    if high == low:
        return 0.0
    return (value - low) / (high - low)


def calc_profit_quality(net_income: float, cashflow: float) -> float:
    """Calculate profit quality score (0-1)."""
    net_income = _to_float(net_income)
    cashflow = _to_float(cashflow)
    if net_income <= 0:
        return 0.0
    ratio = cashflow / net_income
    return _clip(_minmax(ratio, 0.0, 2.0), 0.0, 1.0)


def calc_growth(revenue: float, last_revenue: float) -> float:
    """Calculate growth score (0-1) with symmetric bounds."""
    revenue = _to_float(revenue)
    last_revenue = _to_float(last_revenue)
    if last_revenue <= 0:
        return 0.0
    raw = (revenue - last_revenue) / last_revenue
    return _clip(_minmax(raw, -0.5, 0.5), 0.0, 1.0)


def calc_risk(debt_ratio: float, short_debt: float, cash: float) -> float:
    """Calculate risk score (0-1), higher is riskier."""
    debt_ratio = _to_float(debt_ratio)
    short_debt = _to_float(short_debt)
    cash = _to_float(cash)
    if cash <= 0:
        return _clip(debt_ratio, 0.0, 1.0)
    raw = debt_ratio + (short_debt / cash)
    return _clip(_minmax(raw, 0.0, 2.0), 0.0, 1.0)


def calc_fundamental_score(
    profit_quality: float,
    growth: float,
    risk: float,
    weights: tuple[float, float, float] = (0.4, 0.3, 0.3),
    scale: float = 100.0,
) -> float:
    """Calculate composite fundamental score, normalized to 0-100 by default."""
    w_profit, w_growth, w_risk = weights
    profit_quality = _clip(_to_float(profit_quality), 0.0, 1.0)
    growth = _clip(_to_float(growth), 0.0, 1.0)
    risk = _clip(_to_float(risk), 0.0, 1.0)
    score_0_1 = (profit_quality * w_profit) + (growth * w_growth) + ((1.0 - risk) * w_risk)
    return _clip(score_0_1, 0.0, 1.0) * max(scale, 0.0)


def normalize_financials(rows: Iterable[dict]) -> List[dict]:
    """Normalize financial rows (types/keys) for loader."""
    normalized: List[dict] = []
    for row in rows:
        normalized.append(
            {
                "symbol": row.get("symbol"),
                "period": row.get("period"),
                "revenue": float(row.get("revenue", 0) or 0),
                "net_income": float(row.get("net_income", 0) or 0),
                "cash_flow": float(row.get("cash_flow", 0) or 0),
                "roe": float(row.get("roe", 0) or 0),
                "debt_ratio": float(row.get("debt_ratio", 0) or 0),
            }
        )
    return normalized


def build_fundamental_score_row(
    symbol: str,
    score: float,
    summary: str,
    as_of: date | datetime,
) -> dict:
    return {
        "symbol": symbol,
        "score": float(score),
        "summary": summary,
        "updated_at": as_of,
    }
