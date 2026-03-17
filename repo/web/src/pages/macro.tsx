import React, { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

import { getMacro, getMacroSeries } from "../services/api";
import { formatLoosePercent, formatNumber } from "../utils/format";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

type MacroItem = {
  key: string;
  date: string;
  value: number;
  score?: number;
};

type MacroPage = {
  items: MacroItem[];
  total: number;
  limit: number;
  offset: number;
};

type MacroSeries = {
  key: string;
  items: { date: string; value: number; score?: number }[];
};

type MacroSource = "world_bank" | "akshare";
type SortOrder = "asc" | "desc";

type SnapshotCard = MacroItem & {
  source: MacroSource;
  country: string;
  family: string;
  label: string;
  countryLabel: string;
  sourceLabel: string;
};

const SNAPSHOT_PAGE_LIMIT = 200;
const SNAPSHOT_PAGE_MAX = 10;
const SNAPSHOT_CARD_LIMIT = 12;
const MACRO_SNAPSHOT_CACHE_TTL_MS = 10 * 60 * 1000;
const MACRO_SERIES_CACHE_TTL_MS = 10 * 60 * 1000;

const WORLD_BANK_LABELS: Record<string, string> = {
  GDP: "国内生产总值",
  CPI: "居民消费价格指数",
  UNEMP: "失业率",
  TRADE: "贸易开放度",
};

const COUNTRY_LABELS: Record<string, string> = {
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
  BALANCE: "顺差",
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
  LPR_1Y: "一年期LPR",
  LPR_5Y: "五年期LPR",
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
  CHG_3M: "近3月",
  CHG_6M: "近6月",
  CHG_1Y: "近1年",
  CHG_2Y: "近2年",
  CHG_3Y: "近3年",
};

function parseMacroKey(key: string) {
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

function formatIndicatorLabel(indicator: string) {
  if (!indicator) {
    return "";
  }
  if (!isAkshareKey(indicator)) {
    return WORLD_BANK_LABELS[indicator] || indicator;
  }
  const tokens = mergeAkTokens(indicator.slice(3).split("_").filter(Boolean));
  return tokens.map(mapAkTokenToChinese).join(" / ");
}

function formatFamilyLabel(family: string) {
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

function formatValue(item: SnapshotCard | { value: number; family: string }) {
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

function formatFullValue(item: SnapshotCard | { value: number; family: string }) {
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

function formatScore(score?: number) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return "--";
  }
  return score.toFixed(2);
}

async function loadLatestMacroSnapshotItems(): Promise<MacroItem[]> {
  const merged: MacroItem[] = [];
  let offset = 0;
  let total = Number.POSITIVE_INFINITY;
  for (let page = 0; page < SNAPSHOT_PAGE_MAX && offset < total; page += 1) {
    const response = (await getMacro({
      limit: SNAPSHOT_PAGE_LIMIT,
      offset,
      sort: "desc",
    })) as MacroPage;
    const items = response.items ?? [];
    merged.push(...items);
    total = Number(response.total ?? merged.length);
    if (items.length < SNAPSHOT_PAGE_LIMIT) {
      break;
    }
    offset += SNAPSHOT_PAGE_LIMIT;
  }
  const latestByKey = new Map<string, MacroItem>();
  for (const item of merged) {
    const current = latestByKey.get(item.key);
    if (!current || current.date < item.date) {
      latestByKey.set(item.key, item);
    }
  }
  return Array.from(latestByKey.values()).sort((left, right) => left.key.localeCompare(right.key));
}

function buildMacroSnapshotCacheKey() {
  return "macro:snapshots:latest";
}

function buildMacroSeriesCacheKey(key: string, start: string, end: string) {
  return `macro:series:${key}:start=${start || "none"}:end=${end || "none"}`;
}

function buildSnapshotCard(item: MacroItem): SnapshotCard {
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

function paginate<T>(items: T[], page: number, pageSize: number) {
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(Math.max(1, page), maxPage);
  const offset = (safePage - 1) * pageSize;
  return {
    page: safePage,
    maxPage,
    items: items.slice(offset, offset + pageSize),
  };
}

export default function MacroPage() {
  const [snapshotItems, setSnapshotItems] = useState<MacroItem[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [series, setSeries] = useState<MacroSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [search, setSearch] = useState("");
  const [country, setCountry] = useState("");
  const [family, setFamily] = useState("");
  const [snapshotPage, setSnapshotPage] = useState(1);
  const [sort, setSort] = useState<SortOrder>("desc");

  useEffect(() => {
    let active = true;
    const cachedItems = readPersistentCache<MacroItem[]>(
      buildMacroSnapshotCacheKey(),
      MACRO_SNAPSHOT_CACHE_TTL_MS,
    );
    if (cachedItems?.length) {
      setSnapshotItems(cachedItems);
      setLoading(false);
    } else {
      setLoading(true);
    }

    loadLatestMacroSnapshotItems()
      .then((items) => {
        if (!active) return;
        setSnapshotItems(items);
        writePersistentCache(buildMacroSnapshotCacheKey(), items);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setSnapshotItems([]);
        setError(err.message || "宏观快照加载失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const cards = useMemo(() => snapshotItems.map(buildSnapshotCard), [snapshotItems]);

  const visibleCards = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return cards
      .filter((item) => (country ? item.country === country : true))
      .filter((item) => (family ? item.family === family : true))
      .filter((item) => {
        if (!keyword) return true;
        return [item.key, item.label, item.countryLabel, item.family].join(" ").toLowerCase().includes(keyword);
      })
      .sort((left, right) => {
        const dateCompare = left.date.localeCompare(right.date);
        if (dateCompare !== 0) {
          return sort === "asc" ? dateCompare : -dateCompare;
        }
        return left.label.localeCompare(right.label);
      });
  }, [cards, country, family, search, sort]);

  useEffect(() => {
    if (!visibleCards.length) {
      if (selectedKey) setSelectedKey("");
      return;
    }
    if (!visibleCards.some((item) => item.key === selectedKey)) {
      setSelectedKey(visibleCards[0].key);
    }
  }, [selectedKey, visibleCards]);

  useEffect(() => {
    setSnapshotPage(1);
  }, [country, family, search, sort]);

  useEffect(() => {
    if (!selectedKey) {
      setSeries(null);
      setSeriesLoading(false);
      return;
    }

    let active = true;
    const cacheKey = buildMacroSeriesCacheKey(selectedKey, start, end);
    const cachedSeries = readPersistentCache<MacroSeries>(cacheKey, MACRO_SERIES_CACHE_TTL_MS);
    if (cachedSeries?.items?.length) {
      setSeries(cachedSeries);
      setSeriesLoading(false);
    } else {
      setSeriesLoading(true);
    }

    getMacroSeries(selectedKey, {
      start: start || undefined,
      end: end || undefined,
    })
      .then((payload) => {
        if (!active) return;
        setSeries(payload as MacroSeries);
        writePersistentCache(cacheKey, payload as MacroSeries);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setSeries(null);
        setError(err.message || "宏观序列加载失败");
      })
      .finally(() => {
        if (active) setSeriesLoading(false);
      });

    return () => {
      active = false;
    };
  }, [end, selectedKey, start]);

  const countryOptions = useMemo(
    () => Array.from(new Set(cards.map((item) => item.country))).sort((left, right) => left.localeCompare(right)),
    [cards],
  );

  const familyOptions = useMemo(
    () => Array.from(new Set(cards.map((item) => item.family))).sort((left, right) => left.localeCompare(right)),
    [cards],
  );

  const pagedSnapshots = useMemo(
    () => paginate(visibleCards, snapshotPage, SNAPSHOT_CARD_LIMIT),
    [snapshotPage, visibleCards],
  );

  useEffect(() => {
    if (pagedSnapshots.page !== snapshotPage) {
      setSnapshotPage(pagedSnapshots.page);
    }
  }, [pagedSnapshots.page, snapshotPage]);

  const selectedCard = useMemo(
    () => visibleCards.find((item) => item.key === selectedKey) ?? null,
    [selectedKey, visibleCards],
  );

  const chartOption = useMemo(() => {
    if (!series || !series.items.length || !selectedCard) return null;
    return {
      animation: false,
      color: selectedCard.source === "world_bank" ? ["#0f766e", "#64748b"] : ["#b45309", "#64748b"],
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
      },
      yAxis: [
        {
          type: "value",
          scale: true,
          axisLabel: {
            formatter: (value: number) => formatValue({ value, family: selectedCard.family }),
          },
        },
        { type: "value", min: 0, max: 1, axisLabel: { formatter: (value: number) => value.toFixed(1) } },
      ],
      series: [
        {
          name: "数值",
          type: "line",
          data: series.items.map((item) => item.value),
          smooth: true,
          showSymbol: false,
          areaStyle: { opacity: 0.08 },
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
  }, [selectedCard, series]);

  const latestPoint = series?.items?.[series.items.length - 1] ?? null;

  if (loading) {
    return <div className="page">宏观数据加载中...</div>;
  }

  if (error && !cards.length) {
    return <div className="page">{`宏观数据加载失败：${error}`}</div>;
  }

  return (
    <div className="page">
      <section className="card hero-card">
        <div className="page-header">
          <div>
            <h1 className="page-title">宏观数据看板</h1>
            <p className="helper" style={{ marginTop: 8, maxWidth: 780 }}>
              世界银行核心口径与 AkShare 扩展指标已合并为统一快照列表。
            </p>
          </div>
        </div>
        <div className="toolbar" style={{ marginTop: 8 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            搜索
            <input className="input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="GDP / CPI / 非农 / 中国" />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            国家或地区
            <select className="select" value={country} onChange={(event) => setCountry(event.target.value)}>
              <option value="">全部</option>
              {countryOptions.map((item) => (
                <option key={item} value={item}>
                  {COUNTRY_LABELS[item] || item}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            指标类别
            <select className="select" value={family} onChange={(event) => setFamily(event.target.value)}>
              <option value="">全部</option>
              {familyOptions.map((item) => (
                <option key={item} value={item}>
                  {formatFamilyLabel(item)}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            排序
            <select className="select" value={sort} onChange={(event) => setSort(event.target.value as SortOrder)}>
              <option value="desc">最新优先</option>
              <option value="asc">最早优先</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            序列开始日期
            <input className="input" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            序列结束日期
            <input className="input" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
          </label>
        </div>
      </section>

      <section className="split-grid">
        <div className="card">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 4 }}>
                当前选中序列
              </h2>
              <div className="helper">{selectedCard ? selectedCard.key : "请从下方快照中选择一个序列"}</div>
            </div>
            {selectedCard ? (
              <div
                style={{
                  borderRadius: 999,
                  padding: "8px 12px",
                  background: selectedCard.source === "world_bank" ? "rgba(15, 118, 110, 0.12)" : "rgba(180, 83, 9, 0.12)",
                  color: selectedCard.source === "world_bank" ? "#0f766e" : "#b45309",
                  fontSize: 12,
                  fontWeight: 700,
                }}
              >
                {selectedCard.sourceLabel}
              </div>
            ) : null}
          </div>
          {seriesLoading ? <div className="helper">序列加载中...</div> : null}
          {!seriesLoading && chartOption ? <ReactECharts option={chartOption} style={{ height: 320 }} /> : null}
          {!seriesLoading && !chartOption ? <div className="helper">暂无可展示序列。</div> : null}
        </div>

        <div className="card">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 4 }}>
                关键摘要
              </h2>
              <div className="helper">当前所选宏观序列的最新快照</div>
            </div>
          </div>
          {!selectedCard ? (
            <div className="helper">选择一个序列卡片后可查看详情。</div>
          ) : (
            <div className="summary-grid" style={{ marginTop: 0 }}>
              <div className="summary-card">
                <div className="helper">指标名称</div>
                <div className="stock-card-title" style={{ marginTop: 8 }}>
                  {selectedCard.label}
                </div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {selectedCard.countryLabel}
                </div>
              </div>
              <div className="summary-card">
                <div className="helper">最新数值</div>
                <div className="stock-score-value">{formatValue(selectedCard)}</div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {selectedCard.date}
                </div>
                <div className="helper" style={{ marginTop: 4 }}>
                  {`完整值：${formatFullValue(selectedCard)}`}
                </div>
              </div>
              <div className="summary-card">
                <div className="helper">最新评分</div>
                <div className="stock-score-value">{formatScore(latestPoint?.score ?? selectedCard.score)}</div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {series ? `已加载 ${series.items.length} 个历史点` : "尚未加载历史序列"}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      <section>
        <div className="section-headline">
          <div>
            <h2 className="section-title">宏观快照（合并）</h2>
            <div className="helper">世界银行核心口径和 AkShare 扩展指标统一展示。</div>
          </div>
          <div className="helper">{`${visibleCards.length} 个序列`}</div>
        </div>
        {pagedSnapshots.items.length ? (
          <>
            <div className="grid grid-3">
              {pagedSnapshots.items.map((item) => {
                const active = item.key === selectedKey;
                const isWorldBank = item.source === "world_bank";
                return (
                  <button
                    key={item.key}
                    type="button"
                    className="card index-card index-card-button"
                    data-active={active}
                    onClick={() => setSelectedKey(item.key)}
                    style={{
                      textAlign: "left",
                      borderColor: active ? (isWorldBank ? "rgba(15, 118, 110, 0.4)" : "rgba(180, 83, 9, 0.38)") : undefined,
                      background: active
                        ? isWorldBank
                          ? "linear-gradient(180deg, #ecfeff 0%, #ffffff 100%)"
                          : "linear-gradient(180deg, #fff7ed 0%, #ffffff 100%)"
                        : undefined,
                    }}
                    title={`完整值：${formatFullValue(item)}`}
                  >
                    <div className="card-title">{item.label}</div>
                    <div className="helper">{`${item.countryLabel} | ${item.sourceLabel}`}</div>
                    <div style={{ marginTop: 10, fontSize: 24, fontWeight: 800, lineHeight: 1.15, wordBreak: "break-word" }}>
                      {formatValue(item)}
                    </div>
                    <div className="helper" style={{ marginTop: 6 }}>{`完整值：${formatFullValue(item)}`}</div>
                    <div className="helper" style={{ marginTop: 8 }}>{`更新于 ${item.date}`}</div>
                    <div className="helper" style={{ marginTop: 4 }}>{`评分 ${formatScore(item.score)}`}</div>
                  </button>
                );
              })}
            </div>
            <div className="toolbar" style={{ marginTop: 16, justifyContent: "space-between" }}>
              <div className="helper">{`第 ${pagedSnapshots.page} / ${pagedSnapshots.maxPage} 页`}</div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="input"
                  type="button"
                  disabled={pagedSnapshots.page <= 1}
                  onClick={() => setSnapshotPage((value) => value - 1)}
                >
                  上一页
                </button>
                <button
                  className="input"
                  type="button"
                  disabled={pagedSnapshots.page >= pagedSnapshots.maxPage}
                  onClick={() => setSnapshotPage((value) => value + 1)}
                >
                  下一页
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="helper">当前筛选条件下没有可展示的宏观序列。</div>
        )}
      </section>
    </div>
  );
}
