from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import sqrt
from typing import Callable

from sqlalchemy import and_, func, inspect
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.bond_market_trade import BondMarketTrade
from app.models.daily_prices import DailyPrice
from app.models.futures_price import FuturesPrice
from app.models.fx_quote import FxPairQuote, FxSpotQuote
from app.models.indices import Index
from app.models.macro import Macro
from app.models.stock_factor_exposure_cache import StockFactorExposureCache
from app.schemas.portfolio_stress import PortfolioStressOut, PortfolioStressPreviewIn, PortfolioStressRuleIn
from app.services.cache_utils import build_cache_key
from app.services.portfolio_snapshot_service import (
    HoldingSnapshot,
    canonical_sector_label,
    load_bought_target_snapshots,
    load_watch_target_snapshots,
    sector_has_keyword,
)

PORTFOLIO_STRESS_CACHE_TTL = 120
DEFAULT_POSITION_LIMIT = 8
PORTFOLIO_STRESS_CACHE_VERSION = "v3"
FACTOR_LOOKBACK_MIN = 60
FACTOR_LOOKBACK_MAX = 120
FACTOR_DEFAULT_PROPAGATION_LAMBDA = 0.22
FACTOR_REGRESSION_RIDGE = 1e-6
FACTOR_CACHE_STALE_DAYS = 7


@dataclass(frozen=True)
class ScenarioDefinition:
    code: str
    name: str
    description: str
    rules: tuple[str, ...]
    shock_fn: Callable[[HoldingSnapshot], float]


@dataclass(frozen=True)
class StockFactorExposure:
    market_beta: float
    sector_beta: float
    rate_beta: float
    fx_beta: float
    commodity_beta: float
    idiosyncratic_term: float
    sample_size: int
    window_size: int


@dataclass(frozen=True)
class FactorShockVector:
    market_shock: float
    sector_shocks: dict[str, float]
    rate_shock: float
    fx_shock: float
    commodity_shock: float
    idiosyncratic_shocks: dict[str, float]
    propagation_lambda: float


def _bank_sector_shock(snapshot: HoldingSnapshot) -> float:
    if snapshot.sector == "金融" or sector_has_keyword(snapshot, ("bank", "broker", "insurance", "finance", "fintech")):
        return -0.05
    return 0.0


def _hk_tech_shock(snapshot: HoldingSnapshot) -> float:
    if snapshot.market != "HK":
        return 0.0
    if snapshot.sector in {"科技", "电信传媒"}:
        return -0.08
    if sector_has_keyword(
        snapshot,
        (
            "tech",
            "technology",
            "internet",
            "software",
            "semiconductor",
            "media",
            "telecom",
            "ai",
            "cloud",
            "platform",
            "e-commerce",
            "ecommerce",
        ),
    ):
        return -0.08
    return 0.0


def _us_yield_up_shock(snapshot: HoldingSnapshot) -> float:
    if snapshot.sector == "金融":
        return 0.01
    if snapshot.sector in {"科技", "电信传媒"} or sector_has_keyword(
        snapshot,
        ("tech", "technology", "internet", "software", "semiconductor", "ai", "cloud", "growth"),
    ):
        return -0.06 if snapshot.market in {"HK", "US"} else -0.04
    if snapshot.sector == "房地产":
        return -0.05
    if snapshot.sector in {"公用事业", "医疗健康"}:
        return -0.03
    if snapshot.sector == "消费":
        return -0.02
    if snapshot.market in {"HK", "US"}:
        return -0.02
    return -0.01


SCENARIOS: tuple[ScenarioDefinition, ...] = (
    ScenarioDefinition(
        code="bank_sector_drop",
        name="银行板块回撤",
        description="假设银行和金融板块统一下跌 5%，观察组合对单一行业回撤的敏感度。",
        rules=("金融/银行持仓 -5%", "其他持仓 0%"),
        shock_fn=_bank_sector_shock,
    ),
    ScenarioDefinition(
        code="hk_tech_pullback",
        name="港股科技回撤",
        description="假设港股科技和互联网平台整体回撤 8%，评估组合对成长风格波动的弹性。",
        rules=("港股科技/互联网持仓 -8%", "其他持仓 0%"),
        shock_fn=_hk_tech_shock,
    ),
    ScenarioDefinition(
        code="us_yield_up_50bp",
        name="美债收益率上行",
        description="假设美债收益率上行 50bp，成长和利率敏感资产承压，金融板块小幅受益。",
        rules=("科技/传媒 -4%~-6%", "房地产 -5%", "公用事业/医疗 -3%", "金融 +1%", "其他 -1%~-2%"),
        shock_fn=_us_yield_up_shock,
    ),
)


