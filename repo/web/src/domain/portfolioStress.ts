import {
  ApiQueryOptions,
  PortfolioScenarioLabResponse,
  PortfolioStressPreviewPayload,
  PortfolioStressResponse,
  PortfolioStressRuleScope,
  getMyBoughtTargetStressTest,
  getMyWatchTargetStressTest,
  previewMyBoughtTargetStressTest,
  previewMyWatchTargetStressTest,
  runMyBoughtTargetScenarioLab,
  runMyWatchTargetScenarioLab,
} from "../services/api";
import type { PortfolioTargetScope } from "./portfolioDiagnostics";

export const PORTFOLIO_STRESS_POSITION_LIMIT = 8;

export type PortfolioStressRuleDraft = {
  id: string;
  scopeType: PortfolioStressRuleScope;
  scopeValue: string;
  shockPctText: string;
};

export type PortfolioScenarioLabPreset = {
  id: string;
  title: string;
  summary: string;
  prompt: string;
  tags: string[];
};

export const PORTFOLIO_SCENARIO_LAB_PRESETS: PortfolioScenarioLabPreset[] = [
  {
    id: "oil-rmb-property",
    title: "油价上行 + 汇率走弱",
    summary: "适合快速查看资源、运输、地产链在复合宏观冲击下的分化。",
    prompt: "国际油价大涨 8%，人民币走弱，地产松绑",
    tags: ["油价", "人民币", "地产"],
  },
  {
    id: "usd-export-hk-tech",
    title: "美元走强 + 出口修复",
    summary: "观察出口链回暖和港股科技承压同时发生时，组合受益与受损方向。",
    prompt: "美元走强，出口订单回暖，港股科技承压 6%",
    tags: ["美元", "出口", "港股科技"],
  },
  {
    id: "rrr-consumption-travel",
    title: "宽松政策 + 消费修复",
    summary: "用于测试降准后消费、航空旅游等顺周期板块的弹性。",
    prompt: "降准 50bp，消费回暖，航空旅游受益",
    tags: ["降准", "消费", "出行"],
  },
  {
    id: "rates-real-estate-finance",
    title: "利率上行冲击",
    summary: "检验利率抬升对地产、金融等利率敏感板块的相对表现。",
    prompt: "美债收益率上行 50bp，房地产承压，金融相对受益",
    tags: ["利率", "房地产", "金融"],
  },
  {
    id: "policy-manufacturing-cyclicals",
    title: "政策放松 + 制造复苏",
    summary: "用来检查政策边际放松后，制造、周期和高负债资产的传导链。",
    prompt: "地产政策放松，基建发力，工业金属上涨 5%，高负债地产继续承压",
    tags: ["政策", "基建", "周期"],
  },
];

export const PORTFOLIO_SCENARIO_LAB_EXAMPLES = PORTFOLIO_SCENARIO_LAB_PRESETS.map((item) => item.prompt);

function hashIdentity(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return Math.abs(hash).toString(36);
}

export function buildPortfolioStressQueryKey(
  token: string,
  targetType: PortfolioTargetScope = "bought",
  positionLimit = PORTFOLIO_STRESS_POSITION_LIMIT,
) {
  return `user:portfolio-stress:${targetType}:${hashIdentity(token)}:limit=${positionLimit}`;
}

export function getPortfolioStressQueryOptions(
  targetType: PortfolioTargetScope = "bought",
): ApiQueryOptions {
  return {
    staleTimeMs: 60_000,
    cacheTimeMs: 5 * 60_000,
    retry: 1,
    label: `${targetType}-portfolio-stress`,
  };
}

export async function loadPortfolioStress(
  token: string,
  targetType: PortfolioTargetScope = "bought",
  positionLimit = PORTFOLIO_STRESS_POSITION_LIMIT,
): Promise<PortfolioStressResponse> {
  return targetType === "watch"
    ? getMyWatchTargetStressTest(token, { position_limit: positionLimit })
    : getMyBoughtTargetStressTest(token, { position_limit: positionLimit });
}

export async function previewPortfolioStress(
  token: string,
  targetType: PortfolioTargetScope,
  payload: PortfolioStressPreviewPayload,
) {
  return targetType === "watch"
    ? previewMyWatchTargetStressTest(token, payload)
    : previewMyBoughtTargetStressTest(token, payload);
}

export async function runPortfolioScenarioLab(
  token: string,
  targetType: PortfolioTargetScope,
  text: string,
  positionLimit = PORTFOLIO_STRESS_POSITION_LIMIT,
): Promise<PortfolioScenarioLabResponse> {
  const payload = {
    text: text.trim(),
    position_limit: positionLimit,
  };
  return targetType === "watch"
    ? runMyWatchTargetScenarioLab(token, payload)
    : runMyBoughtTargetScenarioLab(token, payload);
}

export function normalizeScenarioLabInput(value: string) {
  return String(value || "").trim();
}

export function validatePortfolioStressDraft(
  name: string,
  rules: PortfolioStressRuleDraft[],
) {
  if (!name.trim()) {
    return "Please enter a scenario name.";
  }
  for (const rule of rules) {
    const shockPct = Number(rule.shockPctText);
    if (!Number.isFinite(shockPct)) {
      return "Shock must be a valid number.";
    }
    if (shockPct < -95 || shockPct > 95) {
      return "Shock must stay between -95 and 95.";
    }
    if (rule.scopeType !== "all" && !rule.scopeValue.trim()) {
      return "Market, sector, and symbol rules require a scope value.";
    }
  }
  return null;
}

export function validateScenarioLabInput(text: string) {
  if (!normalizeScenarioLabInput(text)) {
    return "Please enter a scenario prompt.";
  }
  return null;
}
