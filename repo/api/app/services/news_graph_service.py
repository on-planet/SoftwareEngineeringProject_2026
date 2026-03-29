from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
import json
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.events import Event
from app.models.news import News, NewsRelatedSector, NewsRelatedSymbol
from app.models.stocks import Stock
from app.schemas.news_graph import (
    NewsGraphChainOut,
    NewsGraphChainStepOut,
    NewsGraphEdgeOut,
    NewsGraphEntityOut,
    NewsGraphEventOut,
    NewsGraphExplanationOut,
    NewsGraphImpactSummaryOut,
    NewsGraphNodeOut,
    NewsGraphOut,
)
from app.services.news_relation_utils import serialize_news_items, with_news_relations
from etl.utils.llm_client import chat_completion
from etl.utils.sector_taxonomy import UNKNOWN_SECTOR, normalize_sector_name
from etl.utils.stock_basics_cache import load_stock_basics_cache

MAX_NEWS_ITEMS = 24
MAX_THEME_NODES = 6
MAX_PEER_NODES = 6


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


def _truncate(text: str, limit: int = 28) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1].rstrip()}…"


def _stock_lookup(symbol: str) -> dict[str, str]:
    rows = load_stock_basics_cache([symbol])
    if rows:
        row = rows[0]
        return {
            "symbol": str(row.get("symbol") or symbol),
            "name": str(row.get("name") or symbol),
            "market": str(row.get("market") or ""),
            "sector": str(row.get("sector") or UNKNOWN_SECTOR),
        }
    return {"symbol": symbol, "name": symbol, "market": "", "sector": UNKNOWN_SECTOR}


def _resolve_stock_center(db: Session, symbol: str) -> dict[str, str]:
    item = db.query(Stock).filter(Stock.symbol == symbol).first()
    if item is not None:
        return {
            "symbol": str(item.symbol or symbol),
            "name": str(item.name or symbol),
            "market": str(item.market or ""),
            "sector": str(item.sector or UNKNOWN_SECTOR),
        }
    return _stock_lookup(symbol)


def _add_node(nodes: dict[str, NewsGraphNodeOut], node: NewsGraphNodeOut) -> None:
    existing = nodes.get(node.id)
    if existing is None or node.size >= existing.size:
        nodes[node.id] = node


def _add_edge(edges: dict[tuple[str, str, str], NewsGraphEdgeOut], edge: NewsGraphEdgeOut) -> None:
    key = (edge.source, edge.target, edge.type)
    current = edges.get(key)
    if current is None or edge.weight >= current.weight:
        edges[key] = edge


def _nearby_news_query(
    db: Session,
    *,
    symbol: str,
    sector: str | None,
    start_at: datetime,
    limit: int,
) -> list[News]:
    base_query = with_news_relations(db.query(News)).filter(News.published_at >= start_at)
    target_limit = max(1, min(int(limit), MAX_NEWS_ITEMS))
    direct_rows = (
        base_query.filter(
            or_(
                News.symbol == symbol,
                News.related_symbol_rows.any(symbol=symbol),
            )
        )
        .order_by(News.published_at.desc(), News.id.desc())
        .limit(target_limit)
        .all()
    )
    if len(direct_rows) >= target_limit or not sector or sector == UNKNOWN_SECTOR:
        return _rank_news_rows(
            direct_rows,
            score=lambda item: _stock_news_relevance_score(item, symbol=symbol, sector=sector),
        )[:target_limit]

    sector_rows = (
        base_query.filter(News.related_sector_rows.any(sector=sector))
        .order_by(News.published_at.desc(), News.id.desc())
        .limit(max(target_limit * 3, target_limit + 4))
        .all()
    )
    return _rank_news_rows(
        [*direct_rows, *sector_rows],
        score=lambda item: _stock_news_relevance_score(item, symbol=symbol, sector=sector),
    )[:target_limit]


def _nearby_event_rows(db: Session, *, symbol: str, start_date: date, limit: int = 12) -> list[Event]:
    return (
        db.query(Event)
        .filter(Event.symbol == symbol, Event.date >= start_date)
        .order_by(Event.date.desc(), Event.id.desc())
        .limit(limit)
        .all()
    )


def _event_payload(item: Event) -> NewsGraphEventOut:
    return NewsGraphEventOut(
        id=int(item.id),
        symbol=str(item.symbol or ""),
        type=str(item.type or ""),
        title=str(item.title or ""),
        date=item.date,
        link=item.link,
        source=item.source,
    )


def _dominant_sentiment(news_rows: list[News]) -> str:
    counts = Counter(str(item.sentiment or "neutral") for item in news_rows)
    if not counts:
        return "neutral"
    return counts.most_common(1)[0][0]


def _dominant_direction(news_rows: list[News]) -> str | None:
    counts = Counter(str(item.impact_direction or "").strip().lower() for item in news_rows if str(item.impact_direction or "").strip())
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _format_stock_label(symbol: str, name: str) -> str:
    normalized_symbol = str(symbol or "").strip().upper()
    normalized_name = str(name or normalized_symbol).strip() or normalized_symbol
    return f"{normalized_name} ({normalized_symbol})"


