import { formatLoosePercent, formatNumber } from "../../utils/format";
import { marketTheme } from "../../styles/marketTheme";

export type MacroItem = {
  key: string;
  date: string;
  value: number;
  score?: number;
};

export type MacroPage = {
  items: MacroItem[];
  total: number;
  limit: number;
  offset: number;
};

export type MacroSeries = {
  key: string;
  items: { date: string; value: number; score?: number }[];
};

export type MacroSource = "world_bank" | "akshare";
export type SortOrder = "asc" | "desc";

export type SnapshotCard = MacroItem & {
  source: MacroSource;
  country: string;
  family: string;
  label: string;
  countryLabel: string;
  sourceLabel: string;
};

export const SNAPSHOT_PAGE_LIMIT = 200;
export const SNAPSHOT_PAGE_MAX = 10;
export const SNAPSHOT_CARD_LIMIT = 12;
export const MACRO_SNAPSHOT_CACHE_TTL_MS = 10 * 60 * 1000;
export const MACRO_SERIES_CACHE_TTL_MS = 10 * 60 * 1000;

const WORLD_BANK_LABELS: Record<string, string> = {
  GDP: "国内生产总值",
  CPI: "居民消费价格指数",
  UNEMP: "失业率",
  TRADE: "贸易开放度",
};

export const COUNTRY_LABELS: Record<string, string> = {
  USA: "美国",
  CHN: "中国",
  JPN: "日本",
  DEU: "德国",
  FRA: "法国",
  GBR: "英国",
  ITA: "意大利",
  CAN: "加拿大",
  AUS: "澳大利亚",
  KOR: "韩国",
  IND: "印度",
  BRA: "巴西",
  RUS: "俄罗斯",
  MEX: "墨西哥",
  IDN: "印度尼西亚",
  TUR: "土耳其",
  SAU: "沙特",
  ZAF: "南非",
  ARG: "阿根廷",
  EUU: "欧盟",
  EUR: "欧元区",
  BJ: "北京",
  SH: "上海",
};

const AK_TOKEN_LABELS: Record<string, string> = {
  GDP: "国内生产总值",
  CPI: "居民消费价格指数",
  PPI: "工业生产者价格指数",
  M2: "M2",
  PMI: "采购经理指数",
  UNEMP: "失业率",
  YOY: "同比",
  MOM: "环比",
  QOQ: "季环比",
  FX: "外汇",
  RESERVES: "储备",
  EXPORTS: "出口",
  IMPORTS: "进口",
  TRADE: "贸易",
  BALANCE: "差额",
  FED: "美联储",
  RATE: "利率",
  FDI: "外商直接投资",
  LPR: "LPR",
  SOCIAL: "社会",
  FINANCING: "融资",
  CREDIT: "信贷",
  HOUSE: "房价",
  PRICE: "价格",
  ENTERPRISE: "企业",
  BOOM: "景气",
  CONFIDENCE: "信心",
  TAX: "税收",
  ENERGY: "能源",
  COMMODITY: "大宗商品",
  CURRENT: "当期",
  CUMULATIVE: "累计",
  TOTAL: "总量",
  VALUE: "数值",
  ACTUAL: "今值",
  FORECAST: "预测值",
  PREVIOUS: "前值",
  BANK: "银行",
  RMB: "人民币",
  LOAN: "贷款",
  TRUST: "信托",
  BOND: "债券",
  EQUITY: "股权",
  NEW: "新房",
  SECOND: "二手房",
  BASE: "定基",
  LPR_1Y: "一年期 LPR",
  LPR_5Y: "五年期 LPR",
  CURRENT_YOY: "当期同比",
  CURRENT_MOM: "当期环比",
  CUMULATIVE_YOY: "累计同比",
  NEW_YOY: "新房同比",
  NEW_MOM: "新房环比",
  NEW_BASE: "新房定基",
  SECOND_YOY: "二手房同比",
  SECOND_MOM: "二手房环比",
  SECOND_BASE: "二手房定基",
  BOOM_INDEX: "企业景气指数",
  BOOM_YOY: "景气指数同比",
  BOOM_MOM: "景气指数环比",
  CONFIDENCE_INDEX: "企业家信心指数",
  CONFIDENCE_YOY: "信心指数同比",
  CONFIDENCE_MOM: "信心指数环比",
  NON_FARM: "非农",
  NON_FIN_CORP: "非金融企业",
  CHN: "中国",
  USA: "美国",
  EUR: "欧元区",
  BJ: "北京",
  SH: "上海",
  CHG_3M: "近 3 个月",
  CHG_6M: "近 6 个月",
  CHG_1Y: "近 1 年",
  CHG_2Y: "近 2 年",
  CHG_3Y: "近 3 年",
};

