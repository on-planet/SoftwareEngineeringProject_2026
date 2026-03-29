from __future__ import annotations

from dataclasses import dataclass

from etl.utils.news_entities import extract_entities
from etl.utils.news_events import classify_news_event

NEWS_NLP_VERSION = "rule-nlp-v1"


@dataclass(frozen=True)
class NewsNlpResult:
    related_symbols: list[str]
    related_sectors: list[str]
    themes: list[str]
    event_type: str | None
    event_tags: list[str]
    impact_direction: str
    confidence: float
    keywords: list[str]
    version: str = NEWS_NLP_VERSION


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _resolve_impact_direction(event_hint: str | None, sentiment: str | None) -> str:
    normalized_sentiment = str(sentiment or "neutral").strip().lower()
    if event_hint in {"positive", "negative"}:
        if normalized_sentiment == "neutral":
            return event_hint
        if normalized_sentiment == event_hint:
            return event_hint
        return "mixed"
    if normalized_sentiment in {"positive", "negative"}:
        return normalized_sentiment
    return "neutral"


def _compute_confidence(
    *,
    seed_symbol: str | None,
    related_symbols: list[str],
    related_sectors: list[str],
    themes: list[str],
    event_score: int,
    impact_direction: str,
) -> float:
    score = 0.30
    if seed_symbol and seed_symbol in related_symbols:
        score += 0.16
    score += min(len(related_symbols), 2) * 0.14
    score += min(len(related_sectors), 2) * 0.08
    if themes:
        score += 0.08
    if event_score > 0:
        score += 0.10 + min(event_score, 4) * 0.04
    if impact_direction != "neutral":
        score += 0.04
    return round(min(score, 0.95), 2)


def extract_news_nlp(
    title: str,
    *,
    symbol: str | None = None,
    source: str | None = None,
    topic_category: str | None = None,
    sentiment: str | None = None,
) -> NewsNlpResult:
    del source, topic_category
    entities = extract_entities(title, seed_symbol=symbol)
    event_match = classify_news_event(title)
    impact_direction = _resolve_impact_direction(event_match.impact_hint, sentiment)
    keywords = _dedupe(entities.keywords + event_match.keywords)[:10]
    confidence = _compute_confidence(
        seed_symbol=symbol,
        related_symbols=entities.related_symbols,
        related_sectors=entities.related_sectors,
        themes=entities.themes,
        event_score=event_match.score,
        impact_direction=impact_direction,
    )
    return NewsNlpResult(
        related_symbols=entities.related_symbols,
        related_sectors=entities.related_sectors,
        themes=entities.themes,
        event_type=event_match.event_type,
        event_tags=event_match.event_tags,
        impact_direction=impact_direction,
        confidence=confidence,
        keywords=keywords,
    )
