from __future__ import annotations

from datetime import date

from etl.providers.base_provider import BaseProvider
from etl.fetchers.news_client import get_news as _get_news


class NewsProvider(BaseProvider):
    """新闻资讯 Provider：RSS 聚合与新闻抓取。"""

    def get_news(self, as_of: date) -> list[dict]:
        result = self._safe_call(_get_news, as_of)
        return result or []