def _serialize_bucket_rows(
    bucket_changes: dict[str, float],
    bucket_values: dict[str, float],
    total_value: float,
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for label, value_change in bucket_changes.items():
        affected_value = float(bucket_values.get(label) or 0.0)
        rows.append(
            {
                "label": label,
                "affected_value": affected_value,
                "portfolio_weight": (affected_value / total_value) if total_value else 0.0,
                "value_change": float(value_change),
            }
        )
    rows.sort(key=lambda item: abs(float(item["value_change"])), reverse=True)
    return rows


def clip_shock_pct(value: float) -> float:
    return max(-0.95, min(0.95, float(value)))


def scope_value_matches(rule: PortfolioStressRuleIn, snapshot: HoldingSnapshot) -> bool:
    scope_type = str(rule.scope_type or "").lower()
    scope_value = str(rule.scope_value or "").strip()
    if scope_type == "all":
        return True
    if not scope_value:
        return False
    if scope_type == "market":
        return snapshot.market.upper() == scope_value.upper()
    if scope_type == "symbol":
        return snapshot.symbol.upper() == scope_value.upper()
    if scope_type == "sector":
        target = canonical_sector_label(scope_value, snapshot.market).lower()
        return (
            target in snapshot.sector.lower()
            or target in snapshot.raw_sector.lower()
            or scope_value.lower() in snapshot.sector.lower()
            or scope_value.lower() in snapshot.raw_sector.lower()
        )
    return False


def custom_rule_label(rule: PortfolioStressRuleIn) -> str:
    shock_text = f"{rule.shock_pct * 100:+.1f}%"
    if rule.scope_type == "all":
        return f"全组合 {shock_text}"
    scope_name = {
        "market": "市场",
        "sector": "行业",
        "symbol": "股票",
    }.get(rule.scope_type, rule.scope_type)
    return f"{scope_name}:{rule.scope_value} {shock_text}"


def build_custom_shock_function(rules: list[PortfolioStressRuleIn]) -> Callable[[HoldingSnapshot], float]:
    normalized_rules = list(rules)

    def _shock(snapshot: HoldingSnapshot) -> float:
        total_shock = 0.0
        for rule in normalized_rules:
            if scope_value_matches(rule, snapshot):
                total_shock += float(rule.shock_pct)
        return clip_shock_pct(total_shock)

    return _shock


def _series_pct_change(points: list[tuple[date, float]]) -> dict[date, float]:
    if not points:
        return {}
    ordered = sorted(points, key=lambda item: item[0])
    result: dict[date, float] = {}
    prev_value: float | None = None
    for item_date, value in ordered:
        current = float(value)
        if prev_value is not None and abs(prev_value) > 1e-12:
            result[item_date] = clip_shock_pct((current / prev_value) - 1.0)
        prev_value = current
    return result


def _average_series(series_list: list[dict[date, float]]) -> dict[date, float]:
    if not series_list:
        return {}
    bucket: dict[date, list[float]] = defaultdict(list)
    for series in series_list:
        for item_date, value in series.items():
            bucket[item_date].append(float(value))
    averaged: dict[date, float] = {}
    for item_date, values in bucket.items():
        if not values:
            continue
        averaged[item_date] = sum(values) / float(len(values))
    return averaged


def _pearson_corr(values_x: list[float], values_y: list[float]) -> float:
    n = min(len(values_x), len(values_y))
    if n < 3:
        return 0.0
    xs = values_x[:n]
    ys = values_y[:n]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=False))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 1e-12 or var_y <= 1e-12:
        return 0.0
    return max(-1.0, min(1.0, cov / sqrt(var_x * var_y)))


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    n = len(vector)
    if n == 0 or any(len(row) != n for row in matrix):
        return None
    aug = [row[:] + [vector[idx]] for idx, row in enumerate(matrix)]
    for col in range(n):
        pivot_row = max(range(col, n), key=lambda row_idx: abs(aug[row_idx][col]))
        pivot = aug[pivot_row][col]
        if abs(pivot) <= 1e-12:
            return None
        if pivot_row != col:
            aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        pivot = aug[col][col]
        for j in range(col, n + 1):
            aug[col][j] /= pivot
        for row_idx in range(n):
            if row_idx == col:
                continue
            factor = aug[row_idx][col]
            if abs(factor) <= 1e-12:
                continue
            for j in range(col, n + 1):
                aug[row_idx][j] -= factor * aug[col][j]
    return [aug[idx][n] for idx in range(n)]


def _ols_coefficients(feature_rows: list[list[float]], targets: list[float]) -> list[float] | None:
    if not feature_rows or len(feature_rows) != len(targets):
        return None
    feature_count = len(feature_rows[0])
    if feature_count == 0:
        return None
    augmented_rows = [row + [1.0] for row in feature_rows]
    dim = feature_count + 1
    xtx = [[0.0 for _ in range(dim)] for _ in range(dim)]
    xty = [0.0 for _ in range(dim)]
    for row, target in zip(augmented_rows, targets, strict=False):
        for i in range(dim):
            xty[i] += row[i] * target
            for j in range(dim):
                xtx[i][j] += row[i] * row[j]
    for idx in range(feature_count):
        xtx[idx][idx] += FACTOR_REGRESSION_RIDGE
    return _solve_linear_system(xtx, xty)


def _load_stock_return_series(
    db: Session,
    symbols: list[str],
    *,
    since: date,
) -> dict[str, dict[date, float]]:
    if not symbols:
        return {}
    try:
        rows = (
            db.query(DailyPrice.symbol, DailyPrice.date, DailyPrice.close)
            .filter(DailyPrice.symbol.in_(symbols), DailyPrice.date >= since)
            .order_by(DailyPrice.symbol.asc(), DailyPrice.date.asc())
            .all()
        )
    except Exception:
        return {}

    close_series: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for symbol, item_date, close in rows:
        if not isinstance(item_date, date):
            continue
        close_value = float(close or 0.0)
        if close_value <= 0:
            continue
        close_series[str(symbol)].append((item_date, close_value))
    return {symbol: _series_pct_change(points) for symbol, points in close_series.items() if len(points) >= 2}


