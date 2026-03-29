from __future__ import annotations

from dataclasses import dataclass
import re

from app.schemas.portfolio_stress import PortfolioScenarioImpactOut, PortfolioStressRuleIn
from app.services.portfolio_stress_service import clip_shock_pct, custom_rule_label


@dataclass(frozen=True)
class ScenarioRuleSeed:
    scope_type: str
    scope_value: str | None
    shock_pct: float


@dataclass(frozen=True)
class ScenarioImpactSeed:
    label: str
    direction: str
    rationale: str


@dataclass(frozen=True)
class ScenarioTemplate:
    code: str
    name: str
    description: str
    base_trigger: float
    trigger_unit: str
    keywords: tuple[str, ...]
    direction_keywords: tuple[str, ...]
    rules: tuple[ScenarioRuleSeed, ...]
    beneficiaries: tuple[ScenarioImpactSeed, ...]
    losers: tuple[ScenarioImpactSeed, ...]


@dataclass(frozen=True)
class ResolvedScenarioClause:
    text: str
    parser: str
    confidence: str
    headline: str
    explanation: str
    matched_template_code: str | None
    matched_template_name: str | None
    extracted_shock_pct: float | None
    extracted_bp: float | None
    rules: list[PortfolioStressRuleIn]
    beneficiaries: list[PortfolioScenarioImpactOut]
    losers: list[PortfolioScenarioImpactOut]


@dataclass(frozen=True)
class ResolvedScenarioBundle:
    matched_template_code: str | None
    matched_template_name: str | None
    matched_template_codes: list[str]
    matched_template_names: list[str]
    name: str
    description: str
    confidence: str
    extracted_shock_pct: float | None
    headline: str
    explanation: str
    clauses: list[ResolvedScenarioClause]
    rules: list[PortfolioStressRuleIn]
    beneficiaries: list[PortfolioScenarioImpactOut]
    losers: list[PortfolioScenarioImpactOut]


UP_WORDS = ("涨", "上涨", "上行", "走高", "走强", "反弹", "回暖", "修复", "改善", "利好", "benefit", "higher")
DOWN_WORDS = ("跌", "下跌", "下行", "走低", "走弱", "回落", "承压", "疲软", "恶化", "利空", "hurt", "lower")
QUAL_UP_WORDS = ("放松", "宽松", "松绑", "刺激", "托底", "支持", "缓和", "修复")
QUAL_DOWN_WORDS = ("收紧", "从严", "加码", "打压", "趋严", "整顿", "压制")
EXTRA_UP_WORDS = ("受益", "景气", "抬升", "修复", "改善", "回升")
EXTRA_DOWN_WORDS = ("拖累", "受压", "走弱", "回撤", "放缓", "恶化")

CLAUSE_SPLIT_RE = re.compile(r"(?:[,，;；。/\n+&]|(?:并且|而且|同时|以及|且|并|叠加|同时叠加|and|with))")
PERCENT_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*(?:%|pct|％)")
BP_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*(?:bp|bps|基点)")
SIGNED_NUMBER_RE = re.compile(r"([+-]\d+(?:\.\d+)?)")
RMB_WEAKER_RE = re.compile(r"(?:人民币|cny).{0,8}(?:贬值|走弱|走贬|跌破|破)")
RMB_STRONGER_RE = re.compile(r"(?:人民币|cny).{0,8}(?:升值|走强|走升|收复)")
USD_STRONGER_RE = re.compile(r"(?:美元|usd).{0,8}(?:走强|升值|反弹)")
USD_WEAKER_RE = re.compile(r"(?:美元|usd).{0,8}(?:走弱|贬值|回落)")

PHRASE_ALIAS_GROUPS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("美元走强", "usd走强", "美元升值", "美元反弹"), "人民币贬值"),
    (("美元走弱", "usd走弱", "美元贬值", "美元回落"), "人民币升值"),
    (("降准", "降息", "宽货币", "流动性宽松", "央行宽松"), "利率下行"),
    (("加息", "缩表", "流动性收紧", "央行收紧"), "利率上行"),
    (("地产松绑", "楼市松绑", "地产救市", "放开限购", "降首付", "降低首付"), "地产政策放松"),
    (("地产调控加码", "限购收紧", "地产从严", "地产打压"), "地产政策收紧"),
    (("内需回暖", "社零回暖", "消费修复", "消费改善", "需求复苏"), "消费复苏"),
    (("内需走弱", "内需疲软", "消费疲软", "消费疲弱", "社零走弱"), "消费走弱"),
    (("平台整改结束", "平台经济整改结束", "反垄断缓和", "监管缓和"), "科技监管放松"),
    (("平台监管加码", "监管加码", "反垄断趋严", "监管趋严"), "科技监管趋严"),
    (("外需修复", "订单回暖", "出口订单回暖", "海外需求修复"), "出口回暖"),
    (("外需走弱", "外需转弱", "订单下滑", "出口订单下滑"), "出口放缓"),
)

