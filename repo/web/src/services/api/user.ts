import {
  request,
  requestAuthed,
  requestAuthedDelete,
  requestAuthedJson,
  requestJson,
} from "./core";

export type PortfolioStressPosition = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
  current_price: number;
  current_value: number;
  weight: number;
  shock_pct: number;
  projected_value: number;
  value_change: number;
};

export type PortfolioStressBucket = {
  label: string;
  affected_value: number;
  portfolio_weight: number;
  value_change: number;
};

export type PortfolioStressScenario = {
  code: string;
  name: string;
  description: string;
  rules: string[];
  projected_value: number;
  portfolio_change: number;
  portfolio_change_pct: number;
  loss_amount: number;
  loss_pct: number;
  impacted_value: number;
  impacted_weight: number;
  average_shock_pct?: number | null;
  affected_positions: PortfolioStressPosition[];
  sector_impacts: PortfolioStressBucket[];
  market_impacts: PortfolioStressBucket[];
};

export type PortfolioStressSummary = {
  as_of?: string | null;
  holdings_count: number;
  total_value: number;
  scenario_count: number;
  worst_scenario_code?: string | null;
  worst_scenario_name?: string | null;
  worst_loss_amount: number;
  worst_loss_pct: number;
  max_impacted_weight: number;
};

export type PortfolioStressResponse = {
  summary: PortfolioStressSummary;
  scenarios: PortfolioStressScenario[];
};

export type PortfolioStressRuleScope = "all" | "market" | "sector" | "symbol";

export type PortfolioStressCustomRuleInput = {
  scope_type: PortfolioStressRuleScope;
  scope_value?: string | null;
  shock_pct: number;
};

export type PortfolioStressPreviewPayload = {
  name: string;
  description?: string;
  rules: PortfolioStressCustomRuleInput[];
  position_limit?: number;
};

export type PortfolioScenarioImpact = {
  label: string;
  direction: string;
  rationale: string;
};

export type PortfolioScenarioLabClause = {
  text: string;
  parser: string;
  confidence: string;
  headline: string;
  explanation: string;
  matched_template_code?: string | null;
  matched_template_name?: string | null;
  extracted_shock_pct?: number | null;
  extracted_bp?: number | null;
  rules: string[];
};

export type PortfolioScenarioLabParse = {
  input_text: string;
  matched_template_code?: string | null;
  matched_template_name?: string | null;
  matched_template_codes: string[];
  matched_template_names: string[];
  confidence: string;
  extracted_shock_pct?: number | null;
  headline: string;
  explanation: string;
  clauses: PortfolioScenarioLabClause[];
};

export type PortfolioScenarioLabResponse = {
  schema_version: string;
  parse: PortfolioScenarioLabParse;
  scenario: PortfolioStressScenario;
  beneficiaries: PortfolioScenarioImpact[];
  losers: PortfolioScenarioImpact[];
};

export type PortfolioDiagnosticsExposure = {
  label: string;
  value: number;
  weight: number;
};

export type PortfolioDiagnosticsHolding = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
  weight: number;
  current_value: number;
  pnl_value: number;
  pnl_pct: number;
};

export type PortfolioDiagnosticsStyle = {
  code: string;
  label: string;
  score: number;
  explanation: string;
};

export type PortfolioDiagnosticsSensitivity = {
  code: string;
  label: string;
  scenario_name: string;
  portfolio_change_pct: number;
  direction: string;
  explanation: string;
};

export type PortfolioDiagnosticsTag = {
  code: string;
  label: string;
  tone: string;
  explanation: string;
};

export type PortfolioDiagnosticsSummary = {
  as_of?: string | null;
  holdings_count: number;
  total_cost: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  sector_count: number;
  top_sector?: string | null;
  top_market?: string | null;
  top3_weight: number;
};

export type PortfolioDiagnosticsResponse = {
  schema_version: string;
  summary: PortfolioDiagnosticsSummary;
  overview: string;
  portrait: PortfolioDiagnosticsTag[];
  style_exposures: PortfolioDiagnosticsStyle[];
  macro_sensitivities: PortfolioDiagnosticsSensitivity[];
  sector_exposure: PortfolioDiagnosticsExposure[];
  market_exposure: PortfolioDiagnosticsExposure[];
  top_positions: PortfolioDiagnosticsHolding[];
};