def _load_index_return_series(db: Session, symbols: tuple[str, ...], *, since: date) -> dict[str, dict[date, float]]:
    if not symbols:
        return {}
    try:
        rows = (
            db.query(Index.symbol, Index.date, Index.close)
            .filter(Index.symbol.in_(symbols), Index.date >= since)
            .order_by(Index.symbol.asc(), Index.date.asc())
            .all()
        )
    except Exception:
        return {}
    close_series: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for symbol, item_date, close in rows:
        if not isinstance(item_date, date):
            continue
        close_value = float(close or 0.0)
        if close_value <= 0:
            continue
        close_series[str(symbol)] += [(item_date, close_value)]
    return {symbol: _series_pct_change(points) for symbol, points in close_series.items() if len(points) >= 2}


def _build_market_factor_series(
    db: Session,
    snapshots: list[HoldingSnapshot],
    stock_returns: dict[str, dict[date, float]],
    *,
    since: date,
) -> dict[str, dict[date, float]]:
    market_candidates: dict[str, tuple[str, ...]] = {
        "A": ("000300.SH", "000001.SH", "399001.SZ"),
        "HK": ("HKHSI", "HKHSCEI", "HKHSTECH"),
        "US": ("SPX", "SP500", "IXIC", "DJI", ".INX"),
    }
    symbols_needed = tuple({item for values in market_candidates.values() for item in values})
    index_series = _load_index_return_series(db, symbols_needed, since=since)

    by_market_symbols: dict[str, list[str]] = defaultdict(list)
    for snapshot in snapshots:
        by_market_symbols[str(snapshot.market).upper()].append(snapshot.symbol)

    result: dict[str, dict[date, float]] = {}
    for market, symbols in by_market_symbols.items():
        selected: dict[date, float] | None = None
        for candidate in market_candidates.get(market, ()):
            candidate_series = index_series.get(candidate)
            if candidate_series and len(candidate_series) >= 20:
                selected = candidate_series
                break
        if selected is None:
            fallback_series = [stock_returns.get(symbol, {}) for symbol in symbols if stock_returns.get(symbol)]
            selected = _average_series(fallback_series)
        result[market] = selected or {}
    return result


def _build_sector_factor_series(
    snapshots: list[HoldingSnapshot],
    stock_returns: dict[str, dict[date, float]],
) -> dict[tuple[str, str], dict[date, float]]:
    buckets: dict[tuple[str, str], list[dict[date, float]]] = defaultdict(list)
    for snapshot in snapshots:
        key = (str(snapshot.market).upper(), str(snapshot.sector))
        series = stock_returns.get(snapshot.symbol)
        if not series:
            continue
        buckets[key].append(series)
    return {key: _average_series(series_list) for key, series_list in buckets.items()}


def _load_macro_rate_factor_series(db: Session, *, since: date) -> dict[date, float]:
    try:
        key_rows = (
            db.query(Macro.key, func.count(Macro.date).label("cnt"))
            .filter(
                Macro.date >= since,
                and_(
                    Macro.value.isnot(None),
                    func.length(Macro.key) > 0,
                ),
            )
            .group_by(Macro.key)
            .all()
        )
    except Exception:
        key_rows = []

    candidates = []
    for key, count in key_rows:
        normalized = str(key or "").upper()
        if any(token in normalized for token in ("YIELD", "RATE", "10Y", "LPR", "SHIBOR", "FED")):
            candidates.append((str(key), int(count or 0)))
    candidates.sort(key=lambda item: item[1], reverse=True)
    for key, _ in candidates[:8]:
        try:
            rows = (
                db.query(Macro.date, Macro.value)
                .filter(Macro.key == key, Macro.date >= since)
                .order_by(Macro.date.asc())
                .all()
            )
        except Exception:
            continue
        points = [(item_date, float(value or 0.0)) for item_date, value in rows if isinstance(item_date, date)]
        points = [item for item in points if abs(item[1]) > 1e-12]
        if len(points) < 20:
            continue
        series = _series_pct_change(points)
        if len(series) >= 20:
            return series

    try:
        trade_rows = (
            db.query(BondMarketTrade.as_of, BondMarketTrade.weighted_yield)
            .filter(BondMarketTrade.as_of >= datetime.combine(since, datetime.min.time()))
            .order_by(BondMarketTrade.as_of.asc())
            .all()
        )
    except Exception:
        trade_rows = []
    if not trade_rows:
        return {}
    by_day: dict[date, list[float]] = defaultdict(list)
    for as_of, weighted_yield in trade_rows:
        if as_of is None:
            continue
        day = as_of.date()
        value = float(weighted_yield or 0.0)
        if abs(value) <= 1e-12:
            continue
        by_day[day].append(value)
    points = sorted((day, sum(values) / len(values)) for day, values in by_day.items() if values)
    return _series_pct_change(points)


