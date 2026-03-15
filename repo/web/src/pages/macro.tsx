import React, { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

import { getMacro, getMacroSeries } from "../services/api";
import { formatNumber } from "../utils/format";

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

type SortOrder = "asc" | "desc";

const INDICATOR_LABELS: Record<string, string> = {
  GDP: "GDP(美元)",
  CPI: "CPI(年增)",
  PPI: "PPI(年增)",
  UNEMP: "失业率",
  TRADE: "贸易占比",
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
};

const DEFAULT_KEY = "";
const SNAPSHOT_PAGE_LIMIT = 200;
const SNAPSHOT_PAGE_MAX = 10;

function parseMacroKey(key: string) {
  const [indicator, country] = key.split(":");
  return {
    key,
    indicator: indicator || "",
    country: country || "",
  };
}

function formatSeriesLabel(key: string): string {
  const { indicator, country } = parseMacroKey(key);
  const indicatorLabel = INDICATOR_LABELS[indicator] || indicator;
  const countryLabel = COUNTRY_LABELS[country] || country;
  return country ? `${indicatorLabel} - ${countryLabel}` : indicatorLabel;
}

async function loadMacroSnapshotItems(): Promise<MacroItem[]> {
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

  return merged;
}

export default function MacroPage() {
  const [snapshotItems, setSnapshotItems] = useState<MacroItem[]>([]);
  const [selectedKey, setSelectedKey] = useState(DEFAULT_KEY);
  const [series, setSeries] = useState<MacroSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [sort, setSort] = useState<SortOrder>("desc");
  const [limit, setLimit] = useState(40);
  const [page, setPage] = useState(1);
  const [indicator, setIndicator] = useState("");
  const [country, setCountry] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    loadMacroSnapshotItems()
      .then((res) => {
        if (!active) {
          return;
        }
        setSnapshotItems(res);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setSnapshotItems([]);
        setError(err.message || "加载宏观指标失败");
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

  const parsedKeys = useMemo(() => {
    const byKey = new Map<string, ReturnType<typeof parseMacroKey>>();
    snapshotItems.forEach((item) => {
      const parsed = parseMacroKey(item.key);
      if (parsed.indicator && parsed.country) {
        byKey.set(item.key, parsed);
      }
    });
    return Array.from(byKey.values()).sort((left, right) => left.key.localeCompare(right.key));
  }, [snapshotItems]);

  const indicatorOptions = useMemo(
    () => Array.from(new Set(parsedKeys.map((item) => item.indicator))).sort((left, right) => left.localeCompare(right)),
    [parsedKeys],
  );

  const countryOptions = useMemo(
    () => Array.from(new Set(parsedKeys.map((item) => item.country))).sort((left, right) => left.localeCompare(right)),
    [parsedKeys],
  );

  const filteredKeys = useMemo(() => {
    return parsedKeys
      .filter((item) => (indicator ? item.indicator === indicator : true))
      .filter((item) => (country ? item.country === country : true))
      .map((item) => item.key);
  }, [country, indicator, parsedKeys]);

  useEffect(() => {
    if (filteredKeys.length === 0) {
      if (selectedKey) {
        setSelectedKey(DEFAULT_KEY);
      }
      return;
    }
    if (!filteredKeys.includes(selectedKey)) {
      setSelectedKey(filteredKeys[0]);
    }
  }, [filteredKeys, selectedKey]);

  useEffect(() => {
    setPage(1);
  }, [country, indicator, limit, sort]);

  useEffect(() => {
    if (!selectedKey) {
      setSeries(null);
      setSeriesLoading(false);
      return;
    }
    let active = true;
    setSeriesLoading(true);
    getMacroSeries(selectedKey, {
      start: start || undefined,
      end: end || undefined,
    })
      .then((res) => {
        if (!active) {
          return;
        }
        setSeries(res as MacroSeries);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setSeries(null);
        setError(err.message || "加载宏观序列失败");
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

  const filteredSnapshotItems = useMemo(() => {
    return snapshotItems.filter((item) => {
      const parsed = parseMacroKey(item.key);
      if (indicator && parsed.indicator !== indicator) {
        return false;
      }
      if (country && parsed.country !== country) {
        return false;
      }
      return true;
    });
  }, [country, indicator, snapshotItems]);

  const sortedSnapshotItems = useMemo(() => {
    const next = [...filteredSnapshotItems];
    next.sort((left, right) => {
      const dateCompare = left.date.localeCompare(right.date);
      if (dateCompare !== 0) {
        return sort === "asc" ? dateCompare : -dateCompare;
      }
      return sort === "asc" ? left.key.localeCompare(right.key) : right.key.localeCompare(left.key);
    });
    return next;
  }, [filteredSnapshotItems, sort]);

  const total = sortedSnapshotItems.length;
  const maxPage = useMemo(() => Math.max(1, Math.ceil(total / limit)), [limit, total]);

  useEffect(() => {
    if (page > maxPage) {
      setPage(maxPage);
    }
  }, [maxPage, page]);

  const offset = useMemo(() => (page - 1) * limit, [page, limit]);

  const pagedSnapshotItems = useMemo(
    () => sortedSnapshotItems.slice(offset, offset + limit),
    [limit, offset, sortedSnapshotItems],
  );

  const chartTitle = useMemo(() => (selectedKey ? formatSeriesLabel(selectedKey) : ""), [selectedKey]);

  const seriesOption = useMemo(() => {
    if (!series || !series.items.length) {
      return null;
    }
    const labels = series.items.map((item) => item.date);
    const values = series.items.map((item) => item.value);
    const scores = series.items.map((item) => item.score ?? 0);
    return {
      animation: false,
      title: chartTitle ? { text: chartTitle, left: "center", textStyle: { fontSize: 14, fontWeight: 600 } } : undefined,
      tooltip: { trigger: "axis" },
      legend: { data: ["数值", "评分"], top: 28 },
      grid: { left: 48, right: 48, top: 64, bottom: 40 },
      xAxis: {
        type: "category",
        data: labels,
        boundaryGap: false,
      },
      yAxis: [
        { type: "value", scale: true },
        { type: "value", min: 0, max: 1 },
      ],
      series: [
        { name: "数值", type: "line", data: values, smooth: true, showSymbol: false },
        { name: "评分", type: "line", yAxisIndex: 1, data: scores, smooth: true, showSymbol: false },
      ],
    };
  }, [chartTitle, series]);

  if (loading) {
    return <div className="page">宏观指标加载中...</div>;
  }

  if (error) {
    return <div className="page">宏观指标加载失败：{error}</div>;
  }

  return (
    <div className="page">
      <section className="card" style={{ marginBottom: 16 }}>
        <div className="card-title" style={{ marginBottom: 12 }}>
          筛选条件
        </div>
        <div className="toolbar" style={{ flexWrap: "wrap", gap: 12 }}>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            开始日期
            <input className="input" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            结束日期
            <input className="input" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            排序
            <select className="select" value={sort} onChange={(event) => setSort(event.target.value as SortOrder)}>
              <option value="desc">倒序</option>
              <option value="asc">正序</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            每页
            <select className="select" value={limit} onChange={(event) => setLimit(Number(event.target.value) || 40)}>
              <option value={20}>20</option>
              <option value={40}>40</option>
              <option value={80}>80</option>
              <option value={120}>120</option>
            </select>
          </label>
          <div className="helper" style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 18 }}>
            <button type="button" onClick={() => setPage((prev) => Math.max(1, prev - 1))} disabled={page <= 1} className="input">
              上一页
            </button>
            <span>
              第 {page} / {maxPage} 页 · 共 {total} 条
            </span>
            <button
              type="button"
              onClick={() => setPage((prev) => Math.min(maxPage, prev + 1))}
              disabled={page >= maxPage}
              className="input"
            >
              下一页
            </button>
          </div>
        </div>
        <div className="helper" style={{ marginTop: 12 }}>
          日期范围只影响上方图表序列，国家和指标目录固定来自最新宏观快照。
        </div>
      </section>

      <section>
        <h2 className="section-title">宏观指标</h2>
        <div className="toolbar" style={{ marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
          <span className="helper">选择指标</span>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            指标
            <select
              className="select"
              value={indicator}
              onChange={(event) => {
                setIndicator(event.target.value);
              }}
            >
              <option value="">全部</option>
              {indicatorOptions.map((item) => (
                <option key={item} value={item}>
                  {INDICATOR_LABELS[item] || item}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            国家/地区
            <select
              className="select"
              value={country}
              onChange={(event) => {
                setCountry(event.target.value);
              }}
            >
              <option value="">全部</option>
              {countryOptions.map((item) => (
                <option key={item} value={item}>
                  {COUNTRY_LABELS[item] || item}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            序列
            <select className="select" value={selectedKey} onChange={(event) => setSelectedKey(event.target.value)}>
              {filteredKeys.length === 0 ? <option value="">暂无指标</option> : null}
              {filteredKeys.map((key) => (
                <option key={key} value={key}>
                  {formatSeriesLabel(key)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="card">
          {seriesLoading ? (
            <div>宏观序列加载中...</div>
          ) : !selectedKey ? (
            <div>请先选择指标序列</div>
          ) : seriesOption ? (
            <ReactECharts option={seriesOption} style={{ height: 320 }} />
          ) : (
            <div>当前序列暂无历史数据，接口会在首次访问时自动回填。</div>
          )}
        </div>
      </section>

      <section>
        <h2 className="section-title">最新指标快照</h2>
        {pagedSnapshotItems.length === 0 ? (
          <div className="helper">暂无宏观指标数据</div>
        ) : (
          <div className="grid grid-3">
            {pagedSnapshotItems.map((item) => {
              const { indicator: indicatorPart, country: countryPart } = parseMacroKey(item.key);
              const isActive = item.key === selectedKey;
              return (
                <button
                  key={`${item.key}-${item.date}`}
                  type="button"
                  className="card index-card index-card-button"
                  data-active={isActive}
                  onClick={() => setSelectedKey(item.key)}
                >
                  <div className="card-title">{INDICATOR_LABELS[indicatorPart] || indicatorPart}</div>
                  <div className="helper">
                    {COUNTRY_LABELS[countryPart] || countryPart} · {item.date}
                  </div>
                  <div style={{ marginTop: 6 }}>数值 {formatNumber(item.value)}</div>
                  <div className="helper" style={{ marginTop: 4 }}>
                    评分 {formatNumber(item.score ?? 0)}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
