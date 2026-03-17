from __future__ import annotations

from functools import lru_cache

from etl.utils.sector_taxonomy import UNKNOWN_SECTOR, normalize_sector_name
from etl.utils.stock_basics_cache import load_stock_basics_cache

SECTOR_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("科技", ("ai", "人工智能", "半导体", "芯片", "云计算", "算力", "服务器", "软件", "科技股", "nvidia", "英伟达")),
    ("金融", ("银行", "券商", "保险", "fintech", "资本市场", "信用", "利率", "美联储", "央行")),
    ("能源材料", ("原油", "油价", "天然气", "黄金", "白银", "铜", "铝", "煤炭", "有色", "大宗商品", "矿业")),
    ("工业制造", ("汽车", "新能源车", "机器人", "制造业", "工业", "物流", "航运", "船运", "航空")),
    ("消费", ("消费", "零售", "白酒", "啤酒", "食品", "饮料", "电商", "旅游", "酒店")),
    ("医疗健康", ("医药", "医疗", "创新药", "生物科技", "biotech", "pharma")),
    ("房地产", ("地产", "房地产", "楼市", "物业", "房价", "土地市场")),
    ("公用事业", ("电力", "水务", "燃气", "核电", "光伏", "风电", "utility")),
]

SYMBOL_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("00700.HK", ("腾讯", "tencent")),
    ("09988.HK", ("阿里", "alibaba", "淘宝", "天猫")),
    ("01810.HK", ("小米", "xiaomi")),
    ("03690.HK", ("美团", "meituan")),
    ("01211.HK", ("比亚迪", "byd")),
    ("002594.SZ", ("比亚迪", "byd")),
    ("300750.SZ", ("宁德时代", "catl")),
    ("600519.SH", ("茅台", "贵州茅台", "moutai")),
    ("601318.SH", ("中国平安", "平安保险", "ping an")),
    ("601398.SH", ("工商银行", "icbc")),
    ("601857.SH", ("中国石油", "petrochina")),
    ("601899.SH", ("紫金矿业", "zijin")),
    ("600036.SH", ("招商银行", "cmb", "china merchants bank")),
    ("NVDA.US", ("英伟达", "nvidia")),
    ("AAPL.US", ("苹果", "apple")),
    ("TSLA.US", ("特斯拉", "tesla")),
    ("MSFT.US", ("微软", "microsoft")),
    ("GOOGL.US", ("谷歌", "google", "alphabet")),
    ("AMZN.US", ("亚马逊", "amazon")),
    ("META.US", ("meta", "facebook", "脸书")),
]


def _contains_keyword(text: str, keyword: str) -> bool:
    return keyword in text


@lru_cache(maxsize=1)
def _symbol_sector_lookup() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in load_stock_basics_cache():
        symbol = str(row.get("symbol") or "").strip().upper()
        sector = normalize_sector_name(row.get("sector"), market=row.get("market"))
        if symbol and sector and sector != UNKNOWN_SECTOR:
            mapping[symbol] = sector
    return mapping


def infer_news_relevance(title: str, *, symbol: str | None = None) -> dict[str, str | None]:
    text = str(title or "").strip()
    lowered = text.lower()
    related_symbols: list[str] = []
    related_sectors: list[str] = []
    sector_lookup = _symbol_sector_lookup()

    normalized_symbol = str(symbol or "").strip().upper()
    if normalized_symbol and normalized_symbol != "ALL":
        related_symbols.append(normalized_symbol)
        sector = sector_lookup.get(normalized_symbol)
        if sector:
            related_sectors.append(sector)

    for mapped_symbol, keywords in SYMBOL_KEYWORDS:
        if any(_contains_keyword(lowered, keyword.lower()) for keyword in keywords):
            if mapped_symbol not in related_symbols:
                related_symbols.append(mapped_symbol)
            sector = sector_lookup.get(mapped_symbol)
            if sector and sector not in related_sectors:
                related_sectors.append(sector)

    for sector_name, keywords in SECTOR_KEYWORDS:
        if any(_contains_keyword(lowered, keyword.lower()) for keyword in keywords):
            if sector_name not in related_sectors:
                related_sectors.append(sector_name)

    return {
        "related_symbols": ",".join(related_symbols) if related_symbols else None,
        "related_sectors": ",".join(related_sectors) if related_sectors else None,
    }
