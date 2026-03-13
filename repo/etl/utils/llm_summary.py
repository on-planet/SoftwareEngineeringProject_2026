from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional

from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


@dataclass
class LlmConfig:
    enabled: bool
    provider: str
    api_key: Optional[str]
    model: str


def load_llm_config() -> LlmConfig:
    enabled = os.getenv("LLM_ENABLED", "false").lower() in {"1", "true", "yes"}
    provider = os.getenv("LLM_PROVIDER", "openai")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    if enabled and not api_key:
        LOGGER.warning("LLM 已启用但未配置 API Key，将回退模板摘要")
    return LlmConfig(enabled=enabled and bool(api_key), provider=provider, api_key=api_key, model=model)


def build_summary_prompt(symbol: str, score: float, profit_quality: float, growth: float, risk: float) -> str:
    return (
        "你是量化研究助理，请用一句话总结基本面评分结果。\n"
        f"股票: {symbol}\n"
        f"评分: {score:.2f}\n"
        f"盈利质量: {profit_quality:.2f}\n"
        f"成长性: {growth:.2f}\n"
        f"风险: {risk:.2f}\n"
    )


def generate_summary_template(score: float, profit_quality: float, growth: float, risk: float) -> str:
    tone = "稳健" if score >= 70 else "中性" if score >= 50 else "偏弱"
    risk_desc = "风险可控" if risk < 0.5 else "风险偏高"
    growth_desc = "成长性较好" if growth > 0 else "成长性一般"
    return f"综合评分{score:.1f}，盈利质量{profit_quality:.2f}、{growth_desc}，{risk_desc}，整体{tone}。"


def generate_summary(symbol: str, score: float, profit_quality: float, growth: float, risk: float) -> str:
    config = load_llm_config()
    if not config.enabled:
        return generate_summary_template(score, profit_quality, growth, risk)

    prompt = build_summary_prompt(symbol, score, profit_quality, growth, risk)
    LOGGER.info("LLM 已启用但未接入真实调用，回退模板摘要。provider=%s model=%s", config.provider, config.model)
    return generate_summary_template(score, profit_quality, growth, risk)
