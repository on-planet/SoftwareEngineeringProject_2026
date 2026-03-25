from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable

_CONFIGURED_VENDOR_PATH = str(os.getenv("AUTOGLUON_VENDOR_PATH") or "").strip()
_DEFAULT_VENDOR_PATH = Path(__file__).resolve().parents[3] / ".vendor" / "autogluon"
_BOOTSTRAP_VENDOR_PATH = Path(_CONFIGURED_VENDOR_PATH) if _CONFIGURED_VENDOR_PATH else _DEFAULT_VENDOR_PATH
if _BOOTSTRAP_VENDOR_PATH.exists() and str(_BOOTSTRAP_VENDOR_PATH) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_VENDOR_PATH))

import numpy as np
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.buyback import Buyback
from app.models.daily_prices import DailyPrice
from app.models.events import Event
from app.models.financials import Financial
from app.models.stock_live_snapshot import StockLiveSnapshot
from app.models.stock_research_item import StockResearchItem
from app.models.stock_strategy_run import StockStrategyRun
from app.models.stock_strategy_score import StockStrategyScore
from app.models.stocks import Stock
from app.utils.symbols import normalize_symbol

STRATEGY_CODE = "smoke_butt_autogluon"
STRATEGY_NAME = "AutoGluon Smoke Butt"
DEFAULT_HORIZON_DAYS = 60
DEFAULT_SAMPLE_STEP = 21
MIN_TRAIN_ROWS = 60
MODEL_FEATURE_COLUMNS = [
    "market",
    "sector",
    "ret_20d",
    "ret_60d",
    "ret_120d",
    "volatility_20d",
    "volatility_60d",
    "drawdown_120d",
    "rebound_from_low_120d",
    "volume_ratio_20d",
    "roe",
    "debt_ratio",
    "profit_quality",
    "revenue_growth",
    "net_income_growth",
    "cash_flow_margin",
    "financial_age_days",
    "event_count_90d",
    "research_count_180d",
    "buyback_count_180d",
]
TARGET_COLUMN = "future_return"
FEATURE_VALUE_LABELS = [
    ("expected_return", "模型预期收益"),
    ("pb", "PB"),
    ("pe_ttm", "PE(TTM)"),
    ("dividend_yield", "股息率"),
    ("ret_120d", "120日涨跌"),
    ("drawdown_120d", "120日回撤"),
    ("volatility_20d", "20日波动"),
    ("debt_ratio", "负债率"),
    ("profit_quality", "利润现金覆盖"),
    ("event_count_90d", "90日事件数"),
    ("buyback_count_180d", "180日回购数"),
    ("research_count_180d", "180日研报数"),
]
RATIO_PERCENT_COLUMNS = {
    "expected_return",
    "ret_20d",
    "ret_60d",
    "ret_120d",
    "drawdown_120d",
    "rebound_from_low_120d",
    "volatility_20d",
    "volatility_60d",
    "dividend_yield",
}
DIVIDEND_YIELD_COLUMN = "dividend_yield"
DIVIDEND_DRIVER_LABEL = "\u80a1\u606f\u7387\u8f83\u9ad8"
DIVIDEND_FEATURE_LABEL = next(label for key, label in FEATURE_VALUE_LABELS if key == DIVIDEND_YIELD_COLUMN)
_YYYYMM_RE = re.compile(r"^(?P<year>\d{4})(?P<month>\d{2})$")
_QUARTER_RE = re.compile(r"^(?P<year>\d{4})Q(?P<quarter>[1-4])$", re.IGNORECASE)
_DATE_RE = re.compile(r"^(?P<year>\d{4})[-/]?(?P<month>\d{2})(?:[-/]?(?P<day>\d{2}))?$")


class SmokeButtStrategyError(RuntimeError):
    pass


class AutoGluonUnavailableError(SmokeButtStrategyError):
    pass


class SmokeButtDataError(SmokeButtStrategyError):
    pass


@dataclass
class StrategyDataset:
    train_frame: pd.DataFrame
    score_frame: pd.DataFrame
    as_of: date


def _load_tabular_predictor():
    vendor_path = _autogluon_vendor_path()
    if vendor_path.exists() and str(vendor_path) not in sys.path:
        sys.path.insert(0, str(vendor_path))
    try:
        from autogluon.tabular import TabularPredictor
    except Exception as exc:  # pragma: no cover
        raise AutoGluonUnavailableError(
            "AutoGluon 未安装。请先执行 `python -m pip install -r requirements-autogluon.txt --target .vendor/autogluon`。"
        ) from exc
    return TabularPredictor


