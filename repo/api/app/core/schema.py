from __future__ import annotations

from sqlalchemy import text

from app.core.db import engine
from app.models.base import Base

# Import models so SQLAlchemy metadata contains every table before create_all().
from app.models.buyback import Buyback  # noqa: F401
from app.models.daily_prices import DailyPrice  # noqa: F401
from app.models.events import Event  # noqa: F401
from app.models.financials import Financial  # noqa: F401
from app.models.fund_holdings import FundHolding  # noqa: F401
from app.models.fundamental_score import FundamentalScore  # noqa: F401
from app.models.futures_price import FuturesPrice  # noqa: F401
from app.models.futures_weekly_price import FuturesWeeklyPrice  # noqa: F401
from app.models.index_constituent import IndexConstituent  # noqa: F401
from app.models.indices import Index  # noqa: F401
from app.models.insider_trade import InsiderTrade  # noqa: F401
from app.models.macro import Macro  # noqa: F401
from app.models.news import News  # noqa: F401
from app.models.sector_exposure import SectorExposure  # noqa: F401
from app.models.sector_exposure_summary import SectorExposureSummary  # noqa: F401
from app.models.stock_valuation_snapshot import StockValuationSnapshot  # noqa: F401
from app.models.stock_live_snapshot import StockLiveSnapshot  # noqa: F401
from app.models.stock_intraday_kline import StockIntradayKline  # noqa: F401
from app.models.stock_research_item import StockResearchItem  # noqa: F401
from app.models.stocks import Stock  # noqa: F401
from app.models.user_portfolio import UserPortfolio  # noqa: F401


def init_schema() -> None:
    Base.metadata.create_all(bind=engine)
    statements = [
        "ALTER TABLE futures_prices ADD COLUMN IF NOT EXISTS contract_month VARCHAR(16)",
        "ALTER TABLE futures_prices ADD COLUMN IF NOT EXISTS settlement DOUBLE PRECISION",
        "ALTER TABLE futures_prices ADD COLUMN IF NOT EXISTS open_interest DOUBLE PRECISION",
        "ALTER TABLE futures_prices ADD COLUMN IF NOT EXISTS turnover DOUBLE PRECISION",
        "ALTER TABLE futures_weekly_prices ADD COLUMN IF NOT EXISTS contract_month VARCHAR(16)",
        "ALTER TABLE futures_weekly_prices ADD COLUMN IF NOT EXISTS settlement DOUBLE PRECISION",
        "ALTER TABLE futures_weekly_prices ADD COLUMN IF NOT EXISTS open_interest DOUBLE PRECISION",
        "ALTER TABLE futures_weekly_prices ADD COLUMN IF NOT EXISTS turnover DOUBLE PRECISION",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS source_site VARCHAR(128)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS source_category VARCHAR(64)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS topic_category VARCHAR(64)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS time_bucket VARCHAR(32)",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS related_symbols TEXT",
        "ALTER TABLE news ADD COLUMN IF NOT EXISTS related_sectors TEXT",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS as_of TIMESTAMP",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS current DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS change DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS percent DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS open DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS high DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS low DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS last_close DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS volume DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS amount DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS turnover_rate DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS amplitude DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS quote_timestamp TIMESTAMP",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS pe_ttm DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS pb DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS ps_ttm DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS pcf DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS market_cap DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS float_market_cap DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS dividend_yield DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS volume_ratio DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS lot_size DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS pankou_diff DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS pankou_ratio DOUBLE PRECISION",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS pankou_timestamp TIMESTAMP",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS pankou_bids_json TEXT",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS pankou_asks_json TEXT",
        "ALTER TABLE stock_live_snapshots ADD COLUMN IF NOT EXISTS source VARCHAR(64)",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