def _build_entity(*, entity_id: str, entity_type: str, label: str, sentiment: str | None = None) -> NewsGraphEntityOut:
    return NewsGraphEntityOut(id=entity_id, type=entity_type, label=label, sentiment=sentiment)


def _build_chain_step(
    *,
    entity_id: str,
    entity_type: str,
    label: str,
    relation: str | None = None,
    sentiment: str | None = None,
    weight: float | None = None,
) -> NewsGraphChainStepOut:
    return NewsGraphChainStepOut(
        id=entity_id,
        type=entity_type,
        label=label,
        relation=relation,
        sentiment=sentiment,
        weight=weight,
    )


def _news_chain_step(item: News, *, relation: str, weight: float) -> NewsGraphChainStepOut:
    return _build_chain_step(
        entity_id=f"news:{int(item.id)}",
        entity_type="news",
        label=_truncate(str(item.title or ""), 40),
        relation=relation,
        sentiment=str(item.sentiment or "").strip() or None,
        weight=weight,
    )


def _event_chain_step(item: Event, *, relation: str, weight: float) -> NewsGraphChainStepOut:
    return _build_chain_step(
        entity_id=f"event:{int(item.id)}",
        entity_type="event",
        label=_truncate(str(item.title or item.type or "event"), 36),
        relation=relation,
        weight=weight,
    )


def _event_type_chain_step(event_type: str, *, relation: str, weight: float) -> NewsGraphChainStepOut:
    return _build_chain_step(
        entity_id=f"event-tag:{event_type}",
        entity_type="event",
        label=_truncate(str(event_type or "event"), 36),
        relation=relation,
        weight=weight,
    )


def _sector_chain_step(sector: str, *, relation: str, weight: float) -> NewsGraphChainStepOut:
    return _build_chain_step(
        entity_id=f"sector:{sector}",
        entity_type="sector",
        label=str(sector or UNKNOWN_SECTOR),
        relation=relation,
        weight=weight,
    )


def _stock_chain_step(
    symbol: str,
    *,
    name: str,
    relation: str,
    weight: float,
) -> NewsGraphChainStepOut:
    normalized_symbol = str(symbol or "").strip().upper()
    return _build_chain_step(
        entity_id=f"stock:{normalized_symbol}",
        entity_type="stock",
        label=_format_stock_label(normalized_symbol, name),
        relation=relation,
        weight=weight,
    )


def _dedupe_entities(entities: list[NewsGraphEntityOut]) -> list[NewsGraphEntityOut]:
    seen: set[str] = set()
    output: list[NewsGraphEntityOut] = []
    for item in entities:
        if item.id in seen:
            continue
        seen.add(item.id)
        output.append(item)
    return output


def _dedupe_news_rows(rows: list[News]) -> list[News]:
    seen: set[int] = set()
    output: list[News] = []
    for item in rows:
        news_id = int(getattr(item, "id", 0) or 0)
        if news_id <= 0 or news_id in seen:
            continue
        seen.add(news_id)
        output.append(item)
    return output


def _normalize_symbol_values(values: list[str] | tuple[str, ...] | set[str] | None) -> set[str]:
    normalized: set[str] = set()
    for value in values or []:
        text = str(value or "").strip().upper()
        if not text:
            continue
        normalized.add(text)
    return normalized


def _normalize_sector_values(values: list[str] | tuple[str, ...] | set[str] | None) -> set[str]:
    normalized: set[str] = set()
    for value in values or []:
        sector = normalize_sector_name(value)
        if not sector or sector == UNKNOWN_SECTOR:
            continue
        normalized.add(sector)
    return normalized


def _stock_news_relevance_score(item: News, *, symbol: str, sector: str | None) -> int:
    normalized_symbol = str(symbol or "").strip().upper()
    target_sector = normalize_sector_name(sector)
    item_symbol = str(item.symbol or "").strip().upper()
    related_symbols = _normalize_symbol_values(item.related_symbols)
    related_sectors = _normalize_sector_values(item.related_sectors)
    score = 0
    if item_symbol == normalized_symbol:
        score += 12
    if normalized_symbol in related_symbols:
        score += 10
    if target_sector and target_sector != UNKNOWN_SECTOR and target_sector in related_sectors:
        score += 2
    return score


def _focus_news_relevance_score(
    item: News,
    *,
    center_news: News,
    related_symbols: set[str],
    related_sectors: set[str],
    themes: set[str],
) -> int:
    center_symbol = str(center_news.symbol or "").strip().upper()
    item_symbol = str(item.symbol or "").strip().upper()
    item_related_symbols = _normalize_symbol_values(item.related_symbols)
    item_related_sectors = _normalize_sector_values(item.related_sectors)
    item_themes = {str(value or "").strip() for value in item.themes if str(value or "").strip()}
    shared_symbols = item_related_symbols & related_symbols
    shared_sectors = item_related_sectors & related_sectors
    shared_themes = item_themes & themes
    score = 0
    if center_symbol and center_symbol not in {"ALL", "MARKET"} and item_symbol == center_symbol:
        score += 6
    if center_symbol and center_symbol not in {"ALL", "MARKET"} and center_symbol in item_related_symbols:
        score += 4
    score += min(len(shared_symbols), 3) * 3
    score += min(len(shared_sectors), 2) * 2
    score += min(len(shared_themes), 2)
    if str(center_news.event_type or "").strip() and str(item.event_type or "").strip() == str(center_news.event_type or "").strip():
        score += 2
    return score