PERCENT_MAGNITUDE_HINTS: tuple[tuple[tuple[str, ...], float], ...] = (
    (("暴涨", "暴跌", "飙升", "跳水", "急跌", "急涨"), 0.12),
    (("大涨", "大跌", "大幅", "显著", "明显", "剧烈"), 0.08),
    (("走强", "走弱", "回暖", "修复", "承压", "改善", "放缓", "疲软"), 0.05),
    (("小幅", "温和", "轻微"), 0.03),
)

BP_MAGNITUDE_HINTS: tuple[tuple[tuple[str, ...], float], ...] = (
    (("大幅", "显著", "明显", "快速", "急剧"), 75.0),
    (("小幅", "温和"), 25.0),
)

MARKET_ALIASES = {
    "港股": "HK",
    "香港": "HK",
    "hk": "HK",
    "美股": "US",
    "美国": "US",
    "us": "US",
    "中概": "US",
    "中概股": "US",
    "a股": "A",
    "a-share": "A",
    "沪深": "A",
    "内地": "A",
}

SECTOR_ALIASES = {
    "金融": "金融",
    "银行": "金融",
    "券商": "金融",
    "保险": "金融",
    "科技": "科技",
    "互联网": "科技",
    "半导体": "科技",
    "芯片": "科技",
    "传媒": "电信传媒",
    "通信": "电信传媒",
    "电信": "电信传媒",
    "地产": "房地产",
    "房地产": "房地产",
    "消费": "消费",
    "零售": "消费",
    "医药": "医疗健康",
    "医疗": "医疗健康",
    "能源": "能源",
    "石油": "能源",
    "煤炭": "能源",
    "原材料": "原材料",
    "建材": "原材料",
    "运输": "交通运输",
    "物流": "交通运输",
    "航运": "交通运输",
    "航空": "航空旅游",
    "旅游": "航空旅游",
    "制造": "工业制造",
    "工业": "工业制造",
    "家电": "家居家电",
    "家居": "家居家电",
}