export function parseMacroKey(key: string) {
  const [indicator, country] = key.split(":");
  return {
    indicator: indicator || "",
    country: country || "",
  };
}

function isAkshareKey(key: string) {
  return key.startsWith("AK_");
}

function mergeAkTokens(tokens: string[]) {
  const merged: string[] = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const current = tokens[index];
    const next = tokens[index + 1];
    const nextNext = tokens[index + 2];
    if (current === "NON" && next === "FARM") {
      merged.push("NON_FARM");
      index += 1;
      continue;
    }
    if (current === "NON" && next === "FIN" && nextNext === "CORP") {
      merged.push("NON_FIN_CORP");
      index += 2;
      continue;
    }
    if (current === "CHG" && ["3M", "6M", "1Y", "2Y", "3Y"].includes(next || "")) {
      merged.push(`CHG_${next}`);
      index += 1;
      continue;
    }
    if (current === "LPR" && ["1Y", "5Y"].includes(next || "")) {
      merged.push(`LPR_${next}`);
      index += 1;
      continue;
    }
    if (current === "CURRENT" && ["YOY", "MOM"].includes(next || "")) {
      merged.push(`CURRENT_${next}`);
      index += 1;
      continue;
    }
    if (current === "CUMULATIVE" && next === "YOY") {
      merged.push("CUMULATIVE_YOY");
      index += 1;
      continue;
    }
    if (current === "NEW" && ["YOY", "MOM", "BASE"].includes(next || "")) {
      merged.push(`NEW_${next}`);
      index += 1;
      continue;
    }
    if (current === "SECOND" && ["YOY", "MOM", "BASE"].includes(next || "")) {
      merged.push(`SECOND_${next}`);
      index += 1;
      continue;
    }
    if (current === "BOOM" && ["INDEX", "YOY", "MOM"].includes(next || "")) {
      merged.push(`BOOM_${next}`);
      index += 1;
      continue;
    }
    if (current === "CONFIDENCE" && ["INDEX", "YOY", "MOM"].includes(next || "")) {
      merged.push(`CONFIDENCE_${next}`);
      index += 1;
      continue;
    }
    merged.push(current);
  }
  return merged;
}

function mapAkTokenToChinese(token: string) {
  if (AK_TOKEN_LABELS[token]) {
    return AK_TOKEN_LABELS[token];
  }
  const yearMatch = token.match(/^(\d+)Y$/);
  if (yearMatch) {
    return `${yearMatch[1]}年期`;
  }
  const monthMatch = token.match(/^(\d+)M$/);
  if (monthMatch) {
    return `${monthMatch[1]}个月`;
  }
  return token;
}

export function formatIndicatorLabel(indicator: string) {
  if (!indicator) {
    return "";
  }
  if (!isAkshareKey(indicator)) {
    return WORLD_BANK_LABELS[indicator] || indicator;
  }
  const tokens = mergeAkTokens(indicator.slice(3).split("_").filter(Boolean));
  return tokens.map(mapAkTokenToChinese).join(" / ");
}

export function formatFamilyLabel(family: string) {
  if (!family) {
    return "";
  }
  if (WORLD_BANK_LABELS[family]) {
    return WORLD_BANK_LABELS[family];
  }
  const tokens = mergeAkTokens(family.split("_").filter(Boolean));
  return tokens.map(mapAkTokenToChinese).join(" / ");
}

function formatCompactNumberZh(value: number) {
  const abs = Math.abs(value);
  if (abs >= 1e12) return `${(value / 1e12).toFixed(abs >= 1e13 ? 1 : 2)}万亿`;
  if (abs >= 1e8) return `${(value / 1e8).toFixed(abs >= 1e9 ? 1 : 2)}亿`;
  if (abs >= 1e4) return `${(value / 1e4).toFixed(abs >= 1e5 ? 1 : 2)}万`;
  return formatNumber(value);
}

