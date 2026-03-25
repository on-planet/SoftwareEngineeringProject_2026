from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class StrategyFeatureImportanceOut(BaseModel):
    feature: str
    importance: float | None = None
    stddev: float | None = None
    p_value: float | None = None
    n: int | None = None


class StrategyLeaderboardItemOut(BaseModel):
    model: str
    score_val: float | None = None
    fit_time: float | None = None
    pred_time_val: float | None = None


class StrategyRunOut(BaseModel):
    id: int
    strategy_code: str
    strategy_name: str
    as_of: date
    label_horizon: int
    status: str
    model_path: str | None = None
    train_rows: int
    scored_rows: int
    trained_at: datetime
    evaluation: dict[str, float | int | str | None] = Field(default_factory=dict)
    leaderboard: list[StrategyLeaderboardItemOut] = Field(default_factory=list)
    feature_importance: list[StrategyFeatureImportanceOut] = Field(default_factory=list)


class StrategyDriverOut(BaseModel):
    label: str
    tone: str
    value: float | None = None
    display_value: str | None = None


class StrategyFeatureValueOut(BaseModel):
    name: str
    value: float | None = None
    display_value: str | None = None


class SmokeButtCandidateOut(BaseModel):
    symbol: str
    name: str
    market: str
    sector: str
    as_of: date
    score: float
    rank: int
    percentile: float
    expected_return: float | None = None
    signal: str
    summary: str | None = None


class SmokeButtDetailOut(SmokeButtCandidateOut):
    run: StrategyRunOut
    drivers: list[StrategyDriverOut] = Field(default_factory=list)
    feature_values: list[StrategyFeatureValueOut] = Field(default_factory=list)


class SmokeButtPageOut(BaseModel):
    items: list[SmokeButtCandidateOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    run: StrategyRunOut | None = None


class SmokeButtTrainIn(BaseModel):
    as_of: date | None = None
    horizon_days: int = Field(60, ge=20, le=240)
    sample_step: int = Field(21, ge=5, le=63)
    time_limit_seconds: int | None = Field(120, ge=30, le=1800)
    force_retrain: bool = False


class SmokeButtTrainOut(BaseModel):
    run: StrategyRunOut
    items: list[SmokeButtCandidateOut] = Field(default_factory=list)
