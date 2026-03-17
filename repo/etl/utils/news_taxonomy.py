from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")

SOURCE_RULES: list[tuple[str, dict[str, str]]] = [
    (
        "quanwenrss.com/caixin/economy",
        {
            "source_site": "Caixin",
            "source_category": "financial_media",
            "topic_category": "macro_economy",
        },
    ),
    (
        "quanwenrss.com/morganstanley/global",
        {
            "source_site": "Morgan Stanley",
            "source_category": "investment_research",
            "topic_category": "global_markets",
        },
    ),
    (
        "quanwenrss.com/apnews/world",
        {
            "source_site": "AP News",
            "source_category": "international_media",
            "topic_category": "world_news",
        },
    ),
    (
        "quanwenrss.com/politico/finance",
        {
            "source_site": "Politico",
            "source_category": "policy_media",
            "topic_category": "financial_policy",
        },
    ),
]

SOURCE_NAME_RULES: list[tuple[str, dict[str, str]]] = [
    (
        "Caixin Economy",
        {
            "source_site": "Caixin",
            "source_category": "financial_media",
            "topic_category": "macro_economy",
        },
    ),
    (
        "Morgan Stanley Global",
        {
            "source_site": "Morgan Stanley",
            "source_category": "investment_research",
            "topic_category": "global_markets",
        },
    ),
    (
        "AP News World",
        {
            "source_site": "AP News",
            "source_category": "international_media",
            "topic_category": "world_news",
        },
    ),
    (
        "Politico Finance",
        {
            "source_site": "Politico",
            "source_category": "policy_media",
            "topic_category": "financial_policy",
        },
    ),
    (
        "RSSHub CLS Telegraph",
        {
            "source_site": "CLS",
            "source_category": "financial_media",
            "topic_category": "market_flash",
        },
    ),
    (
        "Yahoo TW Intl Markets",
        {
            "source_site": "Yahoo Taiwan",
            "source_category": "finance_portal",
            "topic_category": "global_markets",
        },
    ),
    (
        "Yahoo TW Funds",
        {
            "source_site": "Yahoo Taiwan",
            "source_category": "finance_portal",
            "topic_category": "funds",
        },
    ),
    (
        "Yahoo TW News",
        {
            "source_site": "Yahoo Taiwan",
            "source_category": "finance_portal",
            "topic_category": "market_news",
        },
    ),
    (
        "Yahoo TW Market",
        {
            "source_site": "Yahoo Taiwan",
            "source_category": "finance_portal",
            "topic_category": "market_news",
        },
    ),
    (
        "Yahoo TW Personal Finance",
        {
            "source_site": "Yahoo Taiwan",
            "source_category": "finance_portal",
            "topic_category": "personal_finance",
        },
    ),
    (
        "Yahoo TW Column",
        {
            "source_site": "Yahoo Taiwan",
            "source_category": "finance_portal",
            "topic_category": "opinion",
        },
    ),
    (
        "Yahoo TW Research",
        {
            "source_site": "Yahoo Taiwan",
            "source_category": "finance_portal",
            "topic_category": "research",
        },
    ),
]


def classify_time_bucket(published_at: datetime | None) -> str | None:
    if published_at is None:
        return None
    dt = published_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(CN_TZ)
    if local_dt.weekday() >= 5:
        return "weekend"
    minutes = local_dt.hour * 60 + local_dt.minute
    if minutes < 9 * 60 + 30:
        return "pre_market"
    if minutes < 15 * 60:
        return "trading_hours"
    if minutes < 20 * 60:
        return "post_market"
    return "night"


def classify_news_metadata(*, source: str | None, link: str | None, published_at: datetime | None) -> dict[str, str | None]:
    text_source = str(source or "").strip()
    text_link = str(link or "").strip()
    text_link_lower = text_link.lower()

    for needle, payload in SOURCE_RULES:
        if needle in text_link_lower:
            return {
                **payload,
                "time_bucket": classify_time_bucket(published_at),
            }

    for needle, payload in SOURCE_NAME_RULES:
        if text_source == needle:
            return {
                **payload,
                "time_bucket": classify_time_bucket(published_at),
            }

    host = urlparse(text_link).hostname or ""
    host = host.lower()
    source_site = text_source or (host.replace("www.", "") if host else None)
    return {
        "source_site": source_site,
        "source_category": "general_news",
        "topic_category": "general",
        "time_bucket": classify_time_bucket(published_at),
    }