export type WatchTargetItem = {
  symbol: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type BoughtTargetItem = {
  symbol: string;
  buy_price: number;
  lots: number;
  buy_date: string;
  fee: number;
  note: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AlertRuleType = "price" | "event" | "earnings";
export type AlertPriceOperator = "gte" | "lte";
export type AlertResearchKind = "all" | "report" | "earning_forecast";

export type AlertRuleItem = {
  id: number;
  name: string;
  rule_type: AlertRuleType;
  symbol: string;
  price_operator?: AlertPriceOperator | null;
  threshold?: number | null;
  event_type?: string | null;
  research_kind?: AlertResearchKind | null;
  lookback_days: number;
  is_active: boolean;
  note: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AlertCenterItem = AlertRuleItem & {
  triggered: boolean;
  status: string;
  status_message: string;
  explanation?: string | null;
  latest_value?: number | null;
  matched_at?: string | null;
  context_title?: string | null;
};

export type AlertCenterResponse = {
  total: number;
  triggered: number;
  items: AlertCenterItem[];
};

export type UserStockPoolItem = {
  id: number;
  name: string;
  market: "A" | "HK" | "US";
  symbols: string[];
  note: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type UserStockFilterItem = {
  id: number;
  name: string;
  market: "A" | "HK" | "US";
  keyword: string;
  sector: string;
  sort: "asc" | "desc";
  created_at?: string | null;
  updated_at?: string | null;
};

export type UserWorkspaceResponse = {
  pools: UserStockPoolItem[];
  filters: UserStockFilterItem[];
};

export async function getPortfolioAnalysis(userId: number, params?: { top_n?: number }) {
  const query = new URLSearchParams();
  if (params?.top_n !== undefined) query.set("top_n", String(params.top_n));
  const suffix = query.toString();
  return request(`/api/user/${userId}/portfolio/analysis${suffix ? `?${suffix}` : ""}`);
}

export async function registerUser(account: string, password: string) {
  return requestJson("/api/auth/register", { account, password });
}

export async function loginUser(account: string, password: string) {
  return requestJson("/api/auth/login", { account, password });
}

export async function getCurrentUser(token: string) {
  return requestAuthed("/api/auth/me", token);
}

export async function getMyWatchTargets(token: string) {
  return requestAuthed<WatchTargetItem[]>("/api/user/me/watch-targets", token, {
    label: "watch-targets",
  });
}

export async function upsertMyWatchTarget(token: string, symbol: string) {
  return requestAuthedJson<WatchTargetItem>("/api/user/me/watch-targets", { symbol }, token);
}

export async function upsertMyWatchTargetsBatch(token: string, symbols: string[]) {
  return requestAuthedJson<WatchTargetItem[]>("/api/user/me/watch-targets/batch", { symbols }, token);
}

export async function deleteMyWatchTarget(token: string, symbol: string) {
  return requestAuthedDelete(`/api/user/me/watch-targets/${encodeURIComponent(symbol)}`, token);
}

export async function getMyBoughtTargets(token: string) {
  return requestAuthed<BoughtTargetItem[]>("/api/user/me/bought-targets", token, {
    label: "bought-targets",
  });
}

export async function getMyWatchTargetStressTest(
  token: string,
  params?: { position_limit?: number },
) {
  const query = new URLSearchParams();
  if (params?.position_limit !== undefined) query.set("position_limit", String(params.position_limit));
  const suffix = query.toString();
  return requestAuthed<PortfolioStressResponse>(`/api/user/me/watch-targets/stress-test${suffix ? `?${suffix}` : ""}`, token, {
    label: "watch-portfolio-stress",
  });
}

export async function previewMyWatchTargetStressTest(
  token: string,
  payload: PortfolioStressPreviewPayload,
) {
  return requestAuthedJson<PortfolioStressScenario>(
    "/api/user/me/watch-targets/stress-test/custom",
    {
      name: payload.name,
      description: payload.description ?? "",
      position_limit: payload.position_limit ?? 8,
      rules: payload.rules.map((rule) => ({
        scope_type: rule.scope_type,
        scope_value: rule.scope_value ?? null,
        shock_pct: rule.shock_pct,
      })),
    },
    token,
    { label: "watch-portfolio-stress-preview" },
  );
}

export async function runMyWatchTargetScenarioLab(
  token: string,
  payload: { text: string; position_limit?: number },
) {
  return requestAuthedJson<PortfolioScenarioLabResponse>(
    "/api/user/me/watch-targets/stress-test/lab",
    {
      text: payload.text,
      position_limit: payload.position_limit ?? 8,
    },
    token,
    { label: "watch-portfolio-scenario-lab" },
  );
}

export async function getMyWatchTargetDiagnostics(token: string) {
  return requestAuthed<PortfolioDiagnosticsResponse>("/api/user/me/watch-targets/diagnostics", token, {
    label: "watch-portfolio-diagnostics",
  });
}

export async function getMyBoughtTargetStressTest(
  token: string,
  params?: { position_limit?: number },
) {
  const query = new URLSearchParams();
  if (params?.position_limit !== undefined) query.set("position_limit", String(params.position_limit));
  const suffix = query.toString();
  return requestAuthed<PortfolioStressResponse>(`/api/user/me/bought-targets/stress-test${suffix ? `?${suffix}` : ""}`, token, {
    label: "portfolio-stress",
  });
}

export async function previewMyBoughtTargetStressTest(
  token: string,
  payload: PortfolioStressPreviewPayload,
) {
  return requestAuthedJson<PortfolioStressScenario>(
    "/api/user/me/bought-targets/stress-test/custom",
    {
      name: payload.name,
      description: payload.description ?? "",
      position_limit: payload.position_limit ?? 8,
      rules: payload.rules.map((rule) => ({
        scope_type: rule.scope_type,
        scope_value: rule.scope_value ?? null,
        shock_pct: rule.shock_pct,
      })),
    },
    token,
    { label: "portfolio-stress-preview" },
  );
}

export async function runMyBoughtTargetScenarioLab(
  token: string,
  payload: { text: string; position_limit?: number },
) {
  return requestAuthedJson<PortfolioScenarioLabResponse>(
    "/api/user/me/bought-targets/stress-test/lab",
    {
      text: payload.text,
      position_limit: payload.position_limit ?? 8,
    },
    token,
    { label: "portfolio-scenario-lab" },
  );
}

export async function getMyBoughtTargetDiagnostics(token: string) {
  return requestAuthed<PortfolioDiagnosticsResponse>("/api/user/me/bought-targets/diagnostics", token, {
    label: "portfolio-diagnostics",
  });
}

export async function upsertMyBoughtTarget(
  token: string,
  payload: { symbol: string; buy_price: number; lots: number; buy_date: string; fee?: number; note?: string },
) {
  return requestAuthedJson<BoughtTargetItem>(
    "/api/user/me/bought-targets",
    {
      symbol: payload.symbol,
      buy_price: payload.buy_price,
      lots: payload.lots,
      buy_date: payload.buy_date,
      fee: payload.fee ?? 0,
      note: payload.note ?? "",
    },
    token,
  );
}

export async function upsertMyBoughtTargetsBatch(
  token: string,
  items: Array<{ symbol: string; buy_price: number; lots: number; buy_date: string; fee?: number; note?: string }>,
) {
  return requestAuthedJson<BoughtTargetItem[]>(
    "/api/user/me/bought-targets/batch",
    {
      items: items.map((item) => ({
        symbol: item.symbol,
        buy_price: item.buy_price,
        lots: item.lots,
        buy_date: item.buy_date,
        fee: item.fee ?? 0,
        note: item.note ?? "",
      })),
    },
    token,
  );
}

export async function deleteMyBoughtTarget(token: string, symbol: string) {
  return requestAuthedDelete(`/api/user/me/bought-targets/${encodeURIComponent(symbol)}`, token);
}

export async function getMyAlerts(token: string) {
  return requestAuthed<AlertRuleItem[]>("/api/user/me/alerts", token);
}

export async function getMyAlertCenter(token: string) {
  return requestAuthed<AlertCenterResponse>("/api/user/me/alerts/center", token, {
    label: "alert-center",
  });
}

export async function createMyAlert(
  token: string,
  payload: {
    name: string;
    rule_type: AlertRuleType;
    symbol: string;
    price_operator?: AlertPriceOperator;
    threshold?: number;
    event_type?: string;
    research_kind?: AlertResearchKind;
    lookback_days?: number;
    is_active?: boolean;
    note?: string;
  },
) {
  return requestAuthedJson<AlertRuleItem>(
    "/api/user/me/alerts",
    {
      ...payload,
      lookback_days: payload.lookback_days ?? 7,
      is_active: payload.is_active ?? true,
      note: payload.note ?? "",
    },
    token,
  );
}

export async function updateMyAlert(
  token: string,
  ruleId: number,
  payload: {
    name?: string;
    price_operator?: AlertPriceOperator;
    threshold?: number;
    event_type?: string;
    research_kind?: AlertResearchKind;
    lookback_days?: number;
    is_active?: boolean;
    note?: string;
  },
) {
  return requestAuthedJson<AlertRuleItem>(`/api/user/me/alerts/${ruleId}`, payload, token, { method: "PATCH" });
}

export async function deleteMyAlert(token: string, ruleId: number) {
  return requestAuthedDelete(`/api/user/me/alerts/${ruleId}`, token);
}

export async function getMyWorkspace(token: string) {
  return requestAuthed<UserWorkspaceResponse>("/api/user/me/workspace", token, {
    label: "workspace",
  });
}

export async function createMyStockPool(
  token: string,
  payload: { name: string; market: "A" | "HK" | "US"; symbols: string[]; note?: string },
) {
  return requestAuthedJson<UserStockPoolItem>(
    "/api/user/me/stock-pools",
    {
      name: payload.name,
      market: payload.market,
      symbols: payload.symbols,
      note: payload.note ?? "",
    },
    token,
  );
}

export async function deleteMyStockPool(token: string, poolId: number) {
  return requestAuthedDelete(`/api/user/me/stock-pools/${poolId}`, token);
}

export async function createMyStockFilter(
  token: string,
  payload: { name: string; market: "A" | "HK" | "US"; keyword?: string; sector?: string; sort?: "asc" | "desc" },
) {
  return requestAuthedJson<UserStockFilterItem>(
    "/api/user/me/stock-filters",
    {
      name: payload.name,
      market: payload.market,
      keyword: payload.keyword ?? "",
      sector: payload.sector ?? "",
      sort: payload.sort ?? "asc",
    },
    token,
  );
}

export async function deleteMyStockFilter(token: string, filterId: number) {
  return requestAuthedDelete(`/api/user/me/stock-filters/${filterId}`, token);
}