def _load_fx_factor_series(db: Session, *, since: date) -> dict[date, float]:
    candidate_pairs = (
        "USDCNY",
        "USD/CNY",
        "USDT/CNY",
        "CNYUSD",
        "CNY/USD",
    )
    try:
        pair_rows = (
            db.query(FxPairQuote.currency_pair, FxPairQuote.as_of, FxPairQuote.bid, FxPairQuote.ask)
            .filter(FxPairQuote.as_of >= datetime.combine(since, datetime.min.time()))
            .order_by(FxPairQuote.as_of.asc())
            .all()
        )
    except Exception:
        pair_rows = []
    if not pair_rows:
        try:
            pair_rows = (
                db.query(FxSpotQuote.currency_pair, FxSpotQuote.as_of, FxSpotQuote.bid, FxSpotQuote.ask)
                .filter(FxSpotQuote.as_of >= datetime.combine(since, datetime.min.time()))
                .order_by(FxSpotQuote.as_of.asc())
                .all()
            )
        except Exception:
            pair_rows = []
    if not pair_rows:
        return {}

    by_pair_day: dict[str, dict[date, tuple[datetime, float]]] = defaultdict(dict)
    for pair, as_of, bid, ask in pair_rows:
        if as_of is None:
            continue
        pair_key = str(pair or "").upper().replace(" ", "")
        if not pair_key:
            continue
        mid = float(bid or 0.0) if ask is None else (float(bid or 0.0) + float(ask or 0.0)) / 2.0
        if mid <= 0:
            continue
        day = as_of.date()
        previous = by_pair_day[pair_key].get(day)
        if previous is None or as_of > previous[0]:
            by_pair_day[pair_key][day] = (as_of, mid)

    best_pair: str | None = None
    best_series: dict[date, float] = {}
    for pair_key, day_map in by_pair_day.items():
        points = sorted((day, item[1]) for day, item in day_map.items())
        series = _series_pct_change(points)
        if len(series) > len(best_series):
            best_pair = pair_key
            best_series = series
    if not best_pair or len(best_series) < 10:
        return {}
    if "CNYUSD" in best_pair:
        return {item_date: -value for item_date, value in best_series.items()}
    if best_pair not in {value.upper().replace(" ", "") for value in candidate_pairs}:
        return best_series
    return best_series


def _load_commodity_factor_series(db: Session, *, since: date) -> dict[date, float]:
    oil_symbols = {"SC", "CL", "OIL"}
    gold_symbols = {"AU", "AG", "GC"}
    all_symbols = tuple(sorted(oil_symbols | gold_symbols))
    try:
        rows = (
            db.query(FuturesPrice.symbol, FuturesPrice.date, FuturesPrice.close)
            .filter(FuturesPrice.symbol.in_(all_symbols), FuturesPrice.date >= since)
            .order_by(FuturesPrice.symbol.asc(), FuturesPrice.date.asc())
            .all()
        )
    except Exception:
        return {}

    close_series: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for symbol, item_date, close in rows:
        if not isinstance(item_date, date):
            continue
        value = float(close or 0.0)
        if value <= 0:
            continue
        close_series[str(symbol).upper()].append((item_date, value))

    return_series: dict[str, dict[date, float]] = {
        symbol: _series_pct_change(points) for symbol, points in close_series.items() if len(points) >= 2
    }
    oil_series = _average_series([series for symbol, series in return_series.items() if symbol in oil_symbols])
    gold_series = _average_series([series for symbol, series in return_series.items() if symbol in gold_symbols])
    combined = _average_series([series for series in (oil_series, gold_series) if series])
    return combined


def _ensure_factor_exposure_cache_table(db: Session) -> None:
    bind = db.get_bind()
    if inspect(bind).has_table(StockFactorExposureCache.__tablename__):
        return
    StockFactorExposureCache.__table__.create(bind=bind, checkfirst=True)


def _load_cached_factor_exposures(
    db: Session,
    snapshots: list[HoldingSnapshot],
    latest_return_dates: dict[str, date],
) -> dict[str, StockFactorExposure]:
    if not snapshots or not latest_return_dates:
        return {}
    _ensure_factor_exposure_cache_table(db)
    symbols = [snapshot.symbol for snapshot in snapshots]
    min_as_of = min(latest_return_dates.values()) - timedelta(days=FACTOR_CACHE_STALE_DAYS)
    try:
        rows = (
            db.query(StockFactorExposureCache)
            .filter(
                StockFactorExposureCache.symbol.in_(symbols),
                StockFactorExposureCache.as_of >= min_as_of,
            )
            .all()
        )
    except Exception:
        return {}

    best_rows: dict[str, StockFactorExposureCache] = {}
    for row in rows:
        symbol = str(row.symbol)
        latest_date = latest_return_dates.get(symbol)
        if latest_date is None:
            continue
        if row.as_of is None or row.as_of > latest_date:
            continue
        prev = best_rows.get(symbol)
        if prev is None or prev.as_of is None or row.as_of > prev.as_of:
            best_rows[symbol] = row

    result: dict[str, StockFactorExposure] = {}
    for symbol, row in best_rows.items():
        if int(row.sample_size or 0) < FACTOR_LOOKBACK_MIN:
            continue
        result[symbol] = StockFactorExposure(
            market_beta=float(row.market_beta or 0.0),
            sector_beta=float(row.sector_beta or 0.0),
            rate_beta=float(row.rate_beta or 0.0),
            fx_beta=float(row.fx_beta or 0.0),
            commodity_beta=float(row.commodity_beta or 0.0),
            idiosyncratic_term=float(row.idiosyncratic_term or 0.0),
            sample_size=int(row.sample_size or 0),
            window_size=int(row.window_size or 0),
        )
    return result


def _upsert_factor_exposure_cache(
    db: Session,
    snapshots_by_symbol: dict[str, HoldingSnapshot],
    latest_return_dates: dict[str, date],
    exposures: dict[str, StockFactorExposure],
) -> None:
    if not exposures:
        return
    _ensure_factor_exposure_cache_table(db)
    try:
        for symbol, exposure in exposures.items():
            as_of = latest_return_dates.get(symbol)
            snapshot = snapshots_by_symbol.get(symbol)
            if as_of is None or snapshot is None:
                continue
            db.merge(
                StockFactorExposureCache(
                    symbol=symbol,
                    as_of=as_of,
                    market=str(snapshot.market or ""),
                    sector=str(snapshot.sector or ""),
                    market_beta=float(exposure.market_beta),
                    sector_beta=float(exposure.sector_beta),
                    rate_beta=float(exposure.rate_beta),
                    fx_beta=float(exposure.fx_beta),
                    commodity_beta=float(exposure.commodity_beta),
                    idiosyncratic_term=float(exposure.idiosyncratic_term),
                    sample_size=int(exposure.sample_size),
                    window_size=int(exposure.window_size),
                )
            )
        db.commit()
    except Exception:
        db.rollback()