def _rank_news_rows(
    rows: list[News],
    *,
    score,
    min_score: int = 1,
) -> list[News]:
    ranked: list[tuple[int, datetime, int, News]] = []
    for item in _dedupe_news_rows(rows):
        relevance = int(score(item))
        if relevance < min_score:
            continue
        ranked.append(
            (
                relevance,
                item.published_at or datetime.min,
                int(getattr(item, "id", 0) or 0),
                item,
            )
        )
    ranked.sort(key=lambda entry: (entry[0], entry[1], entry[2]), reverse=True)
    return [item for _, _, _, item in ranked]


def _nearby_focus_news_query(
    db: Session,
    *,
    center_news: News,
    start_at: datetime,
    limit: int,
) -> list[News]:
    related_symbols = _normalize_symbol_values(center_news.related_symbols)
    center_symbol = str(center_news.symbol or "").strip().upper()
    if center_symbol and center_symbol not in {"ALL", "MARKET"}:
        related_symbols.add(center_symbol)
    related_sectors = _normalize_sector_values(center_news.related_sectors)
    related_themes = {str(value or "").strip() for value in center_news.themes[:MAX_THEME_NODES] if str(value or "").strip()}
    filters = []
    if related_symbols:
        filters.append(News.symbol.in_(sorted(related_symbols)))
        filters.append(News.related_symbol_rows.any(NewsRelatedSymbol.symbol.in_(sorted(related_symbols))))
    if related_sectors:
        filters.append(News.related_sector_rows.any(NewsRelatedSector.sector.in_(sorted(related_sectors))))
    if str(center_news.event_type or "").strip():
        filters.append(News.event_type == str(center_news.event_type))
    if not filters:
        return []

    target_limit = max(1, min(int(limit), 12))
    candidates = (
        with_news_relations(db.query(News))
        .filter(News.id != int(center_news.id), News.published_at >= start_at)
        .filter(or_(*filters))
        .order_by(News.published_at.desc(), News.id.desc())
        .limit(max(target_limit * 4, 12))
        .all()
    )
    return _rank_news_rows(
        candidates,
        score=lambda item: _focus_news_relevance_score(
            item,
            center_news=center_news,
            related_symbols=related_symbols,
            related_sectors=related_sectors,
            themes=related_themes,
        ),
        min_score=3,
    )[:target_limit]


def _append_chain(
    chains: list[NewsGraphChainOut],
    seen: set[tuple[str, ...]],
    *,
    chain_id: str,
    title: str,
    steps: list[NewsGraphChainStepOut],
    strength: float,
    summary: str | None = None,
) -> None:
    filtered_steps = [step for step in steps if str(step.label or "").strip()]
    if len(filtered_steps) < 2:
        return
    key = tuple(step.id for step in filtered_steps)
    if key in seen:
        return
    seen.add(key)
    chains.append(
        NewsGraphChainOut(
            id=chain_id,
            title=title,
            summary=summary or " -> ".join(step.label for step in filtered_steps),
            strength=round(max(strength, 0.0), 2),
            steps=filtered_steps,
        )
    )


def _limit_chains(chains: list[NewsGraphChainOut], limit: int = 4) -> list[NewsGraphChainOut]:
    return sorted(chains, key=lambda item: item.strength, reverse=True)[:limit]


def _build_impact_summary(
    *,
    news_rows: list[News],
    events: list[Event],
    propagation_chains: list[NewsGraphChainOut],
    impact_chains: list[NewsGraphChainOut],
    symbol_entities: list[NewsGraphEntityOut],
    sector_entities: list[NewsGraphEntityOut],
) -> NewsGraphImpactSummaryOut:
    return NewsGraphImpactSummaryOut(
        related_news_count=len(news_rows),
        related_event_count=len(events),
        propagation_chain_count=len(propagation_chains),
        impact_chain_count=len(impact_chains),
        dominant_sentiment=_dominant_sentiment(news_rows),
        dominant_direction=_dominant_direction(news_rows),
        affected_symbols=_dedupe_entities(symbol_entities)[:6],
        affected_sectors=_dedupe_entities(sector_entities)[:4],
        portfolio_hint=(
            "Intersect the impacted symbols with a watchlist or holdings scope to estimate portfolio spillover."
            if symbol_entities
            else None
        ),
    )


