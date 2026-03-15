from __future__ import annotations

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
from app.models.index_constituent import IndexConstituent  # noqa: F401
from app.models.indices import Index  # noqa: F401
from app.models.insider_trade import InsiderTrade  # noqa: F401
from app.models.macro import Macro  # noqa: F401
from app.models.news import News  # noqa: F401
from app.models.sector_exposure import SectorExposure  # noqa: F401
from app.models.stocks import Stock  # noqa: F401
from app.models.user_portfolio import UserPortfolio  # noqa: F401


def init_schema() -> None:
    Base.metadata.create_all(bind=engine)
