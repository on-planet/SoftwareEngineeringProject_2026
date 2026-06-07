from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.financials import Financial
from app.models.stock_live_snapshot import StockLiveSnapshot
from app.models.stocks import Stock
from app.services.live_market_remote import get_stock_quote
from app.utils.symbols import normalize_symbol
from etl.strategies.cigarbutt import CigarButtAnalyzer, FinancialPanel


def _build_financial_panel(symbol: str, db: Session) -> FinancialPanel:
    """Build FinancialPanel from existing DB models (best-effort)."""
    normalized = normalize_symbol(symbol)
    stock = db.query(Stock).filter(Stock.symbol == normalized).first()
    snapshot = (
        db.query(StockLiveSnapshot)
        .filter(StockLiveSnapshot.symbol == normalized)
        .order_by(StockLiveSnapshot.as_of.desc())
        .first()
    )
    financial = (
        db.query(Financial)
        .filter(Financial.symbol == normalized)
        .order_by(Financial.period.desc())
        .first()
    )

    panel = FinancialPanel(
        report_id=f"db-{normalized}-{date.today()}",
        stock_code=normalized,
        stock_name=stock.name if stock else normalized,
        report_period=str(financial.period) if financial else str(date.today()),
        market=stock.market if stock else "A股",
    )

    if financial:
        panel.revenue = financial.revenue
        panel.net_profit = financial.net_income
        panel.operating_cash_flow = financial.cash_flow

    if snapshot:
        panel.total_shares = _safe_shares(snapshot.market_cap, snapshot.current)
        panel.dividend_yield = snapshot.dividend_yield

    return panel


def _safe_shares(market_cap: float | None, price: float | None) -> float | None:
    if market_cap and price and price > 0:
        return market_cap / price
    return None


def _metrics_to_dict(metrics: Any) -> dict:
    """Serialize CigarButtMetrics (and nested dataclasses) to plain dict."""
    from dataclasses import asdict, is_dataclass

    def recurse(obj: Any) -> Any:
        if is_dataclass(obj):
            return {k: recurse(v) for k, v in asdict(obj).items()}
        if isinstance(obj, list):
            return [recurse(i) for i in obj]
        if isinstance(obj, dict):
            return {k: recurse(v) for k, v in obj.items()}
        return obj

    return recurse(metrics)


def analyze_cigarbutt(symbol: str, db: Session) -> dict:
    """Run static-value cigar butt analysis for a single symbol."""
    normalized = normalize_symbol(symbol)
    panel = _build_financial_panel(normalized, db)

    quote = get_stock_quote(normalized)
    stock_price = quote.get("current") if quote else None

    analyzer = CigarButtAnalyzer(current_stock_price=stock_price)
    metrics = analyzer.analyze(panel, stock_price=stock_price)

    return {
        "symbol": normalized,
        "stock_price": stock_price,
        "analysis": _metrics_to_dict(metrics),
    }