def _build_stock_graph_chains(
    *,
    symbol: str,
    center_name: str,
    center_sector: str,
    news_rows: list[News],
    events: list[Event],
    allowed_peers: set[str],
) -> tuple[list[NewsGraphChainOut], list[NewsGraphChainOut]]:
    propagation_chains: list[NewsGraphChainOut] = []
    impact_chains: list[NewsGraphChainOut] = []
    propagation_seen: set[tuple[str, ...]] = set()
    impact_seen: set[tuple[str, ...]] = set()

    for item in news_rows:
        direct_hit = symbol == str(item.symbol or "").upper() or symbol in item.related_symbols
        shared_sector = next(
            (sector for sector in item.related_sectors if sector == center_sector),
            item.related_sectors[0] if item.related_sectors else (center_sector if center_sector != UNKNOWN_SECTOR else None),
        )
        nearby_event = None
        if item.published_at is not None:
            nearby_event = next(
                (
                    event_item
                    for event_item in events
                    if event_item.date is not None and abs((item.published_at.date() - event_item.date).days) <= 3
                ),
                None,
            )
        propagation_steps = [_news_chain_step(item, relation="headline emerges", weight=1.0)]
        propagation_title = "Propagation chain to target stock"
        propagation_strength = 0.82 if direct_hit else 0.7
        if nearby_event is not None:
            propagation_steps.append(_event_chain_step(nearby_event, relation="co-occurs with event", weight=0.84))
            propagation_title = "Propagation chain through event"
            propagation_strength += 0.08
        elif shared_sector and shared_sector != UNKNOWN_SECTOR:
            propagation_steps.append(_sector_chain_step(shared_sector, relation="spreads through sector", weight=0.74))
            propagation_title = "Propagation chain through sector"
        propagation_steps.append(
            _stock_chain_step(
                symbol,
                name=center_name,
                relation="lands on target stock",
                weight=1.0 if direct_hit else 0.86,
            )
        )
        _append_chain(
            propagation_chains,
            propagation_seen,
            chain_id=f"propagation-stock-{int(item.id)}",
            title=propagation_title,
            steps=propagation_steps,
            strength=propagation_strength,
        )

        peer_symbols = [peer for peer in item.related_symbols if peer != symbol and peer in allowed_peers]
        bridge_sector = shared_sector if shared_sector and shared_sector != UNKNOWN_SECTOR else None
        for peer in peer_symbols[:2]:
            peer_meta = _stock_lookup(peer)
            impact_steps = [_news_chain_step(item, relation="headline emerges", weight=1.0)]
            if bridge_sector is not None:
                impact_steps.append(_sector_chain_step(bridge_sector, relation="sector spillover", weight=0.7))
            else:
                impact_steps.append(
                    _stock_chain_step(
                        symbol,
                        name=center_name,
                        relation="readthrough from target stock",
                        weight=0.64,
                    )
                )
            impact_steps.append(
                _stock_chain_step(
                    peer,
                    name=str(peer_meta.get("name") or peer),
                    relation="affects peer stock",
                    weight=0.72,
                )
            )
            _append_chain(
                impact_chains,
                impact_seen,
                chain_id=f"impact-stock-{int(item.id)}-{peer}",
                title="Impact chain to peer stock",
                steps=impact_steps,
                strength=0.76 if bridge_sector is not None else 0.66,
            )

    return _limit_chains(propagation_chains), _limit_chains(impact_chains)


def _build_focus_graph_chains(
    *,
    center_news: News,
    nearby_news: list[News],
    related_symbols: list[str],
    related_sectors: list[str],
) -> tuple[list[NewsGraphChainOut], list[NewsGraphChainOut]]:
    propagation_chains: list[NewsGraphChainOut] = []
    impact_chains: list[NewsGraphChainOut] = []
    propagation_seen: set[tuple[str, ...]] = set()
    impact_seen: set[tuple[str, ...]] = set()
    primary_sector = related_sectors[0] if related_sectors else None

    for symbol in related_symbols[:3]:
        stock_meta = _stock_lookup(symbol)
        steps = [_news_chain_step(center_news, relation="seed headline", weight=1.0)]
        title = "Propagation chain from headline"
        strength = 0.82
        if str(center_news.event_type or "").strip():
            steps.append(
                _event_type_chain_step(
                    str(center_news.event_type),
                    relation="interpreted as event",
                    weight=0.8,
                )
            )
            title = "Propagation chain through detected event"
            strength += 0.08
        elif primary_sector and primary_sector != UNKNOWN_SECTOR:
            steps.append(_sector_chain_step(primary_sector, relation="travels through sector", weight=0.72))
            title = "Propagation chain through sector"
        steps.append(
            _stock_chain_step(
                symbol,
                name=str(stock_meta.get("name") or symbol),
                relation="lands on stock",
                weight=0.88,
            )
        )
        _append_chain(
            propagation_chains,
            propagation_seen,
            chain_id=f"propagation-news-{int(center_news.id)}-{symbol}",
            title=title,
            steps=steps,
            strength=strength,
        )

    for symbol in related_symbols[1:4]:
        stock_meta = _stock_lookup(symbol)
        steps = [_news_chain_step(center_news, relation="seed headline", weight=1.0)]
        if primary_sector and primary_sector != UNKNOWN_SECTOR:
            steps.append(_sector_chain_step(primary_sector, relation="sector readthrough", weight=0.7))
        steps.append(
            _stock_chain_step(
                symbol,
                name=str(stock_meta.get("name") or symbol),
                relation="impacts additional stock",
                weight=0.72,
            )
        )
        _append_chain(
            impact_chains,
            impact_seen,
            chain_id=f"impact-news-{int(center_news.id)}-{symbol}",
            title="Impact chain to additional stocks",
            steps=steps,
            strength=0.72,
        )

    for item in nearby_news[:3]:
        picked_symbol = next((value for value in item.related_symbols if value), None)
        if picked_symbol is None:
            continue
        stock_meta = _stock_lookup(picked_symbol)
        shared_sector = next((sector for sector in item.related_sectors if sector in related_sectors), primary_sector)
        steps = [
            _news_chain_step(center_news, relation="seed headline", weight=1.0),
            _news_chain_step(item, relation="media pickup", weight=0.72),
        ]
        if shared_sector and shared_sector != UNKNOWN_SECTOR:
            steps.append(_sector_chain_step(shared_sector, relation="sector spillover", weight=0.66))
        steps.append(
            _stock_chain_step(
                picked_symbol,
                name=str(stock_meta.get("name") or picked_symbol),
                relation="affects downstream stock",
                weight=0.68,
            )
        )
        _append_chain(
            impact_chains,
            impact_seen,
            chain_id=f"impact-nearby-news-{int(center_news.id)}-{int(item.id)}",
            title="Impact chain across related coverage",
            steps=steps,
            strength=0.78,
        )

    return _limit_chains(propagation_chains), _limit_chains(impact_chains)