def _estimate_latest_factor_exposures(
    db: Session,
    snapshots: list[HoldingSnapshot],
) -> tuple[dict[str, StockFactorExposure], dict[str, dict[str, float]]]:
    symbols = [snapshot.symbol for snapshot in snapshots]
    if not symbols:
        return {}, {}
    since = date.today() - timedelta(days=420)
    stock_returns = _load_stock_return_series(db, symbols, since=since)
    if not stock_returns:
        return {}, {}

    market_series = _build_market_factor_series(db, snapshots, stock_returns, since=since)
    sector_series = _build_sector_factor_series(snapshots, stock_returns)
    rate_series = _load_macro_rate_factor_series(db, since=since)
    fx_series = _load_fx_factor_series(db, since=since)
    commodity_series = _load_commodity_factor_series(db, since=since)

    latest_return_dates = {symbol: max(series.keys()) for symbol, series in stock_returns.items() if series}
    snapshots_by_symbol = {snapshot.symbol: snapshot for snapshot in snapshots}
    exposures: dict[str, StockFactorExposure] = _load_cached_factor_exposures(db, snapshots, latest_return_dates)
    computed_to_cache: dict[str, StockFactorExposure] = {}
    for snapshot in snapshots:
        if snapshot.symbol in exposures:
            continue
        y_series = stock_returns.get(snapshot.symbol)
        if not y_series:
            continue
        market_factor = market_series.get(str(snapshot.market).upper(), {})
        sector_factor = sector_series.get((str(snapshot.market).upper(), str(snapshot.sector)), {})
        if not market_factor or not sector_factor:
            continue

        dates = sorted(set(y_series.keys()) & set(market_factor.keys()) & set(sector_factor.keys()))
        feature_rows: list[list[float]] = []
        targets: list[float] = []
        date_points: list[date] = []
        for item_date in dates:
            feature_rows.append(
                [
                    float(market_factor.get(item_date) or 0.0),
                    float(sector_factor.get(item_date) or 0.0),
                    float(rate_series.get(item_date) or 0.0),
                    float(fx_series.get(item_date) or 0.0),
                    float(commodity_series.get(item_date) or 0.0),
                ]
            )
            targets.append(float(y_series[item_date]))
            date_points.append(item_date)
        if len(feature_rows) < FACTOR_LOOKBACK_MIN:
            continue

        latest_coeffs: list[float] | None = None
        latest_residual = 0.0
        latest_window_size = 0
        for end_idx in range(FACTOR_LOOKBACK_MIN, len(feature_rows) + 1):
            start_idx = max(0, end_idx - FACTOR_LOOKBACK_MAX)
            window_rows = feature_rows[start_idx:end_idx]
            window_targets = targets[start_idx:end_idx]
            if len(window_rows) < FACTOR_LOOKBACK_MIN:
                continue
            coeffs = _ols_coefficients(window_rows, window_targets)
            if coeffs is None:
                continue
            predicted = sum(coeffs[i] * window_rows[-1][i] for i in range(5)) + coeffs[5]
            latest_residual = float(window_targets[-1]) - float(predicted)
            latest_coeffs = coeffs
            latest_window_size = len(window_rows)
        if latest_coeffs is None:
            continue

        exposures[snapshot.symbol] = StockFactorExposure(
            market_beta=float(latest_coeffs[0]),
            sector_beta=float(latest_coeffs[1]),
            rate_beta=float(latest_coeffs[2]),
            fx_beta=float(latest_coeffs[3]),
            commodity_beta=float(latest_coeffs[4]),
            idiosyncratic_term=clip_shock_pct(latest_residual * 0.35),
            sample_size=len(feature_rows),
            window_size=latest_window_size,
        )
        computed_to_cache[snapshot.symbol] = exposures[snapshot.symbol]

    _upsert_factor_exposure_cache(db, snapshots_by_symbol, latest_return_dates, computed_to_cache)

    correlation_matrix: dict[str, dict[str, float]] = {snapshot.symbol: {} for snapshot in snapshots}
    for left in snapshots:
        left_series = stock_returns.get(left.symbol, {})
        left_dates = sorted(left_series.keys(), reverse=True)[:FACTOR_LOOKBACK_MAX]
        for right in snapshots:
            if left.symbol == right.symbol:
                correlation_matrix[left.symbol][right.symbol] = 0.0
                continue
            right_series = stock_returns.get(right.symbol, {})
            overlap_dates = [item_date for item_date in left_dates if item_date in right_series][:FACTOR_LOOKBACK_MAX]
            xs = [float(left_series[item_date]) for item_date in overlap_dates]
            ys = [float(right_series[item_date]) for item_date in overlap_dates]
            correlation_matrix[left.symbol][right.symbol] = _pearson_corr(xs, ys)
    return exposures, correlation_matrix


