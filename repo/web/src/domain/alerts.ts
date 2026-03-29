import {
  AlertCenterItem,
  AlertCenterResponse,
  AlertPriceOperator,
  AlertResearchKind,
  AlertRuleType,
  buildMyAlertCenterQueryKey,
  createMyAlert,
  deleteMyAlert,
  getMyAlertCenter,
  getUserScopedQueryOptions,
  updateMyAlert,
} from "../services/api";

export const DEFAULT_ALERT_LOOKBACK_DAYS = 7;

export type AlertRuleDraft = {
  name: string;
  symbol: string;
  ruleType: AlertRuleType;
  priceOperator: AlertPriceOperator;
  threshold: string;
  eventType: string;
  researchKind: AlertResearchKind;
  lookbackDays: number;
};

export function normalizeAlertSymbol(value: string) {
  return (value || "").trim().toUpperCase();
}

export function dedupeAlertSymbols(values: string[]) {
  const seen = new Set<string>();
  const output: string[] = [];
  values.forEach((value) => {
    const symbol = normalizeAlertSymbol(value);
    if (!symbol || seen.has(symbol)) {
      return;
    }
    seen.add(symbol);
    output.push(symbol);
  });
  return output;
}

export function buildAlertDefaultThreshold(type: AlertRuleType) {
  return type === "price" ? "10" : "";
}

export function buildAlertRuleSummary(item: AlertCenterItem) {
  if (item.rule_type === "price") {
    return `${item.price_operator === "lte" ? "<=" : ">="} ${item.threshold ?? "--"}`;
  }
  if (item.rule_type === "event") {
    return item.event_type || "event";
  }
  return item.research_kind === "report"
    ? "report"
    : item.research_kind === "earning_forecast"
      ? "forecast"
      : "all research";
}

export function buildAlertReadableExplanation(item: AlertCenterItem) {
  if (item.explanation?.trim()) {
    return item.explanation.trim();
  }
  if (item.rule_type === "price") {
    const operator = item.price_operator === "lte" ? "<=" : ">=";
    return `${item.symbol} price rule watches ${operator} ${item.threshold ?? "--"} and is currently ${item.status}.`;
  }
  if (item.rule_type === "event") {
    return `${item.symbol} event rule tracks ${item.event_type || "event"} over the last ${item.lookback_days} days.`;
  }
  const researchLabel =
    item.research_kind === "report"
      ? "research reports"
      : item.research_kind === "earning_forecast"
        ? "earnings forecasts"
        : "research updates";
  return `${item.symbol} earnings rule watches new ${researchLabel} over the last ${item.lookback_days} days.`;
}

export function buildAlertCenterDomainQueryKey(token: string) {
  return buildMyAlertCenterQueryKey(token);
}

export function getAlertCenterDomainQueryOptions() {
  return getUserScopedQueryOptions("alert-center");
}

export async function loadAlertCenter(token: string) {
  return getMyAlertCenter(token);
}

export async function createAlertRule(token: string, draft: AlertRuleDraft) {
  return createMyAlert(token, {
    name: draft.name.trim(),
    symbol: normalizeAlertSymbol(draft.symbol),
    rule_type: draft.ruleType,
    price_operator: draft.ruleType === "price" ? draft.priceOperator : undefined,
    threshold: draft.ruleType === "price" ? Number(draft.threshold) : undefined,
    event_type: draft.ruleType === "event" ? draft.eventType.trim() : undefined,
    research_kind: draft.ruleType === "earnings" ? draft.researchKind : undefined,
    lookback_days: draft.lookbackDays,
  });
}

export async function setAlertRuleEnabled(token: string, ruleId: number, enabled: boolean) {
  return updateMyAlert(token, ruleId, { is_active: enabled });
}

export async function removeAlertRule(token: string, ruleId: number) {
  return deleteMyAlert(token, ruleId);
}

export function filterAlertItemsBySymbols(
  center: AlertCenterResponse | undefined,
  symbols: string[],
  filterSymbol?: string,
) {
  const normalizedSymbols = dedupeAlertSymbols(symbols);
  const normalizedFilter = normalizeAlertSymbol(filterSymbol || "");
  const scopedItems = (center?.items || []).filter((item) =>
    normalizedSymbols.includes(normalizeAlertSymbol(item.symbol)),
  );
  if (!normalizedFilter) {
    return scopedItems;
  }
  return scopedItems.filter((item) => normalizeAlertSymbol(item.symbol) === normalizedFilter);
}
