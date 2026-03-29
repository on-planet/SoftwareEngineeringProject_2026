from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re

from etl.fetchers.snowball_client import normalize_symbol
from etl.utils.sector_taxonomy import UNKNOWN_SECTOR, normalize_sector_name
from etl.utils.stock_basics_cache import load_stock_basics_cache

COMPANY_SUFFIX_RE = re.compile(
    r"(股份有限公司|控股有限公司|集团股份有限公司|集团有限公司|股份公司|有限公司|集团)$"
)
STOCK_CODE_RE = re.compile(r"\b(?:\d{6}\.(?:SH|SZ)|\d{5}\.HK|[A-Z]{1,6}\.US)\b")

HARDCODED_SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "00700.HK": ("腾讯", "tencent"),
    "09988.HK": ("阿里", "阿里巴巴", "alibaba", "淘宝", "天猫"),
    "01810.HK": ("小米", "xiaomi"),
    "03690.HK": ("美团", "meituan"),
    "01211.HK": ("比亚迪", "byd"),
    "002594.SZ": ("比亚迪", "byd"),
    "300750.SZ": ("宁德时代", "catl"),
    "600519.SH": ("茅台", "贵州茅台", "moutai"),
    "601318.SH": ("中国平安", "平安保险", "ping an"),
    "601398.SH": ("工商银行", "icbc"),
    "601857.SH": ("中国石油", "petrochina"),
    "601899.SH": ("紫金矿业", "zijin"),
    "600036.SH": ("招商银行", "cmb", "china merchants bank"),
    "NVDA.US": ("英伟达", "nvidia"),
    "AAPL.US": ("苹果", "apple"),
    "TSLA.US": ("特斯拉", "tesla"),
    "MSFT.US": ("微软", "microsoft"),
    "GOOGL.US": ("谷歌", "google", "alphabet"),
    "AMZN.US": ("亚马逊", "amazon"),
    "META.US": ("meta", "facebook", "脸书"),
}

SECTOR_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("科技", ("ai", "人工智能", "半导体", "芯片", "云计算", "算力", "服务器", "软件", "科技股", "nvidia")),
    ("金融", ("银行", "券商", "保险", "fintech", "资本市场", "信用", "利率", "美联储", "央行")),
    ("能源材料", ("原油", "油价", "天然气", "黄金", "白银", "铜", "铝", "煤炭", "有色", "大宗商品", "矿业")),
    ("工业制造", ("汽车", "新能源车", "机器人", "制造业", "工业", "物流", "航运", "航空")),
    ("消费", ("消费", "零售", "白酒", "啤酒", "食品", "饮料", "电商", "旅游", "酒店")),
    ("医疗健康", ("医药", "医疗", "创新药", "生物科技", "biotech", "pharma")),
    ("房地产", ("地产", "房地产", "楼市", "物业", "房价", "土地市场")),
    ("公用事业", ("电力", "水务", "燃气", "核电", "光伏", "风电", "utility")),
]

THEME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("AI", ("ai", "人工智能", "大模型", "模型训练", "算力", "服务器", "gpu")),
    ("半导体", ("半导体", "芯片", "晶圆", "封测", "光刻", "存储")),
    ("云计算", ("云计算", "云服务", "saas", "paas", "iaas", "数据中心")),
    ("新能源车", ("新能源车", "电动车", "汽车智能化", "自动驾驶", "充电桩")),
    ("锂电", ("锂电", "电池", "储能", "正极", "负极", "隔膜")),
    ("黄金", ("黄金", "金价", "避险资产")),
    ("原油", ("原油", "油价", "布伦特", "wti")),
    ("人民币汇率", ("人民币", "汇率", "离岸人民币", "美元兑人民币")),
    ("美债利率", ("美债", "国债收益率", "收益率上行", "收益率下行")),
    ("消费复苏", ("消费复苏", "社零", "零售恢复", "客流恢复")),
]


@dataclass(frozen=True)
class EntityExtractionResult:
    related_symbols: list[str]
    related_sectors: list[str]
    themes: list[str]
    keywords: list[str]


def _normalize_text(value: str) -> tuple[str, str]:
    raw = str(value or "").strip()
    lowered = raw.lower()
    return raw, lowered


def _clean_company_name(value: str) -> str:
    text = str(value or "").strip()
    text = COMPANY_SUFFIX_RE.sub("", text)
    return text.strip()