def _strategy_model_root() -> Path:
    configured = str(os.getenv("AUTOGLUON_STRATEGY_ROOT") or "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "etl" / "state" / "autogluon"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _autogluon_vendor_path() -> Path:
    return _BOOTSTRAP_VENDOR_PATH


def _safe_read_sql(query, bind, columns: list[str]) -> pd.DataFrame:
    try:
        frame = pd.read_sql(query.statement, bind)
    except SQLAlchemyError:
        return pd.DataFrame(columns=columns)
    if frame.empty:
        return pd.DataFrame(columns=columns)
    return frame


def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, month, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _parse_period_end(raw: Any) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    match = _YYYYMM_RE.match(text)
    if match:
        year = int(match.group("year"))
        month = int(match.group("month"))
        if 1 <= month <= 12:
            return _last_day_of_month(year, month)
    match = _QUARTER_RE.match(text)
    if match:
        year = int(match.group("year"))
        month = int(match.group("quarter")) * 3
        return _last_day_of_month(year, month)
    match = _DATE_RE.match(text)
    if match:
        year = int(match.group("year"))
        month = int(match.group("month"))
        day = int(match.group("day") or _last_day_of_month(year, month).day)
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom = denominator.astype("float64")
    return numerator.astype("float64") / denom.where(denom.abs() > 1e-9, np.nan)


def _clip_series(series: pd.Series, low: float, high: float) -> pd.Series:
    return series.astype("float64").clip(lower=low, upper=high)


def _prepare_price_frame(price_frame: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    if price_frame.empty:
        return price_frame

    frame = price_frame.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame.sort_values(["symbol", "date"], inplace=True)
    grouped = frame.groupby("symbol", sort=False)
    close_group = grouped["close"]
    high_group = grouped["high"]
    low_group = grouped["low"]
    volume_group = grouped["volume"]

    frame["daily_return"] = close_group.pct_change()
    frame["ret_20d"] = close_group.pct_change(20)
    frame["ret_60d"] = close_group.pct_change(60)
    frame["ret_120d"] = close_group.pct_change(120)
    frame["future_return"] = (close_group.shift(-horizon_days) / frame["close"]) - 1.0
    frame["future_return"] = _clip_series(frame["future_return"], -0.75, 1.5)
    frame["volatility_20d"] = (
        grouped["daily_return"].rolling(20).std().reset_index(level=0, drop=True) * math.sqrt(20.0)
    )
    frame["volatility_60d"] = (
        grouped["daily_return"].rolling(60).std().reset_index(level=0, drop=True) * math.sqrt(60.0)
    )
    rolling_high_120 = high_group.rolling(120).max().reset_index(level=0, drop=True)
    rolling_low_120 = low_group.rolling(120).min().reset_index(level=0, drop=True)
    volume_mean_20 = volume_group.rolling(20).mean().reset_index(level=0, drop=True)
    frame["drawdown_120d"] = (frame["close"] / rolling_high_120) - 1.0
    frame["rebound_from_low_120d"] = (frame["close"] / rolling_low_120) - 1.0
    frame["volume_ratio_20d"] = frame["volume"] / volume_mean_20.replace(0.0, np.nan)
    frame["sample_index"] = grouped.cumcount()
    return frame


def _prepare_financial_frame(financial_frame: pd.DataFrame) -> pd.DataFrame:
    if financial_frame.empty:
        return financial_frame

    frame = financial_frame.copy()
    frame["period_end"] = frame["period"].map(_parse_period_end)
    frame = frame[frame["period_end"].notna()].copy()
    if frame.empty:
        return frame
    frame["period_end"] = pd.to_datetime(frame["period_end"])
    frame.sort_values(["symbol", "period_end"], inplace=True)
    grouped = frame.groupby("symbol", sort=False)
    previous_revenue = grouped["revenue"].shift(1)
    previous_income = grouped["net_income"].shift(1)
    frame["revenue_growth"] = _clip_series(_safe_ratio(frame["revenue"] - previous_revenue, previous_revenue), -3.0, 3.0)
    frame["net_income_growth"] = _clip_series(
        _safe_ratio(frame["net_income"] - previous_income, previous_income.abs()),
        -3.0,
        3.0,
    )
    frame["profit_quality"] = _clip_series(_safe_ratio(frame["cash_flow"], frame["net_income"].abs()), -5.0, 5.0)
    frame["cash_flow_margin"] = _clip_series(_safe_ratio(frame["cash_flow"], frame["revenue"].abs()), -5.0, 5.0)
    return frame


def _merge_financial_features(base_frame: pd.DataFrame, financial_frame: pd.DataFrame) -> pd.DataFrame:
    frame = base_frame.copy()
    if frame.empty:
        return frame
    if financial_frame.empty:
        for column in (
            "roe",
            "debt_ratio",
            "profit_quality",
            "revenue_growth",
            "net_income_growth",
            "cash_flow_margin",
            "financial_age_days",
            "financial_period",
        ):
            frame[column] = np.nan
        return frame

    left = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
    right = financial_frame[
        [
            "symbol",
            "period",
            "period_end",
            "roe",
            "debt_ratio",
            "profit_quality",
            "revenue_growth",
            "net_income_growth",
            "cash_flow_margin",
        ]
    ].sort_values(["symbol", "period_end"]).reset_index(drop=True)
    merged_groups: list[pd.DataFrame] = []
    for symbol, left_group in left.groupby("symbol", sort=False):
        right_group = right[right["symbol"] == symbol].copy()
        if right_group.empty:
            empty_group = left_group.copy()
            empty_group["period"] = np.nan
            empty_group["period_end"] = pd.NaT
            empty_group["roe"] = np.nan
            empty_group["debt_ratio"] = np.nan
            empty_group["profit_quality"] = np.nan
            empty_group["revenue_growth"] = np.nan
            empty_group["net_income_growth"] = np.nan
            empty_group["cash_flow_margin"] = np.nan
            merged_groups.append(empty_group)
            continue
        merged_group = pd.merge_asof(
            left_group.sort_values("date"),
            right_group.sort_values("period_end"),
            left_on="date",
            right_on="period_end",
            direction="backward",
        )
        if "symbol_x" in merged_group.columns:
            merged_group["symbol"] = merged_group["symbol_x"]
            merged_group.drop(columns=["symbol_x", "symbol_y"], inplace=True, errors="ignore")
        merged_groups.append(merged_group)
    merged = pd.concat(merged_groups, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    merged["financial_period"] = merged["period"]
    merged["financial_age_days"] = (merged["date"] - merged["period_end"]).dt.days
    merged.drop(columns=["period", "period_end"], inplace=True, errors="ignore")
    return merged


def _build_date_lookup(records: pd.DataFrame, date_column: str) -> dict[str, np.ndarray]:
    if records.empty:
        return {}
    frame = records.copy()
    frame[date_column] = pd.to_datetime(frame[date_column]).dt.normalize()
    frame.sort_values(["symbol", date_column], inplace=True)
    result: dict[str, np.ndarray] = {}
    for symbol, group in frame.groupby("symbol", sort=False):
        result[str(symbol)] = group[date_column].to_numpy(dtype="datetime64[D]")
    return result


def _attach_window_count(
    base_frame: pd.DataFrame,
    lookup: dict[str, np.ndarray],
    *,
    window_days: int,
    output_column: str,
) -> pd.DataFrame:
    frame = base_frame.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    frame[output_column] = 0
    if frame.empty or not lookup:
        return frame

    values = np.zeros(len(frame), dtype="int64")
    for symbol, positions in frame.groupby("symbol", sort=False).groups.items():
        record_dates = lookup.get(str(symbol))
        if record_dates is None or len(record_dates) == 0:
            continue
        index_list = list(positions)
        anchor_dates = frame.loc[index_list, "date"].to_numpy(dtype="datetime64[D]")
        left_edges = anchor_dates - np.timedelta64(window_days, "D")
        left = np.searchsorted(record_dates, left_edges, side="left")
        right = np.searchsorted(record_dates, anchor_dates, side="right")
        values[index_list] = right - left
    frame[output_column] = values
    return frame


def _load_base_frames(db: Session, as_of: date) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bind = db.get_bind()
    if bind is None:
        raise SmokeButtDataError("数据库连接不可用，无法构建 AutoGluon 训练集。")

    price_frame = _safe_read_sql(
        db.query(
            DailyPrice.symbol,
            DailyPrice.date,
            DailyPrice.open,
            DailyPrice.high,
            DailyPrice.low,
            DailyPrice.close,
            DailyPrice.volume,
        ).filter(DailyPrice.date <= as_of).order_by(DailyPrice.symbol.asc(), DailyPrice.date.asc()),
        bind,
        ["symbol", "date", "open", "high", "low", "close", "volume"],
    )
    stock_frame = _safe_read_sql(
        db.query(Stock.symbol, Stock.name, Stock.market, Stock.sector).order_by(Stock.symbol.asc()),
        bind,
        ["symbol", "name", "market", "sector"],
    )
    financial_frame = _safe_read_sql(
        db.query(
            Financial.symbol,
            Financial.period,
            Financial.revenue,
            Financial.net_income,
            Financial.cash_flow,
            Financial.roe,
            Financial.debt_ratio,
        ).order_by(Financial.symbol.asc(), Financial.period.asc()),
        bind,
        ["symbol", "period", "revenue", "net_income", "cash_flow", "roe", "debt_ratio"],
    )
    event_frame = _safe_read_sql(
        db.query(Event.symbol, Event.date).filter(Event.date <= as_of).order_by(Event.symbol.asc(), Event.date.asc()),
        bind,
        ["symbol", "date"],
    )
    buyback_frame = _safe_read_sql(
        db.query(Buyback.symbol, Buyback.date).filter(Buyback.date <= as_of).order_by(Buyback.symbol.asc(), Buyback.date.asc()),
        bind,
        ["symbol", "date"],
    )
    research_frame = _safe_read_sql(
        db.query(StockResearchItem.symbol, StockResearchItem.published_at)
        .filter(StockResearchItem.published_at.isnot(None), StockResearchItem.published_at <= datetime.combine(as_of, datetime.max.time()))
        .order_by(StockResearchItem.symbol.asc(), StockResearchItem.published_at.asc()),
        bind,
        ["symbol", "published_at"],
    )
    return price_frame, stock_frame, financial_frame, event_frame, buyback_frame, research_frame


def _load_live_snapshot_frame(db: Session) -> pd.DataFrame:
    bind = db.get_bind()
    if bind is None:
        return pd.DataFrame(columns=["symbol", "pe_ttm", "pb", "dividend_yield", "market_cap", "float_market_cap"])
    return _safe_read_sql(
        db.query(
            StockLiveSnapshot.symbol,
            StockLiveSnapshot.pe_ttm,
            StockLiveSnapshot.pb,
            StockLiveSnapshot.dividend_yield,
            StockLiveSnapshot.market_cap,
            StockLiveSnapshot.float_market_cap,
        ).order_by(StockLiveSnapshot.symbol.asc()),
        bind,
        ["symbol", "pe_ttm", "pb", "dividend_yield", "market_cap", "float_market_cap"],
    )


def _build_dataset(
    db: Session,
    *,
    as_of: date,
    horizon_days: int,
    sample_step: int,
) -> StrategyDataset:
    price_frame, stock_frame, financial_frame, event_frame, buyback_frame, research_frame = _load_base_frames(db, as_of)
    if price_frame.empty:
        raise SmokeButtDataError("daily_prices 为空，无法训练烟蒂股策略。")

    features = _prepare_price_frame(price_frame, horizon_days)
    features = _merge_financial_features(features, _prepare_financial_frame(financial_frame))
    features = _attach_window_count(features, _build_date_lookup(event_frame, "date"), window_days=90, output_column="event_count_90d")
    features = _attach_window_count(features, _build_date_lookup(research_frame, "published_at"), window_days=180, output_column="research_count_180d")
    features = _attach_window_count(features, _build_date_lookup(buyback_frame, "date"), window_days=180, output_column="buyback_count_180d")

    if not stock_frame.empty:
        features = features.merge(stock_frame, on="symbol", how="left")
    else:
        features["name"] = features["symbol"]
        features["market"] = "A"
        features["sector"] = "Unknown"

    features["name"] = features["name"].fillna(features["symbol"])
    features["market"] = features["market"].fillna("A")
    features["sector"] = features["sector"].fillna("Unknown")

    feature_ready_mask = features["ret_120d"].notna() & features["volatility_20d"].notna() & features["drawdown_120d"].notna()
    train_frame = features[feature_ready_mask & features[TARGET_COLUMN].notna()].copy()
    train_frame = train_frame[(train_frame["sample_index"] % max(sample_step, 1)) == 0].copy()
    if train_frame.empty or len(train_frame) < MIN_TRAIN_ROWS:
        raise SmokeButtDataError(f"训练样本不足，当前仅有 {len(train_frame)} 条。")

    score_frame = features[feature_ready_mask].copy()
    score_frame = score_frame.sort_values(["symbol", "date"]).groupby("symbol", sort=False).tail(1).copy()
    if score_frame.empty:
        raise SmokeButtDataError("当前候选池为空，无法输出策略评分。")

    live_snapshot_frame = _load_live_snapshot_frame(db)
    if not live_snapshot_frame.empty:
        score_frame = score_frame.merge(live_snapshot_frame, on="symbol", how="left")
    else:
        for column in ("pe_ttm", "pb", "dividend_yield", "market_cap", "float_market_cap"):
            score_frame[column] = np.nan

    train_frame["date"] = pd.to_datetime(train_frame["date"])
    score_frame["date"] = pd.to_datetime(score_frame["date"])
    return StrategyDataset(train_frame=train_frame.reset_index(drop=True), score_frame=score_frame.reset_index(drop=True), as_of=as_of)


def _split_train_validation(train_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    if train_frame.empty:
        return train_frame, None
    ordered_dates = sorted(pd.to_datetime(train_frame["date"]).dt.normalize().unique())
    if len(ordered_dates) < 6:
        return train_frame, None
    cutoff_index = max(1, int(len(ordered_dates) * 0.8))
    cutoff = ordered_dates[min(cutoff_index, len(ordered_dates) - 1)]
    validation = train_frame[pd.to_datetime(train_frame["date"]).dt.normalize() >= cutoff].copy()
    training = train_frame[pd.to_datetime(train_frame["date"]).dt.normalize() < cutoff].copy()
    if len(training) < MIN_TRAIN_ROWS or len(validation) < 20:
        return train_frame, None
    return training, validation


def _serialize_json(payload: Any, fallback: str) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        return fallback


def _load_json_object(raw: str | None, default: dict[str, Any] | None = None) -> dict[str, Any]:
    fallback = default or {}
    if not raw:
        return dict(fallback)
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return dict(fallback)
    return payload if isinstance(payload, dict) else dict(fallback)


def _load_json_list(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _normalize_percent_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) > 1.0:
        return value / 100.0
    return value


def _normalize_metric_value(name: str, value: float | None) -> float | None:
    if name == DIVIDEND_YIELD_COLUMN:
        return _normalize_percent_ratio(value)
    return value


def _metric_display(name: str, value: float | None) -> str | None:
    normalized = _normalize_metric_value(name, value)
    if normalized is None:
        return None
    if name in RATIO_PERCENT_COLUMNS:
        return f"{normalized * 100:.2f}%"
    if abs(normalized) >= 1000:
        return f"{normalized:,.0f}"
    return f"{normalized:.2f}"


def _build_driver_factors(row: pd.Series) -> list[dict[str, Any]]:
    drivers: list[dict[str, Any]] = []
    expected_return = _safe_float(row.get("expected_return"))
    if expected_return is not None:
        tone = "positive" if expected_return >= 0 else "negative"
        drivers.append(
            {
                "label": "模型回报预期",
                "tone": tone,
                "value": expected_return,
                "display_value": _metric_display("expected_return", expected_return),
            }
        )

    pb = _safe_float(row.get("pb"))
    if pb is not None and pb <= 1.2:
        drivers.append({"label": "低 PB 估值", "tone": "positive", "value": pb, "display_value": f"{pb:.2f}"})
    dividend_yield = _normalize_metric_value(DIVIDEND_YIELD_COLUMN, _safe_float(row.get(DIVIDEND_YIELD_COLUMN)))
    if dividend_yield is not None and dividend_yield >= 0.03:
        drivers.append(
            {
                "label": "股息率较高",
                "tone": "positive",
                "value": dividend_yield,
                "display_value": _metric_display(DIVIDEND_YIELD_COLUMN, dividend_yield),
            }
        )
    drawdown = _safe_float(row.get("drawdown_120d"))
    if drawdown is not None and drawdown <= -0.2:
        drivers.append(
            {
                "label": "过去一年大幅回撤",
                "tone": "positive",
                "value": drawdown,
                "display_value": _metric_display("drawdown_120d", drawdown),
            }
        )
    debt_ratio = _safe_float(row.get("debt_ratio"))
    if debt_ratio is not None and debt_ratio <= 0.5:
        drivers.append({"label": "杠杆压力偏低", "tone": "positive", "value": debt_ratio, "display_value": f"{debt_ratio:.2f}"})
    elif debt_ratio is not None and debt_ratio >= 0.8:
        drivers.append({"label": "负债率偏高", "tone": "negative", "value": debt_ratio, "display_value": f"{debt_ratio:.2f}"})
    profit_quality = _safe_float(row.get("profit_quality"))
    if profit_quality is not None and profit_quality >= 1.0:
        drivers.append(
            {"label": "现金流覆盖利润", "tone": "positive", "value": profit_quality, "display_value": f"{profit_quality:.2f}"}
        )
    elif profit_quality is not None and profit_quality < 0.6:
        drivers.append(
            {"label": "利润现金转化偏弱", "tone": "negative", "value": profit_quality, "display_value": f"{profit_quality:.2f}"}
        )
    buyback_count = _safe_float(row.get("buyback_count_180d"))
    if buyback_count is not None and buyback_count > 0:
        drivers.append(
            {
                "label": "近期存在回购催化",
                "tone": "positive",
                "value": buyback_count,
                "display_value": f"{int(buyback_count)} 次",
            }
        )
    volatility = _safe_float(row.get("volatility_20d"))
    if volatility is not None and volatility >= 0.12:
        drivers.append(
            {
                "label": "短期波动偏高",
                "tone": "negative",
                "value": volatility,
                "display_value": _metric_display("volatility_20d", volatility),
            }
        )
    if not drivers:
        drivers.append({"label": "等待更多结构化数据", "tone": "neutral", "value": None, "display_value": None})
    return drivers[:4]


def _build_feature_values(row: pd.Series) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, label in FEATURE_VALUE_LABELS:
        value = _safe_float(row.get(key))
        if value is None:
            continue
        normalized = _normalize_metric_value(key, value)
        items.append({"name": label, "value": normalized, "display_value": _metric_display(key, normalized)})
    return items


def _sanitize_driver_factor(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    if str(normalized.get("label") or "").strip() != DIVIDEND_DRIVER_LABEL:
        return normalized
    value = _normalize_metric_value(DIVIDEND_YIELD_COLUMN, _safe_float(normalized.get("value")))
    normalized["value"] = value
    normalized["display_value"] = _metric_display(DIVIDEND_YIELD_COLUMN, value)
    return normalized


def _sanitize_feature_value(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    if str(normalized.get("name") or "").strip() != DIVIDEND_FEATURE_LABEL:
        return normalized
    value = _normalize_metric_value(DIVIDEND_YIELD_COLUMN, _safe_float(normalized.get("value")))
    normalized["value"] = value
    normalized["display_value"] = _metric_display(DIVIDEND_YIELD_COLUMN, value)
    return normalized


def _build_summary(
    *,
    expected_return: float | None,
    rank: int,
    total: int,
    drivers: Iterable[dict[str, Any]],
    horizon_days: int,
) -> str:
    parts = [f"AutoGluon 预计未来 {horizon_days} 个交易日回报"]
    if expected_return is None:
        parts.append("暂缺。")
    else:
        parts.append(f"{expected_return * 100:.2f}%，当前排名第 {rank}/{total}。")
    labels = [str(item.get("label") or "").strip() for item in drivers if str(item.get("label") or "").strip()]
    if labels:
        parts.append(f"主要驱动：{'、'.join(labels[:3])}。")
    return "".join(parts)


def _signal_from_percentile(percentile: float) -> str:
    if percentile >= 0.9:
        return "strong_buy"
    if percentile >= 0.75:
        return "buy"
    if percentile >= 0.5:
        return "watch"
    return "avoid"


def _serialize_run(run: StockStrategyRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "strategy_code": run.strategy_code,
        "strategy_name": run.strategy_name,
        "as_of": run.as_of,
        "label_horizon": run.label_horizon,
        "status": run.status,
        "model_path": run.model_path,
        "train_rows": int(run.train_rows or 0),
        "scored_rows": int(run.scored_rows or 0),
        "trained_at": run.updated_at or run.created_at,
        "evaluation": _load_json_object(run.evaluation_json),
        "leaderboard": _load_json_list(run.leaderboard_json),
        "feature_importance": _load_json_list(run.feature_importance_json),
    }


def _serialize_score_row(run: StockStrategyRun, score: StockStrategyScore, stock: Stock | None) -> dict[str, Any]:
    stock_name = stock.name if stock and stock.name else score.symbol
    market = stock.market if stock and stock.market else "A"
    sector = stock.sector if stock and stock.sector else "Unknown"
    drivers = [_sanitize_driver_factor(item) for item in _load_json_list(score.driver_factors_json)]
    feature_values = [_sanitize_feature_value(item) for item in _load_json_list(score.feature_values_json)]
    return {
        "symbol": score.symbol,
        "name": stock_name,
        "market": market,
        "sector": sector,
        "as_of": score.as_of,
        "score": float(score.score or 0.0),
        "rank": int(score.rank or 0),
        "percentile": float(score.percentile or 0.0),
        "expected_return": _safe_float(score.expected_return),
        "signal": score.signal or "watch",
        "summary": score.summary,
        "run": _serialize_run(run),
        "drivers": drivers,
        "feature_values": feature_values,
    }


def _validation_metrics(labels: pd.Series, predictions: pd.Series) -> dict[str, float]:
    if labels.empty or predictions.empty:
        return {}
    label_values = labels.astype("float64")
    pred_values = predictions.astype("float64")
    mae = float(np.mean(np.abs(pred_values - label_values)))
    rmse = float(np.sqrt(np.mean(np.square(pred_values - label_values))))
    rank_ic = float(pred_values.corr(label_values, method="spearman"))
    return {"mae": mae, "rmse": rmse, "rank_ic": rank_ic}


def _serialize_importance_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    output: list[dict[str, Any]] = []
    normalized = frame.reset_index().rename(columns={"index": "feature"})
    for row in normalized.to_dict("records"):
        output.append(
            {
                "feature": str(row.get("feature") or ""),
                "importance": _safe_float(row.get("importance")),
                "stddev": _safe_float(row.get("stddev")),
                "p_value": _safe_float(row.get("p_value")),
                "n": int(row.get("n")) if row.get("n") is not None else None,
            }
        )
    output.sort(key=lambda item: abs(item.get("importance") or 0.0), reverse=True)
    return output[:10]


def _serialize_leaderboard_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    output: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        output.append(
            {
                "model": str(row.get("model") or ""),
                "score_val": _safe_float(row.get("score_val")),
                "fit_time": _safe_float(row.get("fit_time")),
                "pred_time_val": _safe_float(row.get("pred_time_val")),
            }
        )
    return output[:10]


def _find_existing_run(db: Session, *, as_of: date, horizon_days: int) -> StockStrategyRun | None:
    return (
        db.query(StockStrategyRun)
        .filter(
            StockStrategyRun.strategy_code == STRATEGY_CODE,
            StockStrategyRun.as_of == as_of,
            StockStrategyRun.label_horizon == horizon_days,
        )
        .order_by(StockStrategyRun.updated_at.desc(), StockStrategyRun.id.desc())
        .first()
    )


def get_latest_smoke_butt_run(db: Session) -> StockStrategyRun | None:
    return (
        db.query(StockStrategyRun)
        .filter(StockStrategyRun.strategy_code == STRATEGY_CODE)
        .order_by(StockStrategyRun.updated_at.desc(), StockStrategyRun.id.desc())
        .first()
    )


def train_smoke_butt_strategy(
    db: Session,
    *,
    as_of: date | None = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    sample_step: int = DEFAULT_SAMPLE_STEP,
    time_limit_seconds: int | None = 120,
    force_retrain: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target_date = as_of or date.today()
    existing = _find_existing_run(db, as_of=target_date, horizon_days=horizon_days)
    if existing is not None and not force_retrain:
        items, _, _ = list_smoke_butt_candidates(db, limit=10, offset=0, run=existing)
        return _serialize_run(existing), items

    dataset = _build_dataset(db, as_of=target_date, horizon_days=horizon_days, sample_step=sample_step)
    training_frame, validation_frame = _split_train_validation(dataset.train_frame)

    train_input = training_frame[MODEL_FEATURE_COLUMNS + [TARGET_COLUMN]].copy()
    validation_input = (
        validation_frame[MODEL_FEATURE_COLUMNS + [TARGET_COLUMN]].copy()
        if validation_frame is not None and not validation_frame.empty
        else None
    )

    predictor_cls = _load_tabular_predictor()
    model_root = _strategy_model_root()
    model_root.mkdir(parents=True, exist_ok=True)
    model_dir = model_root / f"{STRATEGY_CODE}_{target_date.isoformat()}_{_utcnow().strftime('%Y%m%d%H%M%S')}"

    predictor = predictor_cls(
        label=TARGET_COLUMN,
        path=str(model_dir),
        problem_type="regression",
        eval_metric="mean_absolute_error",
    )

    fit_kwargs: dict[str, Any] = {
        "train_data": train_input,
        "presets": str(os.getenv("AUTOGLUON_SMOKE_BUTT_PRESETS") or "medium_quality"),
        "hyperparameters": {"GBM": {}},
        "verbosity": 0,
    }
    if time_limit_seconds is not None:
        fit_kwargs["time_limit"] = int(time_limit_seconds)
    if validation_input is not None and not validation_input.empty:
        fit_kwargs["tuning_data"] = validation_input
    predictor.fit(**fit_kwargs)

    score_input = dataset.score_frame[MODEL_FEATURE_COLUMNS].copy()
    predictions = predictor.predict(score_input)
    scored_frame = dataset.score_frame.copy()
    scored_frame["expected_return"] = predictions.astype("float64")
    scored_frame.sort_values(["expected_return", "symbol"], ascending=[False, True], inplace=True)
    scored_frame.reset_index(drop=True, inplace=True)

    validation_metrics = {}
    if validation_input is not None and not validation_input.empty:
        val_predictions = predictor.predict(validation_input[MODEL_FEATURE_COLUMNS])
        validation_metrics = _validation_metrics(validation_input[TARGET_COLUMN], pd.Series(val_predictions))

    leaderboard_items: list[dict[str, Any]] = []
    try:
        leaderboard_frame = predictor.leaderboard(validation_input if validation_input is not None else train_input, silent=True)
        leaderboard_items = _serialize_leaderboard_frame(leaderboard_frame)
    except Exception:
        leaderboard_items = []

    importance_items: list[dict[str, Any]] = []
    try:
        importance_source = validation_input if validation_input is not None and len(validation_input) >= 32 else train_input.sample(
            n=min(len(train_input), 256),
            random_state=42,
        )
        importance_frame = predictor.feature_importance(importance_source, silent=True)
        importance_items = _serialize_importance_frame(importance_frame)
    except Exception:
        importance_items = []

    run = StockStrategyRun(
        strategy_code=STRATEGY_CODE,
        strategy_name=STRATEGY_NAME,
        as_of=target_date,
        label_horizon=horizon_days,
        status="ready",
        model_path=str(model_dir),
        train_rows=len(train_input),
        scored_rows=len(scored_frame),
        evaluation_json=_serialize_json(validation_metrics, "{}"),
        leaderboard_json=_serialize_json(leaderboard_items, "[]"),
        feature_importance_json=_serialize_json(importance_items, "[]"),
    )
    db.add(run)
    db.flush()

    total = len(scored_frame)
    score_rows: list[StockStrategyScore] = []
    for index, row in scored_frame.iterrows():
        rank = index + 1
        percentile = 1.0 if total <= 1 else 1.0 - (index / (total - 1))
        signal = _signal_from_percentile(percentile)
        score_value = round(percentile * 100.0, 2)
        drivers = _build_driver_factors(row)
        feature_values = _build_feature_values(row)
        expected_return = _safe_float(row.get("expected_return"))
        summary = _build_summary(
            expected_return=expected_return,
            rank=rank,
            total=total,
            drivers=drivers,
            horizon_days=horizon_days,
        )
        score_rows.append(
            StockStrategyScore(
                run_id=run.id,
                symbol=str(row.get("symbol") or ""),
                as_of=target_date,
                score=score_value,
                rank=rank,
                percentile=percentile,
                expected_return=expected_return,
                signal=signal,
                summary=summary,
                feature_values_json=_serialize_json(feature_values, "[]"),
                driver_factors_json=_serialize_json(drivers, "[]"),
            )
        )
    db.add_all(score_rows)
    db.commit()
    db.refresh(run)

    items, _, _ = list_smoke_butt_candidates(db, limit=10, offset=0, run=run)
    return _serialize_run(run), items


def list_smoke_butt_candidates(
    db: Session,
    *,
    market: str | None = None,
    signal: str | None = None,
    limit: int = 20,
    offset: int = 0,
    run: StockStrategyRun | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
    active_run = run or get_latest_smoke_butt_run(db)
    if active_run is None:
        return [], 0, None

    query = (
        db.query(StockStrategyScore, Stock)
        .outerjoin(Stock, Stock.symbol == StockStrategyScore.symbol)
        .filter(StockStrategyScore.run_id == active_run.id)
    )
    if market:
        query = query.filter(Stock.market == market)
    if signal:
        query = query.filter(StockStrategyScore.signal == signal)

    total = query.count()
    rows = query.order_by(StockStrategyScore.rank.asc(), StockStrategyScore.symbol.asc()).offset(offset).limit(limit).all()
    items = []
    for score, stock in rows:
        serialized = _serialize_score_row(active_run, score, stock)
        serialized.pop("run", None)
        serialized.pop("drivers", None)
        serialized.pop("feature_values", None)
        items.append(serialized)
    return items, total, _serialize_run(active_run)


def get_smoke_butt_detail(db: Session, symbol: str) -> dict[str, Any] | None:
    active_run = get_latest_smoke_butt_run(db)
    if active_run is None:
        return None

    normalized = normalize_symbol(symbol)
    row = (
        db.query(StockStrategyScore, Stock)
        .outerjoin(Stock, Stock.symbol == StockStrategyScore.symbol)
        .filter(StockStrategyScore.run_id == active_run.id, StockStrategyScore.symbol == normalized)
        .first()
    )
    if row is None:
        return None
    score, stock = row
    return _serialize_score_row(active_run, score, stock)
