from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.schemas.kline import KlinePeriod
from app.schemas.risk import RiskOut
from app.schemas.stock import StockOverviewOut, StockProfilePanelOut, StockWithRiskOut
from app.services.kline_service import get_stock_kline
from app.services.live_market_service import (
    get_live_stock_overview_profile,
    get_live_stock_profile,
    get_live_stock_profile_extras,
)
from app.services.research_service import get_stock_research
from app.services.risk_service import get_risk_snapshot
from app.services.score_service import get_fundamental_score
from app.utils.symbols import normalize_symbol

_MISSING = object()


def get_stock_profile_payload(symbol: str, *, prefer_live: bool = False):
    return get_live_stock_profile(symbol, prefer_live=prefer_live)


def get_stock_overview_payload(symbol: str, *, prefer_live: bool = False):
    return get_live_stock_overview_profile(symbol, prefer_live=prefer_live)


def get_stock_profile_extras_payload(symbol: str, *, prefer_live: bool = False):
    return get_live_stock_profile_extras(symbol, prefer_live=prefer_live)


def _risk_out(symbol: str, payload: dict | None) -> RiskOut | None:
    if not payload:
        return None
    return RiskOut(
        symbol=symbol,
        max_drawdown=payload.get("max_drawdown"),
        volatility=payload.get("volatility"),
        as_of=payload.get("as_of"),
        cache_hit=payload.get("cache_hit"),
    )


def _stock_payload_to_dict(stock, output_model) -> dict[str, Any]:
    if isinstance(stock, dict):
        return dict(stock)
    return output_model.from_orm(stock).model_dump()


@dataclass
class StockRequestContext:
    symbol: str
    prefer_live: bool = False
    _normalized_symbol: str = field(init=False, repr=False)
    _profile_payload: Any = field(default=_MISSING, init=False, repr=False)
    _overview_payload: Any = field(default=_MISSING, init=False, repr=False)
    _profile_extras_payload: Any = field(default=_MISSING, init=False, repr=False)
    _fundamental_payload: Any = field(default=_MISSING, init=False, repr=False)
    _risk_snapshots: dict[int, dict | None] = field(default_factory=dict, init=False, repr=False)
    _research_payloads: dict[tuple[int, int], dict] = field(default_factory=dict, init=False, repr=False)
    _kline_payloads: dict[tuple[KlinePeriod, int, date | None, date | None], list] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._normalized_symbol = normalize_symbol(self.symbol)

    @property
    def normalized_symbol(self) -> str:
        return self._normalized_symbol

    def get_profile_payload(self):
        if self._profile_payload is _MISSING:
            self._profile_payload = get_stock_profile_payload(self.normalized_symbol, prefer_live=self.prefer_live)
        return self._profile_payload

    def get_overview_payload(self):
        if self._overview_payload is _MISSING:
            self._overview_payload = get_stock_overview_payload(self.normalized_symbol, prefer_live=self.prefer_live)
        return self._overview_payload

    def get_profile_extras_payload(self):
        if self._profile_extras_payload is _MISSING:
            self._profile_extras_payload = get_stock_profile_extras_payload(
                self.normalized_symbol,
                prefer_live=self.prefer_live,
            )
        return self._profile_extras_payload

    def get_risk_snapshot(self, *, window: int = 60) -> dict | None:
        if window not in self._risk_snapshots:
            self._risk_snapshots[window] = get_risk_snapshot(self.normalized_symbol, window=window)
        return self._risk_snapshots[window]

    def get_fundamental_payload(self):
        if self._fundamental_payload is _MISSING:
            self._fundamental_payload = get_fundamental_score(self.normalized_symbol)
        return self._fundamental_payload

    def get_research_payload(self, *, report_limit: int = 10, forecast_limit: int = 10) -> dict:
        key = (report_limit, forecast_limit)
        if key not in self._research_payloads:
            self._research_payloads[key] = get_stock_research(
                self.normalized_symbol,
                report_limit=report_limit,
                forecast_limit=forecast_limit,
            )
        return self._research_payloads[key]

    def get_stock_kline(
        self,
        *,
        period: KlinePeriod = "day",
        limit: int = 200,
        end: date | None = None,
        start: date | None = None,
    ):
        key = (period, limit, start, end)
        if key not in self._kline_payloads:
            self._kline_payloads[key] = get_stock_kline(
                self.normalized_symbol,
                period=period,
                limit=limit,
                end=end,
                start=start,
            )
        return self._kline_payloads[key]


def build_stock_with_risk(context: StockRequestContext) -> StockWithRiskOut | None:
    stock = context.get_profile_payload()
    if stock is None:
        return None
    payload = _stock_payload_to_dict(stock, StockWithRiskOut)
    risk_payload = context.get_risk_snapshot()
    if risk_payload:
        payload["risk"] = _risk_out(context.normalized_symbol, risk_payload)
    return StockWithRiskOut(**payload)


def build_stock_profile_panel(context: StockRequestContext) -> StockProfilePanelOut | None:
    stock = context.get_profile_payload()
    if stock is None:
        return None
    payload = _stock_payload_to_dict(stock, StockProfilePanelOut)
    risk_payload = context.get_risk_snapshot()
    if risk_payload:
        payload["risk"] = _risk_out(context.normalized_symbol, risk_payload)
    payload["fundamental"] = context.get_fundamental_payload()
    return StockProfilePanelOut(**payload)


def build_stock_overview_panel(context: StockRequestContext) -> StockOverviewOut | None:
    stock = context.get_overview_payload()
    if stock is None:
        return None
    payload = _stock_payload_to_dict(stock, StockOverviewOut)
    risk_payload = context.get_risk_snapshot()
    if risk_payload:
        payload["risk"] = _risk_out(context.normalized_symbol, risk_payload)
    payload["fundamental"] = context.get_fundamental_payload()
    return StockOverviewOut(**payload)