def _build_template_explanation(
    *,
    center_label: str,
    days: int,
    sector: str,
    news_rows: list[News],
    events: list[Event],
    themes: list[str],
    peers: list[str],
) -> NewsGraphExplanationOut:
    counts = Counter(str(item.sentiment or "neutral") for item in news_rows)
    positive = counts.get("positive", 0)
    negative = counts.get("negative", 0)
    neutral = counts.get("neutral", 0)
    dominant = _dominant_sentiment(news_rows)
    dominant_text = {
        "positive": "偏正面",
        "negative": "偏负面",
        "neutral": "偏中性",
        "mixed": "多空交织",
    }.get(dominant, "偏中性")
    event_types = Counter(str(item.event_type or "") for item in news_rows if item.event_type)
    top_event = event_types.most_common(1)[0][0] if event_types else None
    theme_text = "、".join(themes[:3]) if themes else "暂无集中主题"
    headline = (
        f"近{days}天围绕{center_label}的新闻关系图谱显示，相关舆情{dominant_text}，"
        f"主题集中在{theme_text}。"
    )
    evidence = [
        f"关联新闻 {len(news_rows)} 条，事件 {len(events)} 个，情绪分布 正/负/中性 = {positive}/{negative}/{neutral}。",
        f"核心板块为 {sector or UNKNOWN_SECTOR}，新闻主题以 {theme_text} 为主。",
    ]
    if top_event:
        evidence.append(f"近期主导事件标签为 {top_event}。")
    if peers:
        evidence.append(f"同一批新闻里高频共现标的包括 {'、'.join(peers[:3])}。")
    risk_hint = None
    if negative > positive:
        risk_hint = "负面新闻占比更高，图谱提示短期风险事件仍需继续跟踪。"
    elif any(str(item.type or "").strip() for item in events):
        risk_hint = "若后续没有新增催化，当前传播热度可能快速回落。"
    return NewsGraphExplanationOut(
        headline=headline,
        evidence=evidence[:4],
        risk_hint=risk_hint,
        generated_by="template",
    )


def _parse_llm_json(content: str) -> dict[str, Any] | None:
    text = str(content or "").strip()
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _build_llm_explanation(
    *,
    center_label: str,
    days: int,
    sector: str,
    news_rows: list[News],
    events: list[Event],
    themes: list[str],
    peers: list[str],
    fallback: NewsGraphExplanationOut,
) -> NewsGraphExplanationOut:
    payload = {
        "center_label": center_label,
        "days": days,
        "sector": sector,
        "news_count": len(news_rows),
        "event_count": len(events),
        "sentiments": Counter(str(item.sentiment or "neutral") for item in news_rows),
        "event_types": Counter(str(item.event_type or "") for item in news_rows if item.event_type),
        "themes": themes[:6],
        "peers": peers[:6],
        "sample_news_titles": [str(item.title or "") for item in news_rows[:6]],
        "sample_event_titles": [str(item.title or "") for item in events[:4]],
    }
    content = chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "你是金融新闻图谱分析助手。"
                    "请基于给定的结构化信息输出 JSON，字段只有 headline、evidence、risk_hint。"
                    "headline 控制在 40 字内，evidence 为 2 到 4 条短句数组。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ],
        temperature=0.2,
        max_tokens=260,
    )
    parsed = _parse_llm_json(content or "")
    if not parsed:
        return fallback
    headline = str(parsed.get("headline") or "").strip()
    evidence_raw = parsed.get("evidence")
    evidence = [str(item).strip() for item in evidence_raw if str(item).strip()] if isinstance(evidence_raw, list) else []
    risk_hint = str(parsed.get("risk_hint") or "").strip() or None
    if not headline:
        return fallback
    return NewsGraphExplanationOut(
        headline=headline,
        evidence=evidence[:4] or fallback.evidence,
        risk_hint=risk_hint or fallback.risk_hint,
        generated_by="llm",
    )