def _build_factor_shock_vector(
    rules: list[PortfolioStressRuleIn],
    *,
    factor_overrides: dict[str, object] | None = None,
    propagation_lambda: float | None = None,
) -> FactorShockVector:
    market_shock = 0.0
    market_hits = 0
    sector_shocks: dict[str, float] = defaultdict(float)
    idio_shocks: dict[str, float] = defaultdict(float)
    for rule in rules:
        scope_type = str(rule.scope_type or "").lower()
        scope_value = str(rule.scope_value or "").strip()
        shock = float(rule.shock_pct)
        if scope_type in {"all", "market"}:
            market_shock += shock
            market_hits += 1
            continue
        if scope_type == "sector":
            sector_key = canonical_sector_label(scope_value, None)
            sector_shocks[sector_key] += shock
            continue
        if scope_type == "symbol":
            idio_shocks[scope_value.upper()] += shock

    if market_hits > 1:
        market_shock /= float(market_hits)
    rate_shock = 0.0
    fx_shock = 0.0
    commodity_shock = 0.0
    lambda_value = FACTOR_DEFAULT_PROPAGATION_LAMBDA if propagation_lambda is None else float(propagation_lambda)

    if isinstance(factor_overrides, dict):
        if "market_shock" in factor_overrides:
            market_shock = float(factor_overrides.get("market_shock") or 0.0)
        if "rate_shock" in factor_overrides:
            rate_shock = float(factor_overrides.get("rate_shock") or 0.0)
        if "fx_shock" in factor_overrides:
            fx_shock = float(factor_overrides.get("fx_shock") or 0.0)
        if "commodity_shock" in factor_overrides:
            commodity_shock = float(factor_overrides.get("commodity_shock") or 0.0)
        if isinstance(factor_overrides.get("sector_shocks"), dict):
            for label, value in dict(factor_overrides.get("sector_shocks") or {}).items():
                key = canonical_sector_label(str(label), None)
                sector_shocks[key] += float(value or 0.0)
        if isinstance(factor_overrides.get("idiosyncratic_shocks"), dict):
            for symbol, value in dict(factor_overrides.get("idiosyncratic_shocks") or {}).items():
                idio_shocks[str(symbol).upper()] += float(value or 0.0)
        if "propagation_lambda" in factor_overrides:
            lambda_value = float(factor_overrides.get("propagation_lambda") or lambda_value)

    return FactorShockVector(
        market_shock=clip_shock_pct(market_shock),
        sector_shocks={key: clip_shock_pct(value) for key, value in sector_shocks.items()},
        rate_shock=clip_shock_pct(rate_shock),
        fx_shock=clip_shock_pct(fx_shock),
        commodity_shock=clip_shock_pct(commodity_shock),
        idiosyncratic_shocks={key: clip_shock_pct(value) for key, value in idio_shocks.items()},
        propagation_lambda=max(0.0, min(1.0, float(lambda_value))),
    )


def _factor_vector_rule_labels(vector: FactorShockVector) -> list[str]:
    parts = [
        f"Factor market {vector.market_shock * 100:+.1f}%",
        f"rate {vector.rate_shock * 100:+.1f}%",
        f"fx {vector.fx_shock * 100:+.1f}%",
        f"commodity {vector.commodity_shock * 100:+.1f}%",
    ]
    if vector.sector_shocks:
        labels = ",".join(f"{key}:{value * 100:+.1f}%" for key, value in list(vector.sector_shocks.items())[:4])
        parts.append(f"sector[{labels}]")
    parts.append(f"propagation λ={vector.propagation_lambda:.2f}")
    return ["; ".join(parts), "传播后冲击 = 直接冲击 + λ × 相关矩阵 × 直接冲击向量"]


def _evaluate_scenario_from_shock_map(
    *,
    code: str,
    name: str,
    description: str,
    rules: list[str],
    snapshots: list[HoldingSnapshot],
    shock_map: dict[str, float],
    total_value: float,
    position_limit: int,
) -> dict[str, object]:
    impacted_value = 0.0
    weighted_shock = 0.0
    portfolio_change = 0.0
    affected_positions: list[dict[str, object]] = []
    sector_changes: dict[str, float] = defaultdict(float)
    sector_values: dict[str, float] = defaultdict(float)
    market_changes: dict[str, float] = defaultdict(float)
    market_values: dict[str, float] = defaultdict(float)

    for snapshot in snapshots:
        shock_pct = float(shock_map.get(snapshot.symbol) or 0.0)
        projected_value = snapshot.current_value * (1.0 + shock_pct)
        value_change = projected_value - snapshot.current_value
        portfolio_change += value_change
        if abs(shock_pct) < 1e-9:
            continue
        impacted_value += snapshot.current_value
        weighted_shock += snapshot.current_value * shock_pct
        sector_key = snapshot.sector or "未分类"
        market_key = snapshot.market or "UNKNOWN"
        sector_changes[sector_key] += value_change
        sector_values[sector_key] += snapshot.current_value
        market_changes[market_key] += value_change
        market_values[market_key] += snapshot.current_value
        affected_positions.append(
            {
                "symbol": snapshot.symbol,
                "name": snapshot.name,
                "market": snapshot.market,
                "sector": snapshot.sector,
                "current_price": snapshot.current_price,
                "current_value": snapshot.current_value,
                "weight": snapshot.weight,
                "shock_pct": shock_pct,
                "projected_value": projected_value,
                "value_change": value_change,
            }
        )

    affected_positions.sort(key=lambda item: abs(float(item["value_change"])), reverse=True)
    projected_value = total_value + portfolio_change
    average_shock_pct = (weighted_shock / impacted_value) if impacted_value else None
    return {
        "code": code,
        "name": name,
        "description": description,
        "rules": list(rules),
        "projected_value": projected_value,
        "portfolio_change": portfolio_change,
        "portfolio_change_pct": (portfolio_change / total_value) if total_value else 0.0,
        "loss_amount": max(-portfolio_change, 0.0),
        "loss_pct": (max(-portfolio_change, 0.0) / total_value) if total_value else 0.0,
        "impacted_value": impacted_value,
        "impacted_weight": (impacted_value / total_value) if total_value else 0.0,
        "average_shock_pct": average_shock_pct,
        "affected_positions": affected_positions[: max(1, position_limit)],
        "sector_impacts": _serialize_bucket_rows(sector_changes, sector_values, total_value),
        "market_impacts": _serialize_bucket_rows(market_changes, market_values, total_value),
    }


