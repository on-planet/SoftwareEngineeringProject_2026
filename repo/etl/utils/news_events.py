from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class EventMatchResult:
    event_type: str | None
    event_tags: list[str]
    impact_hint: str | None
    score: int
    keywords: list[str]


@dataclass(frozen=True)
class EventRule:
    event_type: str
    impact_hint: str
    score: int
    tags: tuple[str, ...]
    patterns: tuple[str, ...]


EVENT_RULES: tuple[EventRule, ...] = (
    EventRule(
        event_type="earnings",
        impact_hint="positive",
        score=5,
        tags=("earnings", "beat", "guidance_up"),
        patterns=("业绩预增", "盈喜", "超预期", "扭亏为盈", "earnings beat", "raises guidance", "上调目标价"),
    ),
    EventRule(
        event_type="earnings",
        impact_hint="negative",
        score=5,
        tags=("earnings", "miss", "guidance_down"),
        patterns=("业绩预减", "盈警", "不及预期", "亏损", "profit warning", "earnings miss", "下调目标价"),
    ),
    EventRule(
        event_type="buyback",
        impact_hint="positive",
        score=4,
        tags=("buyback", "shareholder_return"),
        patterns=("回购", "回购计划", "股份回购", "share repurchase", "buyback"),
    ),
    EventRule(
        event_type="policy",
        impact_hint="positive",
        score=4,
        tags=("policy_support",),
        patterns=("政策支持", "补贴", "审批通过", "利好政策", "刺激计划", "stimulus", "税收优惠"),
    ),
    EventRule(
        event_type="policy",
        impact_hint="negative",
        score=4,
        tags=("policy_risk", "regulation"),
        patterns=("监管", "禁令", "限制出口", "限制销售", "tariff", "sanction", "ban"),
    ),
    EventRule(
        event_type="order",
        impact_hint="positive",
        score=4,
        tags=("order_win",),
        patterns=("中标", "拿下大单", "签订合同", "获得订单", "订单增长", "wins contract", "new order"),
    ),
    EventRule(
        event_type="product",
        impact_hint="positive",
        score=3,
        tags=("product_launch",),
        patterns=("新品发布", "发布新产品", "推出新平台", "launch", "unveil", "rollout"),
    ),
    EventRule(
        event_type="mna",
        impact_hint="positive",
        score=3,
        tags=("merger", "acquisition"),
        patterns=("并购", "收购", "资产重组", "merge", "acquire", "takeover"),
    ),
    EventRule(
        event_type="investigation",
        impact_hint="negative",
        score=5,
        tags=("investigation", "penalty"),
        patterns=("被查", "立案", "处罚", "罚款", "调查", "probe", "investigation", "penalty"),
    ),
    EventRule(
        event_type="litigation",
        impact_hint="negative",
        score=4,
        tags=("lawsuit", "dispute"),
        patterns=("诉讼", "仲裁", "纠纷", "lawsuit", "litigation", "arbitration"),
    ),
    EventRule(
        event_type="financing",
        impact_hint="negative",
        score=3,
        tags=("capital_raise",),
        patterns=("定增", "配股", "融资", "发债", "secondary offering", "share sale"),
    ),
    EventRule(
        event_type="fund_flow",
        impact_hint="positive",
        score=3,
        tags=("fund_inflow",),
        patterns=("北向资金净流入", "南向资金净流入", "资金流入", "inflow", "net buy"),
    ),
    EventRule(
        event_type="fund_flow",
        impact_hint="negative",
        score=3,
        tags=("fund_outflow",),
        patterns=("北向资金净流出", "南向资金净流出", "资金流出", "outflow", "net sell"),
    ),
    EventRule(
        event_type="research",
        impact_hint="positive",
        score=3,
        tags=("research_upgrade",),
        patterns=("买入评级", "增持评级", "上调评级", "upgrade", "outperform", "overweight"),
    ),
    EventRule(
        event_type="research",
        impact_hint="negative",
        score=3,
        tags=("research_downgrade",),
        patterns=("下调评级", "卖出评级", "downgrade", "underperform", "underweight"),
    ),
)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def classify_news_event(text: str) -> EventMatchResult:
    lowered = _normalize_text(text)
    best_rule: EventRule | None = None
    best_hits: list[str] = []
    event_tags: list[str] = []
    matched_keywords: list[str] = []
    best_score = 0

    for rule in EVENT_RULES:
        hits = [pattern for pattern in rule.patterns if pattern.lower() in lowered]
        if not hits:
            continue
        score = rule.score + len(hits) - 1
        if score > best_score:
            best_rule = rule
            best_hits = hits
            best_score = score
        for tag in rule.tags:
            if tag not in event_tags:
                event_tags.append(tag)
        for hit in hits:
            if hit not in matched_keywords:
                matched_keywords.append(hit)

    if best_rule is None:
        return EventMatchResult(
            event_type=None,
            event_tags=[],
            impact_hint=None,
            score=0,
            keywords=[],
        )

    event_tags = list(best_rule.tags) + [tag for tag in event_tags if tag not in best_rule.tags]
    return EventMatchResult(
        event_type=best_rule.event_type,
        event_tags=event_tags[:6],
        impact_hint=best_rule.impact_hint,
        score=best_score,
        keywords=(best_hits + [item for item in matched_keywords if item not in best_hits])[:8],
    )
