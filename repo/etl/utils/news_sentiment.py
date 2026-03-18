from __future__ import annotations

import re

# Chinese rules run on compact text (spaces removed), so both trad/simp forms are covered.
POSITIVE_COMPACT_RULES: list[tuple[str, int]] = [
    (r"(\u8d85|\u8d85\u51fa|\u512a\u65bc|\u4f18\u4e8e)?\u9810\u671f|(\u8d85|\u8d85\u51fa|\u4f18\u4e8e)?\u9884\u671f", 3),
    (r"\u4e0a\u8abf|\u4e0a\u8c03|\u8abf\u5347|\u8c03\u5347|\u8cb7\u5165|\u4e70\u5165|\u589e\u6301|\u770b\u597d", 2),
    (r"\u76c8\u5229|\u7372\u5229|\u83b7\u5229|\u626d\u8667\u70ba\u76c8|\u626d\u4e8f\u4e3a\u76c8", 2),
    (r"\u6de8\u5229\u6f64\u589e\u9577|\u51c0\u5229\u6da6\u589e\u957f|\u696d\u7e3e\u589e\u9577|\u4e1a\u7ee9\u589e\u957f", 2),
    (r"\u56de\u8cfc|\u56de\u8d2d|\u5206\u7d05|\u5206\u7ea2|\u6d3e\u606f", 2),
    (r"\u4e0a\u6f32|\u4e0a\u6da8|\u6f32\u52e2|\u6da8\u52bf|\u8d70\u5f37|\u8d70\u5f3a|\u53cd\u5f48|\u53cd\u5f39", 1),
    (r"\u62c9\u5347|\u8d70\u9ad8|\u5927\u6f32|\u5927\u6da8|\u98c6\u6f32|\u98d9\u6da8|\u7a81\u7834|\u5275\u65b0\u9ad8|\u521b\u65b0\u9ad8|\u65b0\u9ad8", 1),
]

NEGATIVE_COMPACT_RULES: list[tuple[str, int]] = [
    (r"\u4e0d\u53ca\u9810\u671f|\u4e0d\u53ca\u9884\u671f|\u4f4e\u65bc\u9810\u671f|\u4f4e\u4e8e\u9884\u671f", 3),
    (r"\u4e0b\u8abf|\u4e0b\u8c03|\u8abf\u964d|\u8c03\u964d|\u6e1b\u6301|\u51cf\u6301", 2),
    (r"\u8667\u640d|\u4e8f\u635f|\u6de8\u5229\u6f64\u4e0b\u6ed1|\u51c0\u5229\u6da6\u4e0b\u6ed1|\u696d\u7e3e\u4e0b\u6ed1|\u4e1a\u7ee9\u4e0b\u6ed1", 2),
    (r"\u9055\u7d04|\u8fdd\u7ea6|\u7206\u96f7|\u7acb\u6848|\u8655\u7f70|\u5904\u7f5a|\u88ab\u67e5|\u505c\u724c|\u9000\u5e02", 2),
    (r"\u4e0b\u8dcc|\u8d70\u5f31|\u56de\u843d|\u8df3\u6c34|\u7ffb\u9ed1|\u4e0b\u632b|\u5927\u8dcc|\u66b4\u8dcc", 1),
    (r"\u88c1\u54e1|\u88c1\u5458|\u7834\u7522|\u7834\u4ea7|\u95dc\u505c|\u5173\u505c|\u7206\u5009|\u7206\u4ed3", 1),
]

# English rules run on raw lower-cased text with spaces preserved.
POSITIVE_RAW_RULES: list[tuple[str, int]] = [
    (r"\bbeat(s|ing)?\b.{0,24}\bexpect", 3),
    (r"\b(upgrade(d)?|raises?|raised|boosts?|boosted)\b.{0,24}\b(target|guidance|forecast|outlook|rating)\b", 2),
    (r"\b(outperform|overweight|buy rating|maintains? buy)\b", 2),
    (r"\b(profit|earnings?|revenue)\b.{0,24}\b(grow(th)?|rise(s|n)?|jump(s|ed)?|increase(s|d)?|surge(s|d)?)\b", 2),
    (r"\b(buyback|share repurchase|repurchase program|dividend)\b", 2),
    (r"\b(rise(s|n)?|gain(s|ed)?|rally|surge(s|d)?|soar(s|ed)?|rebound(s|ed)?)\b", 1),
]