TEMPLATES: tuple[ScenarioTemplate, ...] = (
    ScenarioTemplate(
        code="oil_up",
        name="油价上行",
        description="将国际油价上行映射到能源受益、航空旅游和运输承压的组合情景。",
        base_trigger=0.08,
        trigger_unit="percent",
        keywords=("油价", "原油", "布油", "wti", "crude", "oil"),
        direction_keywords=("涨", "上涨", "上行", "飙升", "走高", "走强"),
        rules=(
            ScenarioRuleSeed("sector", "能源", 0.06),
            ScenarioRuleSeed("sector", "航空旅游", -0.05),
            ScenarioRuleSeed("sector", "交通运输", -0.03),
            ScenarioRuleSeed("sector", "工业制造", -0.02),
        ),
        beneficiaries=(
            ScenarioImpactSeed("能源", "benefit", "上游油气和资源品通常受益于油价抬升。"),
            ScenarioImpactSeed("油服链", "benefit", "资本开支改善时，油服和设备链的景气度通常同步回升。"),
        ),
        losers=(
            ScenarioImpactSeed("航空旅游", "hurt", "燃油成本上升会直接挤压航空和出行链利润。"),
            ScenarioImpactSeed("交通运输", "hurt", "物流和运输链的燃料成本弹性偏高。"),
            ScenarioImpactSeed("工业制造", "hurt", "部分制造环节会承受原材料和能源成本挤压。"),
        ),
    ),
    ScenarioTemplate(
        code="oil_down",
        name="油价回落",
        description="将国际油价回落映射到成本改善型行业受益、能源承压的组合情景。",
        base_trigger=0.08,
        trigger_unit="percent",
        keywords=("油价", "原油", "布油", "wti", "crude", "oil"),
        direction_keywords=("跌", "下跌", "回落", "走低", "跳水", "走弱"),
        rules=(
            ScenarioRuleSeed("sector", "能源", -0.05),
            ScenarioRuleSeed("sector", "航空旅游", 0.04),
            ScenarioRuleSeed("sector", "交通运输", 0.02),
            ScenarioRuleSeed("sector", "消费", 0.01),
        ),
        beneficiaries=(
            ScenarioImpactSeed("航空旅游", "benefit", "燃油成本回落通常改善航空和旅游链盈利。"),
            ScenarioImpactSeed("交通运输", "benefit", "运输链单位成本下降后，利润率更容易修复。"),
        ),
        losers=(
            ScenarioImpactSeed("能源", "hurt", "上游资源品价格回落通常压缩盈利空间。"),
        ),
    ),
    ScenarioTemplate(
        code="rmb_depreciation",
        name="人民币贬值",
        description="将人民币贬值映射到出口制造受益、航空和内需敏感板块承压的组合情景。",
        base_trigger=0.03,
        trigger_unit="percent",
        keywords=("人民币", "汇率", "usd/cny", "美元兑人民币", "rmb", "cny"),
        direction_keywords=("贬值", "走弱", "走贬", "depreciation", "weaker", "破"),
        rules=(
            ScenarioRuleSeed("sector", "工业制造", 0.03),
            ScenarioRuleSeed("sector", "科技", 0.03),
            ScenarioRuleSeed("sector", "家居家电", 0.03),
            ScenarioRuleSeed("sector", "航空旅游", -0.04),
            ScenarioRuleSeed("sector", "房地产", -0.02),
        ),
        beneficiaries=(
            ScenarioImpactSeed("出口制造", "benefit", "出口导向制造和家电链通常受益于汇率优势。"),
            ScenarioImpactSeed("科技硬件", "benefit", "电子和硬件出口链的换汇弹性通常更强。"),
        ),
        losers=(
            ScenarioImpactSeed("航空旅游", "hurt", "外币成本和出境需求弹性会使航空旅游更承压。"),
            ScenarioImpactSeed("房地产", "hurt", "外部流动性走弱时，地产和内需敏感板块通常偏弱。"),
        ),
    ),
    ScenarioTemplate(
        code="rmb_appreciation",
        name="人民币升值",
        description="将人民币升值映射到输入成本改善、出口链相对承压的组合情景。",
        base_trigger=0.03,
        trigger_unit="percent",
        keywords=("人民币", "汇率", "usd/cny", "美元兑人民币", "rmb", "cny"),
        direction_keywords=("升值", "走强", "appreciation", "stronger", "收复"),
        rules=(
            ScenarioRuleSeed("sector", "工业制造", -0.03),
            ScenarioRuleSeed("sector", "科技", -0.02),
            ScenarioRuleSeed("sector", "家居家电", -0.02),
            ScenarioRuleSeed("sector", "航空旅游", 0.03),
            ScenarioRuleSeed("sector", "消费", 0.01),
        ),
        beneficiaries=(
            ScenarioImpactSeed("航空旅游", "benefit", "汇率升值通常缓解航空旅游的外币成本压力。"),
            ScenarioImpactSeed("消费", "benefit", "进口成本改善通常利好部分消费链。"),
        ),
        losers=(
            ScenarioImpactSeed("出口制造", "hurt", "出口链的价格优势和换汇收益会相对减弱。"),
            ScenarioImpactSeed("科技硬件", "hurt", "海外收入占比较高的硬件链会承受汇兑压力。"),
        ),
    ),
    ScenarioTemplate(
        code="property_easing",
        name="地产政策放松",
        description="将地产政策放松映射到地产链和金融链修复的组合情景。",
        base_trigger=1.0,
        trigger_unit="qualitative",
        keywords=("地产", "房地产", "楼市", "property", "real estate"),
        direction_keywords=("放松", "宽松", "松绑", "刺激", "托底", "支持"),
        rules=(
            ScenarioRuleSeed("sector", "房地产", 0.06),
            ScenarioRuleSeed("sector", "原材料", 0.03),
            ScenarioRuleSeed("sector", "家居家电", 0.03),
            ScenarioRuleSeed("sector", "金融", 0.02),
        ),
        beneficiaries=(
            ScenarioImpactSeed("房地产", "benefit", "地产政策宽松通常直接改善地产销售和估值预期。"),
            ScenarioImpactSeed("建材家居", "benefit", "地产链回暖会向建材、家居和家电传导。"),
            ScenarioImpactSeed("金融", "benefit", "地产风险缓和时，金融链的风险偏好通常改善。"),
        ),
        losers=(),
    ),
    ScenarioTemplate(
        code="property_tightening",
        name="地产政策收紧",
        description="将地产政策收紧映射到地产链和金融链承压的组合情景。",
        base_trigger=1.0,
        trigger_unit="qualitative",
        keywords=("地产", "房地产", "楼市", "property", "real estate"),
        direction_keywords=("收紧", "从严", "加码", "打压", "趋严", "限购"),
        rules=(
            ScenarioRuleSeed("sector", "房地产", -0.06),
            ScenarioRuleSeed("sector", "原材料", -0.03),
            ScenarioRuleSeed("sector", "家居家电", -0.02),
            ScenarioRuleSeed("sector", "金融", -0.02),
        ),
        beneficiaries=(),
        losers=(
            ScenarioImpactSeed("房地产", "hurt", "地产政策收紧通常压制地产链景气和风险偏好。"),
            ScenarioImpactSeed("建材家居", "hurt", "地产后周期链条通常会同步走弱。"),
            ScenarioImpactSeed("金融", "hurt", "地产风险上升时，金融和信用链也更容易承压。"),
        ),
    ),
    ScenarioTemplate(
        code="rate_up",
        name="利率上行",
        description="将利率或收益率上行映射到成长和利率敏感资产承压、金融相对受益的组合情景。",
        base_trigger=50.0,
        trigger_unit="bp",
        keywords=("利率", "收益率", "美债", "国债", "rate", "yield"),
        direction_keywords=("上行", "走高", "抬升", "加息", "bp+", "bps+", "收紧"),
        rules=(
            ScenarioRuleSeed("sector", "金融", 0.01),
            ScenarioRuleSeed("sector", "科技", -0.05),
            ScenarioRuleSeed("sector", "电信传媒", -0.04),
            ScenarioRuleSeed("sector", "房地产", -0.05),
            ScenarioRuleSeed("sector", "公用事业", -0.03),
            ScenarioRuleSeed("sector", "医疗健康", -0.03),
        ),
        beneficiaries=(
            ScenarioImpactSeed("金融", "benefit", "净息差和资产端收益预期改善时，金融板块通常更抗压。"),
        ),
        losers=(
            ScenarioImpactSeed("科技成长", "hurt", "高估值成长资产对贴现率变化更敏感。"),
            ScenarioImpactSeed("房地产", "hurt", "融资和估值两端都会对利率上行更敏感。"),
            ScenarioImpactSeed("公用事业/医疗", "hurt", "类久期资产在利率上行时通常承压。"),
        ),
    ),
    ScenarioTemplate(
        code="rate_down",
        name="利率下行",
        description="将利率或收益率下行映射到成长和地产修复、金融相对承压的组合情景。",
        base_trigger=50.0,
        trigger_unit="bp",
        keywords=("利率", "收益率", "美债", "国债", "rate", "yield"),
        direction_keywords=("下行", "走低", "降息", "降准", "宽松", "bp-", "bps-"),
        rules=(
            ScenarioRuleSeed("sector", "金融", -0.01),
            ScenarioRuleSeed("sector", "科技", 0.05),
            ScenarioRuleSeed("sector", "电信传媒", 0.04),
            ScenarioRuleSeed("sector", "房地产", 0.04),
            ScenarioRuleSeed("sector", "公用事业", 0.02),
            ScenarioRuleSeed("sector", "医疗健康", 0.02),
        ),
        beneficiaries=(
            ScenarioImpactSeed("科技成长", "benefit", "估值贴现率回落时，成长资产通常更受益。"),
            ScenarioImpactSeed("房地产", "benefit", "融资成本下行通常改善地产链和利率敏感资产预期。"),
        ),
        losers=(
            ScenarioImpactSeed("金融", "hurt", "利率下行阶段，金融板块相对收益通常被压缩。"),
        ),
    ),
    ScenarioTemplate(
        code="consumption_recovery",
        name="消费复苏",
        description="将消费复苏映射到可选消费、家居家电和旅游链改善的组合情景。",
        base_trigger=0.05,
        trigger_unit="percent",
        keywords=("消费", "零售", "餐饮", "白酒", "旅游", "可选消费", "demand"),
        direction_keywords=("复苏", "回暖", "改善", "修复", "走强", "超预期"),
        rules=(
            ScenarioRuleSeed("sector", "消费", 0.04),
            ScenarioRuleSeed("sector", "家居家电", 0.02),
            ScenarioRuleSeed("sector", "航空旅游", 0.02),
            ScenarioRuleSeed("sector", "电信传媒", 0.01),
        ),
        beneficiaries=(
            ScenarioImpactSeed("消费", "benefit", "终端需求修复会直接改善消费链和渠道预期。"),
            ScenarioImpactSeed("家居家电", "benefit", "顺周期可选消费链在需求修复阶段弹性更高。"),
        ),
        losers=(),
    ),
    ScenarioTemplate(
        code="consumption_weakness",
        name="消费走弱",
        description="将消费走弱映射到可选消费和出行链承压的组合情景。",
        base_trigger=0.05,
        trigger_unit="percent",
        keywords=("消费", "零售", "餐饮", "白酒", "旅游", "可选消费", "demand"),
        direction_keywords=("走弱", "承压", "回落", "下滑", "疲软", "不及预期"),
        rules=(
            ScenarioRuleSeed("sector", "消费", -0.04),
            ScenarioRuleSeed("sector", "家居家电", -0.02),
            ScenarioRuleSeed("sector", "航空旅游", -0.02),
        ),
        beneficiaries=(),
        losers=(
            ScenarioImpactSeed("消费", "hurt", "终端需求回落会直接压制消费链收入和估值。"),
            ScenarioImpactSeed("航空旅游", "hurt", "可选消费和出行链对需求变化更敏感。"),
        ),
    ),
    ScenarioTemplate(
        code="tech_reg_easing",
        name="科技监管放松",
        description="将科技监管放松映射到平台互联网、传媒和科技板块修复的组合情景。",
        base_trigger=0.06,
        trigger_unit="percent",
        keywords=("科技监管", "平台监管", "互联网监管", "监管", "antitrust", "platform"),
        direction_keywords=("放松", "缓和", "松绑", "宽松", "改善"),
        rules=(
            ScenarioRuleSeed("sector", "科技", 0.05),
            ScenarioRuleSeed("sector", "电信传媒", 0.04),
        ),
        beneficiaries=(
            ScenarioImpactSeed("科技平台", "benefit", "监管缓和通常改善平台资产的估值和风险偏好。"),
        ),
        losers=(),
    ),
    ScenarioTemplate(
        code="tech_reg_tightening",
        name="科技监管趋严",
        description="将科技监管趋严映射到平台互联网、传媒和科技板块承压的组合情景。",
        base_trigger=0.06,
        trigger_unit="percent",
        keywords=("科技监管", "平台监管", "互联网监管", "监管", "antitrust", "platform"),
        direction_keywords=("趋严", "收紧", "从严", "加码", "整顿"),
        rules=(
            ScenarioRuleSeed("sector", "科技", -0.05),
            ScenarioRuleSeed("sector", "电信传媒", -0.04),
        ),
        beneficiaries=(),
        losers=(
            ScenarioImpactSeed("科技平台", "hurt", "监管趋严通常压制平台资产的风险偏好和估值修复。"),
        ),
    ),
    ScenarioTemplate(
        code="export_recovery",
        name="出口回暖",
        description="将出口回暖映射到制造、科技硬件和航运链受益的组合情景。",
        base_trigger=0.05,
        trigger_unit="percent",
        keywords=("出口", "外需", "订单", "shipping", "export"),
        direction_keywords=("回暖", "改善", "修复", "增长", "走强", "超预期"),
        rules=(
            ScenarioRuleSeed("sector", "工业制造", 0.04),
            ScenarioRuleSeed("sector", "科技", 0.03),
            ScenarioRuleSeed("sector", "交通运输", 0.02),
        ),
        beneficiaries=(
            ScenarioImpactSeed("出口制造", "benefit", "出口订单修复通常优先传导到制造和硬件链。"),
            ScenarioImpactSeed("交通运输", "benefit", "航运和物流链也会受益于外需改善。"),
        ),
        losers=(),
    ),
    ScenarioTemplate(
        code="export_slowdown",
        name="出口放缓",
        description="将出口放缓映射到制造、科技硬件和航运链承压的组合情景。",
        base_trigger=0.05,
        trigger_unit="percent",
        keywords=("出口", "外需", "订单", "shipping", "export"),
        direction_keywords=("放缓", "回落", "下滑", "走弱", "疲软", "不及预期"),
        rules=(
            ScenarioRuleSeed("sector", "工业制造", -0.04),
            ScenarioRuleSeed("sector", "科技", -0.03),
            ScenarioRuleSeed("sector", "交通运输", -0.02),
        ),
        beneficiaries=(),
        losers=(
            ScenarioImpactSeed("出口制造", "hurt", "出口订单走弱通常优先拖累制造和硬件链。"),
            ScenarioImpactSeed("交通运输", "hurt", "航运和物流链也会因外需转弱承压。"),
        ),
    ),
)