function normalizeFamily(indicator: string) {
  if (!indicator) {
    return "";
  }
  if (!isAkshareKey(indicator)) {
    return indicator.toUpperCase();
  }
  const tokens = mergeAkTokens(indicator.slice(3).split("_").filter(Boolean));
  if (tokens.includes("GDP")) return "GDP";
  if (tokens.includes("CPI")) return "CPI";
  if (tokens.includes("UNEMP")) return "UNEMP";
  return tokens.join("_");
}

export function formatValue(item: SnapshotCard | { value: number; family: string }) {
  const family = item.family.toUpperCase();
  if (
    family.includes("YOY") ||
    family.includes("MOM") ||
    family === "CPI" ||
    family === "PPI" ||
    family === "UNEMP"
  ) {
    return formatLoosePercent(item.value);
  }
  return formatCompactNumberZh(item.value);
}

export function formatFullValue(item: SnapshotCard | { value: number; family: string }) {
  const family = item.family.toUpperCase();
  if (
    family.includes("YOY") ||
    family.includes("MOM") ||
    family === "CPI" ||
    family === "PPI" ||
    family === "UNEMP"
  ) {
    return formatLoosePercent(item.value);
  }
  return formatNumber(item.value);
}

export function formatScore(score?: number) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return "--";
  }
  return score.toFixed(2);
}

export function buildMacroSnapshotCacheKey() {
  return "macro:snapshots:latest";
}

export function buildMacroSeriesCacheKey(key: string, start: string, end: string) {
  return `macro:series:${key}:start=${start || "none"}:end=${end || "none"}`;
}

export function buildSnapshotCard(item: MacroItem): SnapshotCard {
  const { indicator, country } = parseMacroKey(item.key);
  const source: MacroSource = isAkshareKey(item.key) ? "akshare" : "world_bank";
  return {
    ...item,
    source,
    country,
    family: normalizeFamily(indicator),
    label: formatIndicatorLabel(indicator),
    countryLabel: COUNTRY_LABELS[country] || country,
    sourceLabel: source === "world_bank" ? "世界银行" : "AkShare",
  };
}

export function paginate<T>(items: T[], page: number, pageSize: number) {
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(Math.max(1, page), maxPage);
  const offset = (safePage - 1) * pageSize;
  return {
    page: safePage,
    maxPage,
    items: items.slice(offset, offset + pageSize),
  };
}

export function buildMacroSeriesChartOption(selectedCard: SnapshotCard, series: MacroSeries) {
  const isWorldBank = selectedCard.source === "world_bank";
  const valueColor = isWorldBank ? marketTheme.chart.worldBank : marketTheme.chart.akshare;
  const areaColor = isWorldBank ? marketTheme.chart.coolArea : marketTheme.chart.warmArea;
  return {
    animation: false,
    color: [valueColor, marketTheme.chart.axis],
    tooltip: {
      trigger: "axis",
      formatter: (params: Array<{ axisValue?: string; seriesName?: string; value?: number }>) => {
        if (!params.length) return "";
        const lines = [params[0]?.axisValue || ""];
        for (const item of params) {
          if (!item) continue;
          const valueText =
            item.seriesName === "评分"
              ? formatScore(item.value)
              : formatValue({ value: Number(item.value || 0), family: selectedCard.family });
          lines.push(`${item.seriesName}: ${valueText}`);
        }
        return lines.join("<br/>");
      },
    },
    legend: { data: ["数值", "评分"], top: 0 },
    grid: { left: 48, right: 56, top: 46, bottom: 40 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: series.items.map((item) => item.date),
      axisLine: { lineStyle: { color: marketTheme.chart.axis } },
      axisLabel: { color: marketTheme.chart.axis },
    },
    yAxis: [
      {
        type: "value",
        scale: true,
        axisLabel: {
          formatter: (value: number) => formatValue({ value, family: selectedCard.family }),
        },
        splitLine: { lineStyle: { color: marketTheme.chart.grid } },
      },
      {
        type: "value",
        min: 0,
        max: 1,
        axisLabel: { formatter: (value: number) => value.toFixed(1) },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "数值",
        type: "line",
        data: series.items.map((item) => item.value),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2.6 },
        areaStyle: { color: areaColor, opacity: 0.18 },
      },
      {
        name: "评分",
        type: "line",
        yAxisIndex: 1,
        data: series.items.map((item) => item.score ?? 0),
        smooth: true,
        showSymbol: false,
        lineStyle: { type: "dashed" },
      },
    ],
  };
}
