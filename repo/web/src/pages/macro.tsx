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

export default function MacroPage() {
  const [items, setItems] = useState<MacroItem[]>([]);
  const [selectedKey, setSelectedKey] = useState(DEFAULT_KEY);
  const [series, setSeries] = useState<MacroSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [sort, setSort] = useState<SortOrder>("desc");
  const [limit, setLimit] = useState(120);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [indicator, setIndicator] = useState("");
  const [country, setCountry] = useState("");

  const offset = useMemo(() => (page - 1) * limit, [page, limit]);
  const maxPage = useMemo(() => Math.max(1, Math.ceil(total / limit)), [total, limit]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getMacro({
      limit,
      offset,
      sort,
      start: start || undefined,
      end: end || undefined,
    })
      .then((res) => {
        if (!active) return;
        const pageData = res as MacroPage;
        setItems(pageData.items ?? []);
        setTotal(pageData.total ?? 0);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message || "加载宏观指标失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [end, limit, offset, sort, start]);

  const keys = useMemo(() => Array.from(new Set(items.map((item) => item.key))), [items]);

  const parsedKeys = useMemo(() => {
    return keys
      .map((key) => {
        const [indicatorPart, countryPart] = key.split(":");
        return { key, indicator: indicatorPart || "", country: countryPart || "" };
      })
      .filter((item) => item.indicator && item.country);
  }, [keys]);

  const indicatorOptions = useMemo(() => {
    return Array.from(new Set(parsedKeys.map((item) => item.indicator)));
  }, [parsedKeys]);

  const countryOptions = useMemo(() => {
    return Array.from(new Set(parsedKeys.map((item) => item.country)));
  }, [parsedKeys]);

  const filteredKeys = useMemo(() => {
    return parsedKeys
      .filter((item) => (indicator ? item.indicator === indicator : true))
      .filter((item) => (country ? item.country === country : true))
      .map((item) => item.key);
  }, [country, indicator, parsedKeys]);

  useEffect(() => {
    if (filteredKeys.length === 0) {
      if (selectedKey) {
        setSelectedKey("");
      }
      return;
    }
    if (!filteredKeys.includes(selectedKey)) {
      setSelectedKey(filteredKeys[0]);
    }
  }, [filteredKeys, selectedKey]);

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
        if (!active) return;
        setSeries(res as MacroSeries);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setSeries(null);
        setError(err.message || "加载宏观序列失败");
      })
      .finally(() => {
        if (active) setSeriesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [end, selectedKey, start]);

  const latestByKey = useMemo(() => {
    const map = new Map<string, MacroItem>();
    items.forEach((item) => {
      const existing = map.get(item.key);
      if (!existing || new Date(item.date) > new Date(existing.date)) {
        map.set(item.key, item);
      }
    });
    return Array.from(map.values());
  }, [items]);

  const chartTitle = useMemo(() => {
    if (!selectedKey) return "";
    const [indicatorPart, countryPart] = selectedKey.split(":");
    const indicatorLabel = INDICATOR_LABELS[indicatorPart] || indicatorPart;
    const countryLabel = COUNTRY_LABELS[countryPart] || countryPart;
    return countryPart ? `${indicatorLabel} - ${countryLabel}` : indicatorLabel;
  }, [selectedKey]);

  const seriesOption = useMemo(() => {
    if (!series || !series.items.length) return null;
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
            <input
              className="input"
              type="date"
              value={start}
              onChange={(event) => {
                setStart(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            结束日期
            <input
              className="input"
              type="date"
              value={end}
              onChange={(event) => {
                setEnd(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            排序
            <select
              className="select"
              value={sort}
              onChange={(event) => {
                setSort(event.target.value as SortOrder);
                setPage(1);
              }}
            >
              <option value="desc">倒序</option>
              <option value="asc">正序</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            每页
            <select
              className="select"
              value={limit}
              onChange={(event) => {
                setLimit(Number(event.target.value) || 120);
                setPage(1);
              }}
            >
              <option value={50}>50</option>
              <option value={80}>80</option>
              <option value={120}>120</option>
              <option value={200}>200</option>
            </select>
          </label>
          <div className="helper" style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 18 }}>
            <button type="button" onClick={() => setPage((prev) => Math.max(1, prev - 1))} disabled={page <= 1} className="input">
              上一页
            </button>
            <span>
              第 {page} / {maxPage} 页 · 共 {total} 条
            </span>
            <button type="button" onClick={() => setPage((prev) => Math.min(maxPage, prev + 1))} disabled={page >= maxPage} className="input">
              下一页
            </button>
          </div>
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
                setPage(1);
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
                setPage(1);
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
                  {key}
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
            <div>暂无宏观序列数据</div>
          )}
        </div>
      </section>

      <section>
        <h2 className="section-title">最新指标快照</h2>
        {latestByKey.length === 0 ? (
          <div className="helper">暂无宏观指标数据</div>
        ) : (
          <div className="grid grid-3">
            {latestByKey.map((item) => {
              const [indicatorPart, countryPart] = item.key.split(":");
              return (
                <div key={`${item.key}-${item.date}`} className="card">
                  <div className="card-title">{INDICATOR_LABELS[indicatorPart] || indicatorPart}</div>
                  <div className="helper">
                    {COUNTRY_LABELS[countryPart] || countryPart} · {item.date}
                  </div>
                  <div style={{ marginTop: 6 }}>数值 {formatNumber(item.value)}</div>
                  <div className="helper" style={{ marginTop: 4 }}>
                    评分 {formatNumber(item.score ?? 0)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