TEMPLATE_MAP = {template.code: template for template in TEMPLATES}


def _append_phrase(text: str, phrase: str) -> str:
    if phrase in text:
        return text
    return f"{text} {phrase}".strip()


def _contains_any(text: str, parts: tuple[str, ...]) -> bool:
    return any(part in text for part in parts)


def _apply_aliases(text: str) -> str:
    value = text
    for triggers, canonical in PHRASE_ALIAS_GROUPS:
        if _contains_any(value, triggers):
            value = _append_phrase(value, canonical)
    if RMB_WEAKER_RE.search(value) or USD_STRONGER_RE.search(value):
        value = _append_phrase(value, "人民币贬值")
    if RMB_STRONGER_RE.search(value) or USD_WEAKER_RE.search(value):
        value = _append_phrase(value, "人民币升值")
    return value


def _normalize_text(text: str) -> str:
    value = str(text or "").strip().lower()
    translation = str.maketrans({
        "％": "%",
        "＋": "+",
        "－": "-",
        "，": ",",
        "；": ";",
        "：": ":",
        "（": "(",
        "）": ")",
    })
    normalized = value.translate(translation)
    normalized = _apply_aliases(normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _extract_percent(text: str) -> float | None:
    matched = PERCENT_RE.search(text)
    if matched:
        return abs(float(matched.group(1))) / 100.0
    signed = SIGNED_NUMBER_RE.search(text)
    if signed and "%" in text:
        return abs(float(signed.group(1))) / 100.0
    return None


def _extract_bp(text: str) -> float | None:
    matched = BP_RE.search(text)
    if not matched:
        return None
    return abs(float(matched.group(1)))


def _infer_percent_magnitude(text: str) -> float | None:
    for hints, magnitude in PERCENT_MAGNITUDE_HINTS:
        if _contains_any(text, hints):
            return magnitude
    return None


def _infer_bp_magnitude(text: str) -> float | None:
    for hints, magnitude in BP_MAGNITUDE_HINTS:
        if _contains_any(text, hints):
            return magnitude
    if _contains_any(text, ("加息", "降息", "降准", "上行", "下行")):
        return 50.0
    return None


def _dedupe_impacts(items: list[PortfolioScenarioImpactOut]) -> list[PortfolioScenarioImpactOut]:
    result: list[PortfolioScenarioImpactOut] = []
    seen = set()
    for item in items:
        key = (item.label, item.direction, item.rationale)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _scale_rule_shocks(template: ScenarioTemplate, magnitude: float | None) -> list[PortfolioStressRuleIn]:
    ratio = 1.0
    if magnitude is not None and template.base_trigger > 0:
        ratio = max(0.35, min(3.0, magnitude / template.base_trigger))
    return [
        PortfolioStressRuleIn(
            scope_type=rule.scope_type,
            scope_value=rule.scope_value,
            shock_pct=clip_shock_pct(rule.shock_pct * ratio),
        )
        for rule in template.rules
    ]


def _format_magnitude(template: ScenarioTemplate, magnitude: float | None) -> str | None:
    if magnitude is None:
        return None
    if template.trigger_unit == "bp":
        return f"{int(round(magnitude))}bp"
    if template.trigger_unit == "percent":
        return f"{magnitude * 100:.0f}%"
    return None


def _headline(template: ScenarioTemplate, magnitude: float | None) -> str:
    if magnitude is None:
        return template.name
    formatted = _format_magnitude(template, magnitude)
    if not formatted:
        return template.name
    return f"{template.name} {formatted}"


def _impact_list(items: tuple[ScenarioImpactSeed, ...]) -> list[PortfolioScenarioImpactOut]:
    return [
        PortfolioScenarioImpactOut(
            label=item.label,
            direction=item.direction,
            rationale=item.rationale,
        )
        for item in items
    ]


def _render_rule_labels(rules: list[PortfolioStressRuleIn]) -> list[str]:
    return [custom_rule_label(rule) for rule in rules]


def _infer_template_magnitude(template: ScenarioTemplate, text: str) -> float | None:
    if template.trigger_unit == "percent":
        return _infer_percent_magnitude(text)
    if template.trigger_unit == "bp":
        return _infer_bp_magnitude(text)
    return None


def _build_template_clause(template: ScenarioTemplate, clause_text: str) -> ResolvedScenarioClause:
    explicit_magnitude = (
        _extract_percent(clause_text)
        if template.trigger_unit == "percent"
        else _extract_bp(clause_text)
        if template.trigger_unit == "bp"
        else None
    )
    magnitude = explicit_magnitude if explicit_magnitude is not None else _infer_template_magnitude(template, clause_text)
    rules = _scale_rule_shocks(template, magnitude)
    explanation_parts = [
        template.description,
        f"Applied {len(rules)} mapped rules for clause `{clause_text}`.",
    ]
    if explicit_magnitude is not None:
        formatted = _format_magnitude(template, explicit_magnitude)
        if formatted:
            explanation_parts.append(f"Used explicit magnitude {formatted}.")
    elif magnitude is not None:
        formatted = _format_magnitude(template, magnitude)
        if formatted:
            explanation_parts.append(f"Inferred magnitude {formatted} from intensity words or aliases.")
    elif template.trigger_unit != "qualitative":
        explanation_parts.append("No explicit magnitude was found, so the template baseline shock was used.")
    return ResolvedScenarioClause(
        text=clause_text,
        parser="template",
        confidence="high" if explicit_magnitude is not None or template.trigger_unit == "qualitative" else "medium",
        headline=_headline(template, magnitude),
        explanation=" ".join(explanation_parts),
        matched_template_code=template.code,
        matched_template_name=template.name,
        extracted_shock_pct=magnitude if template.trigger_unit == "percent" else None,
        extracted_bp=magnitude if template.trigger_unit == "bp" else None,
        rules=rules,
        beneficiaries=_impact_list(template.beneficiaries),
        losers=_impact_list(template.losers),
    )


def _match_template(text: str) -> ScenarioTemplate | None:
    for template in TEMPLATES:
        if _contains_any(text, template.keywords) and _contains_any(text, template.direction_keywords):
            return template
    return None


def _extract_direction(text: str) -> int:
    if _contains_any(text, UP_WORDS + QUAL_UP_WORDS + EXTRA_UP_WORDS):
        return 1
    if _contains_any(text, DOWN_WORDS + QUAL_DOWN_WORDS + EXTRA_DOWN_WORDS):
        return -1
    signed = SIGNED_NUMBER_RE.search(text)
    if signed:
        return 1 if float(signed.group(1)) > 0 else -1
    return 0


def _resolve_generic_scope_clause(text: str) -> ResolvedScenarioClause | None:
    direction = _extract_direction(text)
    if direction == 0:
        return None

    market = next((value for key, value in MARKET_ALIASES.items() if key in text), None)
    sector = next((value for key, value in SECTOR_ALIASES.items() if key in text), None)
    if not market and not sector:
        return None

    magnitude = _extract_percent(text) or _infer_percent_magnitude(text) or 0.05
    if sector:
        rule = PortfolioStressRuleIn(
            scope_type="sector",
            scope_value=sector,
            shock_pct=clip_shock_pct(direction * magnitude),
        )
        headline = f"{sector}{'走强' if direction > 0 else '承压'} {magnitude * 100:.0f}%"
        explanation = f"Generic scope parser mapped `{text}` into one sector shock on {sector}."
        label = sector
    else:
        rule = PortfolioStressRuleIn(
            scope_type="market",
            scope_value=market,
            shock_pct=clip_shock_pct(direction * magnitude),
        )
        headline = f"{market} market {'up' if direction > 0 else 'down'} {magnitude * 100:.0f}%"
        explanation = f"Generic scope parser mapped `{text}` into one market shock on {market}."
        label = market

    direct = PortfolioScenarioImpactOut(
        label=label,
        direction="benefit" if direction > 0 else "hurt",
        rationale="The parsed scope itself is directly shocked inside the portfolio.",
    )
    reverse = PortfolioScenarioImpactOut(
        label=label,
        direction="hurt" if direction > 0 else "benefit",
        rationale="The reverse side depends on cross-sector spillover and should be reviewed manually.",
    )
    return ResolvedScenarioClause(
        text=text,
        parser="generic",
        confidence="medium",
        headline=headline,
        explanation=explanation,
        matched_template_code=None,
        matched_template_name="generic-scope-parser",
        extracted_shock_pct=magnitude,
        extracted_bp=None,
        rules=[rule],
        beneficiaries=[direct] if direction > 0 else [reverse],
        losers=[reverse] if direction > 0 else [direct],
    )


def _unparsed_clause(text: str) -> ResolvedScenarioClause:
    return ResolvedScenarioClause(
        text=text,
        parser="unparsed",
        confidence="low",
        headline=text,
        explanation="This clause could not be mapped into a supported macro scenario or generic scope shock yet.",
        matched_template_code=None,
        matched_template_name=None,
        extracted_shock_pct=None,
        extracted_bp=None,
        rules=[],
        beneficiaries=[],
        losers=[],
    )


def _split_clauses(text: str) -> list[str]:
    parts = [item.strip() for item in CLAUSE_SPLIT_RE.split(text) if item and item.strip()]
    result: list[str] = []
    seen = set()
    for part in parts:
        if part in seen:
            continue
        seen.add(part)
        result.append(part)
    return result or [text.strip()]


def _merge_rules(clauses: list[ResolvedScenarioClause]) -> list[PortfolioStressRuleIn]:
    merged: dict[tuple[str, str | None], float] = {}
    for clause in clauses:
        for rule in clause.rules:
            key = (rule.scope_type, rule.scope_value)
            merged[key] = merged.get(key, 0.0) + float(rule.shock_pct)
    return [
        PortfolioStressRuleIn(
            scope_type=scope_type,
            scope_value=scope_value,
            shock_pct=clip_shock_pct(shock_pct),
        )
        for (scope_type, scope_value), shock_pct in merged.items()
    ]


def _bundle_confidence(clauses: list[ResolvedScenarioClause]) -> str:
    if not clauses:
        return "low"
    if all(item.parser == "template" for item in clauses):
        return "high"
    if any(item.parser == "unparsed" for item in clauses):
        return "medium" if any(item.parser != "unparsed" for item in clauses) else "low"
    return "medium"


def _combine_explanation(
    clauses: list[ResolvedScenarioClause],
    parsed_count: int,
    total_count: int,
    rules_count: int,
) -> str:
    template_count = len([item for item in clauses if item.parser == "template"])
    generic_count = len([item for item in clauses if item.parser == "generic"])
    skipped_count = total_count - parsed_count
    parts = [
        f"Parsed {parsed_count}/{total_count} clauses into {rules_count} combined stress rules.",
        f"Matched {template_count} template clauses and {generic_count} generic clauses.",
    ]
    if skipped_count > 0:
        parts.append(f"{skipped_count} clauses were left as manual-review items.")
    return " ".join(parts)


def _combine_headline(parsed_clauses: list[ResolvedScenarioClause]) -> str:
    if not parsed_clauses:
        return "Unparsed macro scenario"
    if len(parsed_clauses) == 1:
        return parsed_clauses[0].headline
    return " + ".join(item.headline for item in parsed_clauses[:3])


def _combine_description(parsed_clauses: list[ResolvedScenarioClause]) -> str:
    if not parsed_clauses:
        return "No supported macro clause was parsed."
    return " ".join(item.explanation for item in parsed_clauses[:3])


def _first_extracted_shock_pct(parsed_clauses: list[ResolvedScenarioClause]) -> float | None:
    for clause in parsed_clauses:
        if clause.extracted_shock_pct is not None:
            return clause.extracted_shock_pct
    return None


def _build_bundle(clauses: list[ResolvedScenarioClause]) -> ResolvedScenarioBundle:
    parsed_clauses = [item for item in clauses if item.rules]
    if not parsed_clauses:
        raise ValueError(
            "Unable to parse this scenario. Try inputs like 油价涨 8%、人民币贬值、地产政策放松、美债收益率上行 50bp，或者 港股科技跌 6%。"
        )
    rules = _merge_rules(parsed_clauses)
    template_codes = [item.matched_template_code for item in parsed_clauses if item.matched_template_code]
    template_names = [item.matched_template_name for item in parsed_clauses if item.matched_template_name]
    matched_template_codes = list(dict.fromkeys(template_codes))
    matched_template_names = list(dict.fromkeys(template_names))
    beneficiaries = _dedupe_impacts([impact for clause in parsed_clauses for impact in clause.beneficiaries])[:6]
    losers = _dedupe_impacts([impact for clause in parsed_clauses for impact in clause.losers])[:6]
    headline = _combine_headline(parsed_clauses)
    confidence = _bundle_confidence(clauses)
    return ResolvedScenarioBundle(
        matched_template_code=matched_template_codes[0] if len(matched_template_codes) == 1 else None,
        matched_template_name=matched_template_names[0] if len(matched_template_names) == 1 else None,
        matched_template_codes=matched_template_codes,
        matched_template_names=matched_template_names,
        name=headline,
        description=_combine_description(parsed_clauses),
        confidence=confidence,
        extracted_shock_pct=_first_extracted_shock_pct(parsed_clauses) if len(parsed_clauses) == 1 else None,
        headline=headline,
        explanation=_combine_explanation(clauses, len(parsed_clauses), len(clauses), len(rules)),
        clauses=clauses,
        rules=rules,
        beneficiaries=beneficiaries,
        losers=losers,
    )


def build_macro_scenario_from_code(code: str) -> ResolvedScenarioBundle:
    template = TEMPLATE_MAP.get(str(code or "").strip())
    if template is None:
        raise ValueError("Unsupported macro scenario template.")
    clause = _build_template_clause(template, template.name)
    return _build_bundle([clause])


def resolve_portfolio_macro_scenario(text: str) -> ResolvedScenarioBundle:
    normalized = _normalize_text(text)
    if not normalized:
        raise ValueError("Scenario text cannot be empty.")

    clauses: list[ResolvedScenarioClause] = []
    for raw_clause in _split_clauses(normalized):
        template = _match_template(raw_clause)
        if template is not None:
            clauses.append(_build_template_clause(template, raw_clause))
            continue
        generic = _resolve_generic_scope_clause(raw_clause)
        if generic is not None:
            clauses.append(generic)
            continue
        clauses.append(_unparsed_clause(raw_clause))
    return _build_bundle(clauses)