def build_stock_news_graph(db: Session, symbol: str, *, days: int = 7, limit: int = 18) -> NewsGraphOut:
    normalized_symbol = str(symbol or "").strip().upper()
    target_days = max(1, min(int(days), 30))
    target_limit = max(5, min(int(limit), MAX_NEWS_ITEMS))
    center = _resolve_stock_center(db, normalized_symbol)
    center_sector = normalize_sector_name(center.get("sector"), market=center.get("market"))
    start_date = date.today() - timedelta(days=target_days - 1)
    start_at = datetime.combine(start_date, time.min).replace(tzinfo=None)

    news_rows = _nearby_news_query(
        db,
        symbol=normalized_symbol,
        sector=center_sector,
        start_at=start_at,
        limit=target_limit,
    )
    events = _nearby_event_rows(db, symbol=normalized_symbol, start_date=start_date)

    theme_counter: Counter[str] = Counter()
    peer_counter: Counter[str] = Counter()
    for item in news_rows:
        theme_counter.update(item.themes)
        for peer in item.related_symbols:
            if peer != normalized_symbol:
                peer_counter.update([peer])
    allowed_themes = {item for item, _ in theme_counter.most_common(MAX_THEME_NODES)}
    allowed_peers = {item for item, _ in peer_counter.most_common(MAX_PEER_NODES)}

    nodes: dict[str, NewsGraphNodeOut] = {}
    edges: dict[tuple[str, str, str], NewsGraphEdgeOut] = {}

    _add_node(
        nodes,
        NewsGraphNodeOut(
            id=f"stock:{normalized_symbol}",
            type="stock",
            label=f"{center.get('name') or normalized_symbol} ({normalized_symbol})",
            size=58,
            metadata={
                "symbol": normalized_symbol,
                "name": center.get("name") or normalized_symbol,
                "market": center.get("market") or "",
                "sector": center_sector,
            },
        ),
    )
    if center_sector and center_sector != UNKNOWN_SECTOR:
        _add_node(
            nodes,
            NewsGraphNodeOut(
                id=f"sector:{center_sector}",
                type="sector",
                label=center_sector,
                size=34,
                metadata={"sector": center_sector},
            ),
        )
        _add_edge(
            edges,
            NewsGraphEdgeOut(
                source=f"stock:{normalized_symbol}",
                target=f"sector:{center_sector}",
                type="belongs_to",
                weight=1.0,
                label="belongs_to",
            ),
        )

    event_links: defaultdict[int, list[int]] = defaultdict(list)
    for item in events:
        node_id = f"event:{int(item.id)}"
        _add_node(
            nodes,
            NewsGraphNodeOut(
                id=node_id,
                type="event",
                label=_truncate(str(item.title or str(item.type or "event")), 30),
                size=26,
                metadata={
                    "event_id": int(item.id),
                    "symbol": str(item.symbol or ""),
                    "type": str(item.type or ""),
                    "date": item.date.isoformat() if item.date else None,
                    "title": str(item.title or ""),
                    "link": item.link,
                    "source": item.source,
                },
            ),
        )
        _add_edge(
            edges,
            NewsGraphEdgeOut(
                source=node_id,
                target=f"stock:{normalized_symbol}",
                type="event_of",
                weight=0.95,
                label=str(item.type or "event"),
            ),
        )

    for item in news_rows:
        news_id = int(item.id)
        news_node_id = f"news:{news_id}"
        direct_hit = normalized_symbol == str(item.symbol or "").upper() or normalized_symbol in item.related_symbols
        _add_node(
            nodes,
            NewsGraphNodeOut(
                id=news_node_id,
                type="news",
                label=_truncate(str(item.title or ""), 30),
                size=30 if direct_hit else 24,
                sentiment=item.sentiment,
                metadata={
                    "news_id": news_id,
                    "title": str(item.title or ""),
                    "symbol": str(item.symbol or ""),
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                    "link": item.link,
                    "source": item.source_site or item.source,
                    "event_type": item.event_type,
                    "impact_direction": item.impact_direction,
                    "themes": item.themes,
                    "keywords": item.keywords,
                },
            ),
        )
        if direct_hit:
            _add_edge(
                edges,
                NewsGraphEdgeOut(
                    source=news_node_id,
                    target=f"stock:{normalized_symbol}",
                    type="mentions",
                    weight=1.0,
                    label=item.impact_direction or item.sentiment,
                ),
            )
        for sector in item.related_sectors[:3]:
            _add_node(
                nodes,
                NewsGraphNodeOut(
                    id=f"sector:{sector}",
                    type="sector",
                    label=sector,
                    size=28 if sector == center_sector else 24,
                    metadata={"sector": sector},
                ),
            )
            _add_edge(
                edges,
                NewsGraphEdgeOut(
                    source=news_node_id,
                    target=f"sector:{sector}",
                    type="relates_sector",
                    weight=0.78 if sector == center_sector else 0.6,
                    label="sector",
                ),
            )
        for theme in item.themes:
            if theme not in allowed_themes:
                continue
            _add_node(
                nodes,
                NewsGraphNodeOut(
                    id=f"theme:{theme}",
                    type="theme",
                    label=theme,
                    size=22,
                    metadata={"theme": theme},
                ),
            )
            _add_edge(
                edges,
                NewsGraphEdgeOut(
                    source=news_node_id,
                    target=f"theme:{theme}",
                    type="has_theme",
                    weight=0.62,
                    label="theme",
                ),
            )
        for peer in item.related_symbols:
            if peer == normalized_symbol or peer not in allowed_peers:
                continue
            peer_meta = _stock_lookup(peer)
            _add_node(
                nodes,
                NewsGraphNodeOut(
                    id=f"stock:{peer}",
                    type="stock",
                    label=f"{peer_meta.get('name') or peer} ({peer})",
                    size=24,
                    metadata={
                        "symbol": peer,
                        "name": peer_meta.get("name") or peer,
                        "market": peer_meta.get("market") or "",
                        "sector": normalize_sector_name(peer_meta.get("sector"), market=peer_meta.get("market")),
                    },
                ),
            )
            _add_edge(
                edges,
                NewsGraphEdgeOut(
                    source=news_node_id,
                    target=f"stock:{peer}",
                    type="mentions_peer",
                    weight=0.58,
                    label="peer",
                ),
            )
        if item.published_at is None:
            continue
        for event_item in events:
            if event_item.date is None:
                continue
            if abs((item.published_at.date() - event_item.date).days) > 3:
                continue
            event_node_id = f"event:{int(event_item.id)}"
            _add_edge(
                edges,
                NewsGraphEdgeOut(
                    source=news_node_id,
                    target=event_node_id,
                    type="cooccurs_event",
                    weight=0.66,
                    label="nearby_event",
                ),
            )
            event_links[int(event_item.id)].append(news_id)

    peer_labels = [nodes[f"stock:{peer}"].metadata.get("name") or peer for peer in allowed_peers if f"stock:{peer}" in nodes]
    theme_labels = [theme for theme, _ in theme_counter.most_common(MAX_THEME_NODES)]
    fallback_explanation = _build_template_explanation(
        center_label=center.get("name") or normalized_symbol,
        days=target_days,
        sector=center_sector,
        news_rows=news_rows,
        events=events,
        themes=theme_labels,
        peers=[str(item) for item in peer_labels],
    )
    explanation = _build_llm_explanation(
        center_label=center.get("name") or normalized_symbol,
        days=target_days,
        sector=center_sector,
        news_rows=news_rows,
        events=events,
        themes=theme_labels,
        peers=[str(item) for item in peer_labels],
        fallback=fallback_explanation,
    )
    related_news = serialize_news_items(news_rows)
    related_events = [_event_payload(item) for item in events]
    propagation_chains, impact_chains = _build_stock_graph_chains(
        symbol=normalized_symbol,
        center_name=str(center.get("name") or normalized_symbol),
        center_sector=center_sector,
        news_rows=news_rows,
        events=events,
        allowed_peers=allowed_peers,
    )
    symbol_entities = [
        _build_entity(
            entity_id=f"stock:{normalized_symbol}",
            entity_type="stock",
            label=_format_stock_label(normalized_symbol, str(center.get("name") or normalized_symbol)),
        )
    ]
    sector_entities: list[NewsGraphEntityOut] = []
    if center_sector and center_sector != UNKNOWN_SECTOR:
        sector_entities.append(
            _build_entity(
                entity_id=f"sector:{center_sector}",
                entity_type="sector",
                label=center_sector,
            )
        )
    for peer in allowed_peers:
        peer_node = nodes.get(f"stock:{peer}")
        if peer_node is None:
            continue
        symbol_entities.append(
            _build_entity(
                entity_id=peer_node.id,
                entity_type=peer_node.type,
                label=peer_node.label,
                sentiment=peer_node.sentiment,
            )
        )
    for item in news_rows:
        for sector in item.related_sectors[:3]:
            sector_entities.append(
                _build_entity(
                    entity_id=f"sector:{sector}",
                    entity_type="sector",
                    label=sector,
                )
            )
    impact_summary = _build_impact_summary(
        news_rows=news_rows,
        events=events,
        propagation_chains=propagation_chains,
        impact_chains=impact_chains,
        symbol_entities=symbol_entities,
        sector_entities=sector_entities,
    )
    return NewsGraphOut(
        center_type="stock",
        center_id=normalized_symbol,
        center_label=center.get("name") or normalized_symbol,
        days=target_days,
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        explanation=explanation,
        related_news=related_news,
        related_events=related_events,
        propagation_chains=propagation_chains,
        impact_chains=impact_chains,
        impact_summary=impact_summary,
    )