def _add_alias(mapping: dict[str, set[str]], alias: str, symbol: str) -> None:
    text = str(alias or "").strip().lower()
    if not text:
        return
    if len(text) < 2:
        return
    if text.isascii() and len(text) < 3:
        return
    mapping.setdefault(text, set()).add(symbol)


@lru_cache(maxsize=1)
def _alias_lookup() -> tuple[tuple[str, tuple[str, ...]], ...]:
    mapping: dict[str, set[str]] = {}
    for row in load_stock_basics_cache():
        symbol = normalize_symbol(str(row.get("symbol") or ""))
        if not symbol:
            continue
        name = str(row.get("name") or "").strip()
        aliases = {name, _clean_company_name(name), symbol}
        aliases.update(HARDCODED_SYMBOL_ALIASES.get(symbol, ()))
        for alias in aliases:
            _add_alias(mapping, alias, symbol)
    items = [(alias, tuple(sorted(symbols))) for alias, symbols in mapping.items()]
    items.sort(key=lambda item: (-len(item[0]), item[0]))
    return tuple(items)


@lru_cache(maxsize=1)
def _symbol_sector_lookup() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in load_stock_basics_cache():
        symbol = normalize_symbol(str(row.get("symbol") or ""))
        if not symbol:
            continue
        sector = normalize_sector_name(row.get("sector"), market=row.get("market"))
        if sector and sector != UNKNOWN_SECTOR:
            mapping[symbol] = sector
    return mapping


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


def extract_related_symbols(text: str, *, seed_symbol: str | None = None, max_items: int = 6) -> tuple[list[str], list[str]]:
    raw, lowered = _normalize_text(text)
    results: list[str] = []
    keywords: list[str] = []
    normalized_seed = normalize_symbol(seed_symbol or "")
    if normalized_seed:
        results.append(normalized_seed)

    for matched in STOCK_CODE_RE.findall(raw.upper()):
        symbol = normalize_symbol(matched)
        if symbol and symbol not in results:
            results.append(symbol)
            keywords.append(matched)

    for alias, symbols in _alias_lookup():
        if alias not in lowered:
            continue
        if len(symbols) == 1:
            symbol = symbols[0]
        elif normalized_seed and normalized_seed in symbols:
            symbol = normalized_seed
        else:
            continue
        if symbol not in results:
            results.append(symbol)
        if alias not in keywords:
            keywords.append(alias)
        if len(results) >= max_items:
            break

    return _dedupe(results)[:max_items], _dedupe(keywords)[: max_items * 2]


def extract_related_sectors(text: str, *, symbols: list[str] | None = None) -> tuple[list[str], list[str]]:
    _, lowered = _normalize_text(text)
    sectors: list[str] = []
    keywords: list[str] = []
    sector_lookup = _symbol_sector_lookup()
    for symbol in symbols or []:
        sector = sector_lookup.get(symbol)
        if sector and sector not in sectors:
            sectors.append(sector)
    for sector_name, words in SECTOR_KEYWORDS:
        for word in words:
            if word.lower() in lowered:
                if sector_name not in sectors:
                    sectors.append(sector_name)
                if word not in keywords:
                    keywords.append(word)
                break
    return _dedupe(sectors), _dedupe(keywords)


def extract_themes(text: str) -> tuple[list[str], list[str]]:
    _, lowered = _normalize_text(text)
    themes: list[str] = []
    keywords: list[str] = []
    for theme, words in THEME_KEYWORDS:
        for word in words:
            if word.lower() in lowered:
                if theme not in themes:
                    themes.append(theme)
                if word not in keywords:
                    keywords.append(word)
                break
    return _dedupe(themes), _dedupe(keywords)


def extract_entities(text: str, *, seed_symbol: str | None = None) -> EntityExtractionResult:
    symbols, symbol_keywords = extract_related_symbols(text, seed_symbol=seed_symbol)
    sectors, sector_keywords = extract_related_sectors(text, symbols=symbols)
    themes, theme_keywords = extract_themes(text)
    keywords = _dedupe(symbol_keywords + sector_keywords + theme_keywords)[:10]
    return EntityExtractionResult(
        related_symbols=symbols,
        related_sectors=sectors,
        themes=themes,
        keywords=keywords,
    )
