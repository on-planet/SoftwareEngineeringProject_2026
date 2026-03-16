from __future__ import annotations

import re

UNKNOWN_SECTOR = "未分类"
UNKNOWN_SECTOR_VALUES = {
    "",
    "unknown",
    "未知",
    "未分类",
    "其他",
    "其它",
    "n/a",
    "na",
    "none",
    "null",
}

_SECTOR_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("金融", ("银行", "证券", "保险", "信托", "金融", "finance", "fintech", "broker", "capital", "asset")),
    ("房地产", ("地产", "物业", "房地产", "real estate", "property", "reit")),
    ("医疗健康", ("医药", "医疗", "生物", "制药", "health", "healthcare", "biotech", "pharma", "medical")),
    ("消费", ("食品", "饮料", "白酒", "啤酒", "零售", "商贸", "家电", "服装", "旅游", "酒店", "餐饮", "consumer", "retail", "food", "beverage", "apparel", "ecommerce")),
    ("科技", ("软件", "信息技术", "互联网", "半导体", "芯片", "电子", "计算机", "ai", "cloud", "tech", "technology", "software", "semiconductor", "hardware", "electronics")),
    ("电信传媒", ("通信", "电信", "传媒", "广告", "娱乐", "游戏", "出版", "telecom", "media", "gaming", "entertainment")),
    ("工业制造", ("机械", "制造", "工业", "设备", "军工", "航空", "航天", "运输", "汽车", "工业品", "manufacturing", "industrial", "machinery", "auto", "defense", "logistics")),
    ("能源材料", ("石油", "化工", "煤炭", "有色", "钢铁", "材料", "金属", "采掘", "油气", "矿", "铝", "铜", "黄金", "白银", "energy", "materials", "oil", "gas", "coal", "chemical", "metal", "mining")),
    ("公用事业", ("电力", "燃气", "水务", "环保", "utility", "utilities", "power", "water", "gas", "environment")),
]


def normalize_sector_raw(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return UNKNOWN_SECTOR
    lowered = text.lower()
    if lowered in UNKNOWN_SECTOR_VALUES:
        return UNKNOWN_SECTOR
    text = re.sub(r"\s+", " ", text)
    text = text.replace("股份有限公司", "").strip()
    return text or UNKNOWN_SECTOR


def normalize_sector_name(value: str | None, *, market: str | None = None) -> str:
    text = normalize_sector_raw(value)
    if text == UNKNOWN_SECTOR:
        return UNKNOWN_SECTOR
    lowered = text.lower()
    for sector_name, keywords in _SECTOR_RULES:
        if any(keyword in text or keyword in lowered for keyword in keywords):
            return sector_name
    if market == "HK" and "地产" in text:
        return "房地产"
    return text


def is_unknown_sector(value: str | None) -> bool:
    return normalize_sector_raw(value) == UNKNOWN_SECTOR