def evaluate_scenario(
    scenario: ScenarioDefinition,
    snapshots: list[HoldingSnapshot],
    *,
    total_value: float,
    position_limit: int,
) -> dict[str, object]:
    impacted_value = 0.0
    weighted_shock = 0.0
    portfolio_change = 0.0
    affected_positions: list[dict[str, object]] = []
    sector_changes: dict[str, float] = defaultdict(float)
    sector_values: dict[str, float] = defaultdict(float)
    market_changes: dict[str, float] = defaultdict(float)
    market_values: dict[str, float] = defaultdict(float)

    for snapshot in snapshots:
        shock_pct = float(scenario.shock_fn(snapshot))
        projected_value = snapshot.current_value * (1.0 + shock_pct)
        value_change = projected_value - snapshot.current_value
        portfolio_change += value_change
        if abs(shock_pct) < 1e-9:
            continue

        impacted_value += snapshot.current_value
        weighted_shock += snapshot.current_value * shock_pct
        sector_key = snapshot.sector or "未分类"
        market_key = snapshot.market or "UNKNOWN"
        sector_changes[sector_key] += value_change
        sector_values[sector_key] += snapshot.current_value
        market_changes[market_key] += value_change
        market_values[market_key] += snapshot.current_value
        affected_positions.append(
            {
                "symbol": snapshot.symbol,
                "name": snapshot.name,
                "market": snapshot.market,
                "sector": snapshot.sector,
                "current_price": snapshot.current_price,
                "current_value": snapshot.current_value,
                "weight": snapshot.weight,
                "shock_pct": shock_pct,
                "projected_value": projected_value,
                "value_change": value_change,
            }
        )

    affected_positions.sort(key=lambda item: abs(float(item["value_change"])), reverse=True)
    projected_value = total_value + portfolio_change
    average_shock_pct = (weighted_shock / impacted_value) if impacted_value else None
    return {
        "code": scenario.code,
        "name": scenario.name,
        "description": scenario.description,
        "rules": list(scenario.rules),
        "projected_value": projected_value,
        "portfolio_change": portfolio_change,
        "portfolio_change_pct": (portfolio_change / total_value) if total_value else 0.0,
        "loss_amount": max(-portfolio_change, 0.0),
        "loss_pct": (max(-portfolio_change, 0.0) / total_value) if total_value else 0.0,
        "impacted_value": impacted_value,
        "impacted_weight": (impacted_value / total_value) if total_value else 0.0,
        "average_shock_pct": average_shock_pct,
        "affected_positions": affected_positions[: max(1, position_limit)],
        "sector_impacts": _serialize_bucket_rows(sector_changes, sector_values, total_value),
        "market_impacts": _serialize_bucket_rows(market_changes, market_values, total_value),
    }


