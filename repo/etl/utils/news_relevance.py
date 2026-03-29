from __future__ import annotations

from etl.utils.news_nlp import extract_news_nlp


def infer_news_relevance(title: str, *, symbol: str | None = None) -> dict[str, str | None]:
    result = extract_news_nlp(title, symbol=symbol)
    return {
        "related_symbols": ",".join(result.related_symbols) if result.related_symbols else None,
        "related_sectors": ",".join(result.related_sectors) if result.related_sectors else None,
    }
