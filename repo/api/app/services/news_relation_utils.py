from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Query, selectinload

from app.models.news import News, NewsRelatedSector, NewsRelatedSymbol
from app.schemas.news import NewsOut


def normalize_news_relation_values(values: list[str] | tuple[str, ...] | set[str] | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = values.split(",")
    else:
        raw_values = list(values)
    seen: set[str] = set()
    output: list[str] = []
    for raw in raw_values:
        text = str(raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def join_news_relation_values(values: list[str] | tuple[str, ...] | set[str] | str | None) -> str | None:
    normalized = normalize_news_relation_values(values)
    return ",".join(normalized) if normalized else None


def apply_news_relations(
    item: News,
    *,
    related_symbols: list[str] | tuple[str, ...] | set[str] | str | None = None,
    related_sectors: list[str] | tuple[str, ...] | set[str] | str | None = None,
) -> News:
    normalized_symbols = normalize_news_relation_values(related_symbols)
    normalized_sectors = normalize_news_relation_values(related_sectors)
    item.related_symbols_csv = ",".join(normalized_symbols) if normalized_symbols else None
    item.related_sectors_csv = ",".join(normalized_sectors) if normalized_sectors else None
    item.related_symbol_rows = [NewsRelatedSymbol(symbol=symbol) for symbol in normalized_symbols]
    item.related_sector_rows = [NewsRelatedSector(sector=sector) for sector in normalized_sectors]
    return item


def with_news_relations(query: Query) -> Query:
    return query.options(
        selectinload(News.related_symbol_rows),
        selectinload(News.related_sector_rows),
    )


def filter_news_by_related_symbols(query: Query, related_symbols: list[str] | str | None) -> Query:
    normalized = normalize_news_relation_values(related_symbols)
    if not normalized:
        return query
    return query.filter(News.related_symbol_rows.any(NewsRelatedSymbol.symbol.in_(normalized)))


def filter_news_by_related_sectors(query: Query, related_sectors: list[str] | str | None) -> Query:
    normalized = normalize_news_relation_values(related_sectors)
    if not normalized:
        return query
    return query.filter(News.related_sector_rows.any(NewsRelatedSector.sector.in_(normalized)))


def serialize_news_item(item: News | dict[str, Any]) -> dict[str, Any]:
    if isinstance(item, dict):
        payload = NewsOut(**item)
    elif hasattr(NewsOut, "model_validate"):
        payload = NewsOut.model_validate(item, from_attributes=True)
    else:
        payload = NewsOut.from_orm(item)
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


def serialize_news_items(items: list[News]) -> list[dict[str, Any]]:
    return [serialize_news_item(item) for item in items]