def _evaluate_custom_stress_scenario(
    db: Session,
    snapshots: list[HoldingSnapshot],
    *,
    total_value: float,
    code: str,
    name: str,
    description: str,
    rules: list[PortfolioStressRuleIn],
    factor_overrides: dict[str, object] | None = None,
    propagation_lambda: float | None = None,
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> dict[str, object]:
    legacy_scenario = ScenarioDefinition(
        code=code,
        name=str(name).strip(),
        description=str(description or "").strip(),
        rules=tuple(custom_rule_label(rule) for rule in rules),
        shock_fn=build_custom_shock_function(rules),
    )
    if not snapshots:
        return evaluate_scenario(
            legacy_scenario,
            snapshots,
            total_value=total_value,
            position_limit=max(1, int(position_limit)),
        )

    exposures, correlation = _estimate_latest_factor_exposures(db, snapshots)
    if not exposures:
        return evaluate_scenario(
            legacy_scenario,
            snapshots,
            total_value=total_value,
            position_limit=max(1, int(position_limit)),
        )

    factor_vector = _build_factor_shock_vector(
        rules,
        factor_overrides=factor_overrides,
        propagation_lambda=propagation_lambda,
    )
    legacy_fn = legacy_scenario.shock_fn
    direct_shocks: dict[str, float] = {}
    for snapshot in snapshots:
        exposure = exposures.get(snapshot.symbol)
        if exposure is None:
            direct_shocks[snapshot.symbol] = clip_shock_pct(float(legacy_fn(snapshot)))
            continue
        sector_shock = float(factor_vector.sector_shocks.get(snapshot.sector) or 0.0)
        direct = (
            exposure.market_beta * factor_vector.market_shock
            + exposure.sector_beta * sector_shock
            + exposure.rate_beta * factor_vector.rate_shock
            + exposure.fx_beta * factor_vector.fx_shock
            + exposure.commodity_beta * factor_vector.commodity_shock
            + exposure.idiosyncratic_term
            + float(factor_vector.idiosyncratic_shocks.get(snapshot.symbol.upper()) or 0.0)
        )
        direct_shocks[snapshot.symbol] = clip_shock_pct(direct)

    propagated_shocks: dict[str, float] = {}
    for snapshot in snapshots:
        symbol = snapshot.symbol
        base = float(direct_shocks.get(symbol) or 0.0)
        spillover = 0.0
        corr_row = correlation.get(symbol, {})
        for peer in snapshots:
            if peer.symbol == symbol:
                continue
            spillover += float(corr_row.get(peer.symbol) or 0.0) * float(direct_shocks.get(peer.symbol) or 0.0)
        propagated_shocks[symbol] = clip_shock_pct(base + factor_vector.propagation_lambda * spillover)

    labels = [custom_rule_label(rule) for rule in rules] + _factor_vector_rule_labels(factor_vector)
    return _evaluate_scenario_from_shock_map(
        code=legacy_scenario.code,
        name=legacy_scenario.name,
        description=legacy_scenario.description,
        rules=labels,
        snapshots=snapshots,
        shock_map=propagated_shocks,
        total_value=total_value,
        position_limit=max(1, int(position_limit)),
    )


def evaluate_custom_bought_target_stress_scenario(
    db: Session,
    user_id: int,
    *,
    code: str,
    name: str,
    description: str,
    rules: list[PortfolioStressRuleIn],
    factor_overrides: dict[str, object] | None = None,
    propagation_lambda: float | None = None,
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> dict[str, object]:
    snapshots, total_value, _, _ = load_bought_target_snapshots(db, user_id)
    return _evaluate_custom_stress_scenario(
        db,
        snapshots,
        total_value=total_value,
        code=code,
        name=name,
        description=description,
        rules=rules,
        factor_overrides=factor_overrides,
        propagation_lambda=propagation_lambda,
        position_limit=position_limit,
    )


def evaluate_custom_watch_target_stress_scenario(
    db: Session,
    user_id: int,
    *,
    code: str,
    name: str,
    description: str,
    rules: list[PortfolioStressRuleIn],
    factor_overrides: dict[str, object] | None = None,
    propagation_lambda: float | None = None,
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> dict[str, object]:
    snapshots, total_value, _, _ = load_watch_target_snapshots(db, user_id)
    return _evaluate_custom_stress_scenario(
        db,
        snapshots,
        total_value=total_value,
        code=code,
        name=name,
        description=description,
        rules=rules,
        factor_overrides=factor_overrides,
        propagation_lambda=propagation_lambda,
        position_limit=position_limit,
    )


def _build_portfolio_stress_payload(
    snapshots: list[HoldingSnapshot],
    *,
    total_value: float,
    as_of,
    position_limit: int,
) -> PortfolioStressOut:
    scenarios = [
        evaluate_scenario(
            scenario,
            snapshots,
            total_value=total_value,
            position_limit=position_limit,
        )
        for scenario in SCENARIOS
    ]
    worst = max(scenarios, key=lambda item: float(item.get("loss_amount") or 0.0), default=None)
    return PortfolioStressOut(
        summary={
            "as_of": as_of,
            "holdings_count": len(snapshots),
            "total_value": total_value,
            "scenario_count": len(scenarios),
            "worst_scenario_code": str(worst.get("code")) if worst else None,
            "worst_scenario_name": str(worst.get("name")) if worst else None,
            "worst_loss_amount": float(worst.get("loss_amount") or 0.0) if worst else 0.0,
            "worst_loss_pct": float(worst.get("loss_pct") or 0.0) if worst else 0.0,
            "max_impacted_weight": max((float(item.get("impacted_weight") or 0.0) for item in scenarios), default=0.0),
        },
        scenarios=scenarios,
    )


def _get_portfolio_stress_test(
    db: Session,
    user_id: int,
    *,
    cache_scope: str,
    snapshot_loader,
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> PortfolioStressOut:
    cache_key = build_cache_key(
        cache_scope,
        user_id=user_id,
        position_limit=position_limit,
        version=PORTFOLIO_STRESS_CACHE_VERSION,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict):
        try:
            return PortfolioStressOut(**cached)
        except Exception:
            pass

    snapshots, total_value, _, as_of = snapshot_loader(db, user_id)
    payload = _build_portfolio_stress_payload(
        snapshots,
        total_value=total_value,
        as_of=as_of,
        position_limit=position_limit,
    )
    set_json(cache_key, payload.model_dump(mode="json"), ttl=PORTFOLIO_STRESS_CACHE_TTL)
    return payload


def get_bought_target_stress_test(
    db: Session,
    user_id: int,
    *,
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> PortfolioStressOut:
    return _get_portfolio_stress_test(
        db,
        user_id,
        cache_scope="user:bought-targets:stress-test",
        snapshot_loader=load_bought_target_snapshots,
        position_limit=position_limit,
    )


def get_watch_target_stress_test(
    db: Session,
    user_id: int,
    *,
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> PortfolioStressOut:
    return _get_portfolio_stress_test(
        db,
        user_id,
        cache_scope="user:watch-targets:stress-test",
        snapshot_loader=load_watch_target_snapshots,
        position_limit=position_limit,
    )


def preview_custom_bought_target_stress_test(
    db: Session,
    user_id: int,
    payload: PortfolioStressPreviewIn,
) -> dict[str, object]:
    return evaluate_custom_bought_target_stress_scenario(
        db,
        user_id,
        code="custom_preview",
        name=str(payload.name).strip(),
        description=str(payload.description or "").strip() or "用户自定义压力场景预览",
        rules=list(payload.rules),
        position_limit=int(payload.position_limit),
    )


def preview_custom_watch_target_stress_test(
    db: Session,
    user_id: int,
    payload: PortfolioStressPreviewIn,
) -> dict[str, object]:
    return evaluate_custom_watch_target_stress_scenario(
        db,
        user_id,
        code="custom_preview",
        name=str(payload.name).strip(),
        description=str(payload.description or "").strip() or "用户自定义压力场景预览",
        rules=list(payload.rules),
        position_limit=int(payload.position_limit),
    )
