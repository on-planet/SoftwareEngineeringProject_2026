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
const SOURCE_CARD_LIMIT = 12;
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
  SAU: "沙特阿拉伯",
  ZAF: "南非",
  ARG: "阿根廷",
  EUU: "欧盟",
  EUR: "欧元区",
};

const AK_TOKEN_LABELS: Record<string, string> = {
  GDP: "国内生产总值",
  CPI: "居民消费价格指数",
  PPI: "工业生产者出厂价格指数",
  M2: "M2",
  YOY: "同比",
  MOM: "环比",
  PMI: "PMI",
  IP: "工业增加值",
  FX: "外汇",
  RESERVES: "储备",
  EXPORTS: "出口",
  IMPORTS: "进口",
  TRADE: "贸易",
  BALANCE: "顺差",
  CAIXIN: "财新",
  SERVICES: "服务业",
  NON: "非",
  MAN: "制造业",
  RETAIL: "零售",
  SALES: "销售",
  UNEMP: "失业率",
  NON_FARM: "非农就业",
  CORE: "核心",
  PCE: "PCE",
  CNBS: "宏观杠杆率",
  HOUSEHOLD: "住户部门",
  NON_FIN_CORP: "非金融企业部门",
  GENERAL_GOV: "政府部门",
  CENTRAL_GOV: "中央政府",
  LOCAL_GOV: "地方政府",
  REAL_ECONOMY: "实体经济部门",
  FIN_ASSET: "金融部门资产方",
  FIN_LIABILITY: "金融部门负债方",
  ACTUAL: "今值",
  FORECAST: "预测值",
  PREVIOUS: "前值",
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
    if ((current === "GENERAL" || current === "CENTRAL" || current === "LOCAL") && next === "GOV") {
      merged.push(`${current}_GOV`);
      index += 1;
      continue;
    }
    if (current === "REAL" && next === "ECONOMY") {
      merged.push("REAL_ECONOMY");
      index += 1;
      continue;
    }
    if (current === "FIN" && (next === "ASSET" || next === "LIABILITY")) {
      merged.push(`FIN_${next}`);
      index += 1;
      continue;
    }
    merged.push(current);
  }
  return merged;
}

function formatIndicatorLabel(indicator: string) {
  if (!indicator) {
    return "";
  }
  if (!isAkshareKey(indicator)) {
    return WORLD_BANK_LABELS[indicator] || indicator;
  }
  const tokens = mergeAkTokens(indicator.slice(3).split("_").filter(Boolean));
  return tokens.map((token) => AK_TOKEN_LABELS[token] || token).join(" / ");
}

