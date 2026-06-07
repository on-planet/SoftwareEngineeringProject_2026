from __future__ import annotations

from etl.providers.market_provider import MarketProvider
from etl.providers.macro_provider import MacroProvider
from etl.providers.reference_provider import ReferenceProvider
from etl.providers.news_provider import NewsProvider
from etl.providers.events_provider import EventsProvider
from etl.providers.futures_provider import FuturesProvider
from etl.providers.index_provider import IndexProvider
from etl.providers.fund_provider import FundProvider
from etl.utils.data_source_registry import provider_registry


class DataProvider:
    """统一数据门面。

    所有业务代码（Service / Job / Router）均通过此类获取外部数据，
    不再直接引用底层 etl.fetchers。

    示例：
        provider = DataProvider()
        quotes = provider.market.get_stock_quote("000001.SZ")
        macros = provider.macro.fetch_all_akshare_macro_rows()
    """

    _instance: DataProvider | None = None

    def __new__(cls) -> DataProvider:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_providers()
        return cls._instance

    def _init_providers(self) -> None:
        self.market = MarketProvider()
        self.macro = MacroProvider()
        self.reference = ReferenceProvider()
        self.news = NewsProvider()
        self.events = EventsProvider()
        self.futures = FuturesProvider()
        self.index = IndexProvider()
        self.fund = FundProvider()

        # 注册到全局注册表
        provider_registry.register("market", self.market)
        provider_registry.register("macro", self.macro)
        provider_registry.register("reference", self.reference)
        provider_registry.register("news", self.news)
        provider_registry.register("events", self.events)
        provider_registry.register("futures", self.futures)
        provider_registry.register("index", self.index)
        provider_registry.register("fund", self.fund)

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
        provider_registry.clear()


# 导出便捷单例函数
def get_provider() -> DataProvider:
    return DataProvider()


__all__ = [
    "DataProvider",
    "get_provider",
    "MarketProvider",
    "MacroProvider",
    "ReferenceProvider",
    "NewsProvider",
    "EventsProvider",
    "FuturesProvider",
    "IndexProvider",
    "FundProvider",
]