NEGATIVE_RAW_RULES: list[tuple[str, int]] = [
    (r"\bmiss(es|ed)?\b.{0,24}\bexpect", 3),
    (r"\b(downgrade(d)?|cuts?|cut|lower(s|ed)?)\b.{0,24}\b(target|guidance|forecast|outlook|rating)\b", 2),
    (r"\b(underperform|underweight|sell rating)\b", 2),
    (r"\b(loss(es)?|unprofitable|earnings decline|profit warning|warning)\b", 2),
    (r"\b(default|bankrupt(cy)?|fraud|probe|investigation|lawsuit|penalty|delist(ed|ing)?)\b", 2),
    (r"\b(fall(s|en)?|drop(s|ped)?|plunge(s|d)?|slump(s|ed)?)\b", 1),
    (r"\b(layoff(s)?|shutdown|closure)\b", 1),
]

NEUTRAL_HINTS: tuple[str, ...] = (
    r"\u95e2\u8b20|\u8f9f\u8c23",  # rumor denial
    r"\u6f84\u6e05",
    r"\u50b3\u805e|\u4f20\u95fb|\brumou?r\b",
    r"\u6216\u5c07|\u6216\u5c06|\bmay\b|\bplan(s|ned)?\b",
)

UP_DOWN_MIX_PATTERN = re.compile(
    r"(\u4e0a\u6f32|\u4e0a\u6da8|\u8d70\u5f37|\u8d70\u5f3a|rise|gain).{0,10}(\u4e0b\u8dcc|\u8d70\u5f31|fall|drop)|"
    r"(\u4e0b\u8dcc|\u8d70\u5f31|fall|drop).{0,10}(\u4e0a\u6f32|\u4e0a\u6da8|\u8d70\u5f37|\u8d70\u5f3a|rise|gain)",
    re.IGNORECASE,
)


def _normalize_texts(text: str) -> tuple[str, str]:
    raw = str(text or "").strip().lower()
    raw = re.sub(r"\s+", " ", raw)
    compact = raw.replace(" ", "")
    return raw, compact


def _score_with_rules(text: str, rules: list[tuple[str, int]]) -> int:
    score = 0
    for pattern, weight in rules:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if not matches:
            continue
        score += min(len(matches), 2) * weight
    return score


def infer_news_sentiment(
    title: str,
    *,
    source: str | None = None,
    topic_category: str | None = None,
) -> str:
    raw_text, compact_text = _normalize_texts(title)
    if not compact_text:
        return "neutral"

    positive_score = _score_with_rules(compact_text, POSITIVE_COMPACT_RULES) + _score_with_rules(raw_text, POSITIVE_RAW_RULES)
    negative_score = _score_with_rules(compact_text, NEGATIVE_COMPACT_RULES) + _score_with_rules(raw_text, NEGATIVE_RAW_RULES)

    if UP_DOWN_MIX_PATTERN.search(compact_text) and abs(positive_score - negative_score) <= 2:
        return "neutral"

    if any(re.search(pattern, raw_text, flags=re.IGNORECASE) for pattern in NEUTRAL_HINTS):
        if abs(positive_score - negative_score) <= 1:
            return "neutral"

    if str(topic_category or "") == "market_flash":
        if positive_score - negative_score >= 3:
            return "positive"
        if negative_score - positive_score >= 3:
            return "negative"
        return "neutral"

    score = positive_score - negative_score
    if score >= 2:
        return "positive"
    if score <= -2:
        return "negative"
    return "neutral"