function formatCompactNumberZh(value: number) {
  const abs = Math.abs(value);
  if (abs >= 1e12) {
    return `${(value / 1e12).toFixed(abs >= 1e13 ? 1 : 2)}万亿`;
  }
  if (abs >= 1e8) {
    return `${(value / 1e8).toFixed(abs >= 1e9 ? 1 : 2)}亿`;
  }
  if (abs >= 1e4) {
    return `${(value / 1e4).toFixed(abs >= 1e5 ? 1 : 2)}万`;
  }
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
  const [worldBankPage, setWorldBankPage] = useState(1);
  const [aksharePage, setAksharePage] = useState(1);
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
        if (!active) {
          return;
        }
        setSnapshotItems(items);
        writePersistentCache(buildMacroSnapshotCacheKey(), items);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setSnapshotItems([]);
        setError(err.message || "宏观快照加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const cards = useMemo(() => snapshotItems.map(buildSnapshotCard), [snapshotItems]);

  const visibleCards = useMemo(() => {
    const worldBankCards = cards.filter((item) => item.source === "world_bank");
    const coreCoverage = new Set(worldBankCards.map((item) => `${item.country}:${item.family}`));
    const filteredAkshare = cards.filter((item) => {
      if (item.source !== "akshare") {
        return false;
      }
      return !coreCoverage.has(`${item.country}:${item.family}`);
    });

    const keyword = search.trim().toLowerCase();
    const applyFilters = (items: SnapshotCard[]) =>
      items
        .filter((item) => (country ? item.country === country : true))
        .filter((item) => (family ? item.family === family : true))
        .filter((item) => {
          if (!keyword) {
            return true;
          }
          return [item.key, item.label, item.countryLabel, item.family].join(" ").toLowerCase().includes(keyword);
        })
        .sort((left, right) => {
          const dateCompare = left.date.localeCompare(right.date);
          if (dateCompare !== 0) {
            return sort === "asc" ? dateCompare : -dateCompare;
          }
          return left.label.localeCompare(right.label);
        });

    return {
      worldBank: applyFilters(worldBankCards),
      akshare: applyFilters(filteredAkshare),
      hiddenAkshareDuplicates: cards.filter((item) => item.source === "akshare").length - filteredAkshare.length,
    };
  }, [cards, country, family, search, sort]);

  const allVisibleCards = useMemo(
    () => [...visibleCards.worldBank, ...visibleCards.akshare],
    [visibleCards.akshare, visibleCards.worldBank],
  );

  useEffect(() => {
    if (!allVisibleCards.length) {
      if (selectedKey) {
        setSelectedKey("");
      }
      return;
    }
    if (!allVisibleCards.some((item) => item.key === selectedKey)) {
      setSelectedKey(allVisibleCards[0].key);
    }
  }, [allVisibleCards, selectedKey]);

  useEffect(() => {
    setWorldBankPage(1);
    setAksharePage(1);
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
        if (!active) {
          return;
        }
        setSeries(payload as MacroSeries);
        writePersistentCache(cacheKey, payload as MacroSeries);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setSeries(null);
        setError(err.message || "宏观序列加载失败");
      })
      .finally(() => {
        if (active) {
          setSeriesLoading(false);
        }
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

  const pagedWorldBank = useMemo(
    () => paginate(visibleCards.worldBank, worldBankPage, SOURCE_CARD_LIMIT),
    [visibleCards.worldBank, worldBankPage],
  );

  const pagedAkshare = useMemo(
    () => paginate(visibleCards.akshare, aksharePage, SOURCE_CARD_LIMIT),
    [visibleCards.akshare, aksharePage],
  );

  useEffect(() => {
    if (pagedWorldBank.page !== worldBankPage) {
      setWorldBankPage(pagedWorldBank.page);
    }
  }, [pagedWorldBank.page, worldBankPage]);

  useEffect(() => {
    if (pagedAkshare.page !== aksharePage) {
      setAksharePage(pagedAkshare.page);
    }
  }, [aksharePage, pagedAkshare.page]);

  const selectedCard = useMemo(
    () => allVisibleCards.find((item) => item.key === selectedKey) ?? null,
    [allVisibleCards, selectedKey],
  );

  const chartOption = useMemo(() => {
    if (!series || !series.items.length || !selectedCard) {
      return null;
    }
    return {
      animation: false,
      color: selectedCard.source === "world_bank" ? ["#0f766e", "#64748b"] : ["#b45309", "#64748b"],
      tooltip: {
        trigger: "axis",
        formatter: (params: Array<{ axisValue?: string; seriesName?: string; value?: number }>) => {
          if (!params.length) {
            return "";
          }
          const lines = [params[0]?.axisValue || ""];
          for (const item of params) {
            if (!item) {
              continue;
            }
            const valueText = item.seriesName === "评分" ? formatScore(item.value) : formatValue({ value: Number(item.value || 0), family: selectedCard.family });
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
              页面同时展示世界银行基础宏观序列与 AkShare 扩展指标。若 AkShare 指标与世界银行核心口径重复，则默认隐藏重复卡片，优先保留更稳定的基础口径。
            </p>
          </div>
        </div>
        <div className="hero-grid">
          <div className="hero-metric">
            <div className="helper">当前可见序列</div>
            <div className="hero-metric-value">{allVisibleCards.length}</div>
            <div className="helper">已合并数据源并过滤重复项</div>
          </div>
          <div className="hero-metric">
            <div className="helper">世界银行核心口径</div>
            <div className="hero-metric-value">{visibleCards.worldBank.length}</div>
            <div className="helper">跨国家可比的基础宏观快照</div>
          </div>
          <div className="hero-metric">
            <div className="helper">AkShare 扩展指标</div>
            <div className="hero-metric-value">{visibleCards.akshare.length}</div>
            <div className="helper">{`已隐藏 ${visibleCards.hiddenAkshareDuplicates} 个与世界银行重复的指标`}</div>
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
                  {formatIndicatorLabel(item)}
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
              <div className="helper">{selectedCard ? selectedCard.key : "请从下方卡片中选择一项"}</div>
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
                  {`完整值 ${formatFullValue(selectedCard)}`}
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
            <h2 className="section-title">世界银行核心口径</h2>
            <div className="helper">跨国家可比的基础宏观指标，优先展示长期稳定、覆盖面更广的口径。</div>
          </div>
          <div className="helper">{`${visibleCards.worldBank.length} 个序列`}</div>
        </div>
        {pagedWorldBank.items.length ? (
          <>
            <div className="grid grid-3">
              {pagedWorldBank.items.map((item) => {
                const active = item.key === selectedKey;
                return (
                  <button
                    key={item.key}
                    type="button"
                    className="card index-card index-card-button"
                    data-active={active}
                    onClick={() => setSelectedKey(item.key)}
                    style={{
                      textAlign: "left",
                      borderColor: active ? "rgba(15, 118, 110, 0.4)" : undefined,
                      background: active ? "linear-gradient(180deg, #ecfeff 0%, #ffffff 100%)" : undefined,
                    }}
                    title={`完整值：${formatFullValue(item)}`}
                  >
                    <div className="card-title">{item.label}</div>
                    <div className="helper">{`${item.countryLabel} | ${item.sourceLabel}`}</div>
                    <div style={{ marginTop: 10, fontSize: 24, fontWeight: 800, lineHeight: 1.15, wordBreak: "break-word" }}>{formatValue(item)}</div>
                    <div className="helper" style={{ marginTop: 6 }}>{`完整值 ${formatFullValue(item)}`}</div>
                    <div className="helper" style={{ marginTop: 8 }}>{`更新于 ${item.date}`}</div>
                  </button>
                );
              })}
            </div>
            <div className="toolbar" style={{ marginTop: 16, justifyContent: "space-between" }}>
              <div className="helper">{`第 ${pagedWorldBank.page} / ${pagedWorldBank.maxPage} 页`}</div>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="input" type="button" disabled={pagedWorldBank.page <= 1} onClick={() => setWorldBankPage((value) => value - 1)}>
                  上一页
                </button>
                <button
                  className="input"
                  type="button"
                  disabled={pagedWorldBank.page >= pagedWorldBank.maxPage}
                  onClick={() => setWorldBankPage((value) => value + 1)}
                >
                  下一页
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="helper">当前筛选条件下没有世界银行序列。</div>
        )}
      </section>

      <section>
        <div className="section-headline">
          <div>
            <h2 className="section-title">AkShare 扩展指标</h2>
            <div className="helper">
              展示发布型指标以及中国、美国、欧元区的更细颗粒度数据。与世界银行核心口径重复的 AkShare 指标会在这里自动隐藏。
            </div>
          </div>
          <div className="helper">{`${visibleCards.akshare.length} 个序列 | 已隐藏 ${visibleCards.hiddenAkshareDuplicates} 个重复项`}</div>
        </div>
        {pagedAkshare.items.length ? (
          <>
            <div className="grid grid-3">
              {pagedAkshare.items.map((item) => {
                const active = item.key === selectedKey;
                return (
                  <button
                    key={item.key}
                    type="button"
                    className="card index-card index-card-button"
                    data-active={active}
                    onClick={() => setSelectedKey(item.key)}
                    style={{
                      textAlign: "left",
                      borderColor: active ? "rgba(180, 83, 9, 0.38)" : undefined,
                      background: active ? "linear-gradient(180deg, #fff7ed 0%, #ffffff 100%)" : undefined,
                    }}
                    title={`完整值：${formatFullValue(item)}`}
                  >
                    <div className="card-title">{item.label}</div>
                    <div className="helper">{`${item.countryLabel} | ${item.sourceLabel}`}</div>
                    <div style={{ marginTop: 10, fontSize: 24, fontWeight: 800, lineHeight: 1.15, wordBreak: "break-word" }}>{formatValue(item)}</div>
                    <div className="helper" style={{ marginTop: 6 }}>{`完整值 ${formatFullValue(item)}`}</div>
                    <div className="helper" style={{ marginTop: 8 }}>{`更新于 ${item.date}`}</div>
                    <div className="helper" style={{ marginTop: 4 }}>{`评分 ${formatScore(item.score)}`}</div>
                  </button>
                );
              })}
            </div>
            <div className="toolbar" style={{ marginTop: 16, justifyContent: "space-between" }}>
              <div className="helper">{`第 ${pagedAkshare.page} / ${pagedAkshare.maxPage} 页`}</div>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="input" type="button" disabled={pagedAkshare.page <= 1} onClick={() => setAksharePage((value) => value - 1)}>
                  上一页
                </button>
                <button
                  className="input"
                  type="button"
                  disabled={pagedAkshare.page >= pagedAkshare.maxPage}
                  onClick={() => setAksharePage((value) => value + 1)}
                >
                  下一页
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="helper">当前筛选条件下没有 AkShare 序列。</div>
        )}
      </section>
    </div>
  );
}