def build_news_focus_graph(db: Session, news_id: int, *, days: int = 7, limit: int = 10) -> NewsGraphOut | None:
    row = with_news_relations(db.query(News)).filter(News.id == news_id).first()
    if row is None:
        return None
    center_label = _truncate(str(row.title or f"news:{news_id}"), 36)
    target_days = max(1, min(int(days), 30))
    start_at = (row.published_at or datetime.now(UTC).replace(tzinfo=None)) - timedelta(days=target_days)

    related_symbols = row.related_symbols[: MAX_PEER_NODES + 1]
    related_sectors = row.related_sectors[:3]
    themes = row.themes[: MAX_THEME_NODES]
    nearby_news = _nearby_focus_news_query(
        db,
        center_news=row,
        start_at=start_at,
        limit=limit,
    )

    nodes: dict[str, NewsGraphNodeOut] = {}
    edges: dict[tuple[str, str, str], NewsGraphEdgeOut] = {}
    center_node_id = f"news:{news_id}"
    _add_node(
        nodes,
        NewsGraphNodeOut(
            id=center_node_id,
            type="news",
            label=center_label,
            size=54,
            sentiment=row.sentiment,
            metadata={
                "news_id": int(row.id),
                "title": str(row.title or ""),
                "symbol": str(row.symbol or ""),
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "link": row.link,
                "source": row.source_site or row.source,
                "event_type": row.event_type,
                "impact_direction": row.impact_direction,
                "themes": row.themes,
                "keywords": row.keywords,
            },
        ),
    )

    for symbol in related_symbols:
        stock_meta = _stock_lookup(symbol)
        _add_node(
            nodes,
            NewsGraphNodeOut(
                id=f"stock:{symbol}",
                type="stock",
                label=f"{stock_meta.get('name') or symbol} ({symbol})",
                size=28,
                metadata=stock_meta,
            ),
        )
        _add_edge(
            edges,
            NewsGraphEdgeOut(
                source=center_node_id,
                target=f"stock:{symbol}",
                type="mentions",
                weight=1.0,
                label="mentions",
            ),
        )
    for sector in related_sectors:
        _add_node(
            nodes,
            NewsGraphNodeOut(
                id=f"sector:{sector}",
                type="sector",
                label=sector,
                size=24,
                metadata={"sector": sector},
            ),
        )
        _add_edge(
            edges,
            NewsGraphEdgeOut(
                source=center_node_id,
                target=f"sector:{sector}",
                type="relates_sector",
                weight=0.74,
                label="sector",
            ),
        )
    for theme in themes:
        _add_node(
            nodes,
            NewsGraphNodeOut(
                id=f"theme:{theme}",
                type="theme",
                label=theme,
                size=20,
                metadata={"theme": theme},
            ),
        )
        _add_edge(
            edges,
            NewsGraphEdgeOut(
                source=center_node_id,
                target=f"theme:{theme}",
                type="has_theme",
                weight=0.6,
                label="theme",
            ),
        )
    for item in nearby_news:
        nearby_node_id = f"news:{int(item.id)}"
        _add_node(
            nodes,
            NewsGraphNodeOut(
                id=nearby_node_id,
                type="news",
                label=_truncate(str(item.title or ""), 28),
                size=24,
                sentiment=item.sentiment,
                metadata={
                    "news_id": int(item.id),
                    "title": str(item.title or ""),
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                    "link": item.link,
                    "source": item.source_site or item.source,
                },
            ),
        )
        _add_edge(
            edges,
            NewsGraphEdgeOut(
                source=center_node_id,
                target=nearby_node_id,
                type="related_news",
                weight=0.56,
                label="related",
            ),
        )

    fallback = NewsGraphExplanationOut(
        headline=f"这条新闻主要影响 {len(related_symbols)} 个标的，并与 {len(nearby_news)} 条近邻新闻形成传播关系。",
        evidence=[
            f"关联个股: {'、'.join(related_symbols[:4]) or '无'}。",
            f"关联板块: {'、'.join(related_sectors[:3]) or '无'}。",
        ],
        risk_hint="若后续同主题新闻继续增多，传播影响范围可能进一步扩大。" if nearby_news else None,
        generated_by="template",
    )
    explanation = _build_llm_explanation(
        center_label=str(row.title or f"news:{news_id}"),
        days=target_days,
        sector="、".join(related_sectors),
        news_rows=[row, *nearby_news],
        events=[],
        themes=themes,
        peers=related_symbols,
        fallback=fallback,
    )
    propagation_chains, impact_chains = _build_focus_graph_chains(
        center_news=row,
        nearby_news=nearby_news,
        related_symbols=related_symbols,
        related_sectors=related_sectors,
    )
    symbol_entities: list[NewsGraphEntityOut] = []
    for symbol in related_symbols:
        stock_meta = _stock_lookup(symbol)
        symbol_entities.append(
            _build_entity(
                entity_id=f"stock:{symbol}",
                entity_type="stock",
                label=_format_stock_label(symbol, str(stock_meta.get("name") or symbol)),
            )
        )
    for item in nearby_news:
        for symbol in item.related_symbols[:2]:
            stock_meta = _stock_lookup(symbol)
            symbol_entities.append(
                _build_entity(
                    entity_id=f"stock:{symbol}",
                    entity_type="stock",
                    label=_format_stock_label(symbol, str(stock_meta.get("name") or symbol)),
                )
            )
    sector_entities = [
        _build_entity(
            entity_id=f"sector:{sector}",
            entity_type="sector",
            label=sector,
        )
        for sector in related_sectors
    ]
    for item in nearby_news:
        for sector in item.related_sectors[:2]:
            sector_entities.append(
                _build_entity(
                    entity_id=f"sector:{sector}",
                    entity_type="sector",
                    label=sector,
                )
            )
    impact_summary = _build_impact_summary(
        news_rows=nearby_news,
        events=[],
        propagation_chains=propagation_chains,
        impact_chains=impact_chains,
        symbol_entities=symbol_entities,
        sector_entities=sector_entities,
    )
    return NewsGraphOut(
        center_type="news",
        center_id=str(news_id),
        center_label=str(row.title or f"news:{news_id}"),
        days=target_days,
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        explanation=explanation,
        related_news=serialize_news_items(nearby_news),
        related_events=[],
        propagation_chains=propagation_chains,
        impact_chains=impact_chains,
        impact_summary=impact_summary,
    )
