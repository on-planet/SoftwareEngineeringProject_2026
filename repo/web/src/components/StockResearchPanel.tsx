import React, { useEffect, useState } from "react";

import { getStockResearch } from "../services/api";

type ResearchItem = {
  title: string;
  published_at?: string | null;
  link?: string | null;
  summary?: string | null;
  institution?: string | null;
  rating?: string | null;
  source?: string | null;
};

type ResearchResponse = {
  symbol: string;
  reports: ResearchItem[];
  earning_forecasts: ResearchItem[];
};

type Props = {
  symbol: string;
};

function ResearchList({ title, items, emptyText }: { title: string; items: ResearchItem[]; emptyText: string }) {
  return (
    <div className="research-section">
      <div className="card-title">{title}</div>
      {!items.length ? <div className="helper">{emptyText}</div> : null}
      {items.length ? (
        <div className="research-list">
          {items.map((item, index) => (
            <article key={`${title}-${item.title}-${item.published_at ?? index}`} className="research-item">
              <div className="research-item-top">
                <div className="research-item-title">{item.title}</div>
                {item.link ? (
                  <a className="subtle-link" href={item.link} target="_blank" rel="noreferrer">
                    查看原文
                  </a>
                ) : null}
              </div>
              <div className="research-item-meta">
                <span>{item.published_at ? new Date(item.published_at).toLocaleString("zh-CN") : "时间未知"}</span>
                {item.source ? <span>{item.source}</span> : null}
              </div>
              {item.institution || item.rating ? (
                <div className="tag-row">
                  {item.institution ? <span className="tag-pill">{item.institution}</span> : null}
                  {item.rating ? <span className="tag-pill">{item.rating}</span> : null}
                </div>
              ) : null}
              {item.summary ? <div className="research-item-summary">{item.summary}</div> : null}
            </article>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function StockResearchPanel({ symbol }: Props) {
  const [payload, setPayload] = useState<ResearchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getStockResearch(symbol, { report_limit: 8, forecast_limit: 8 })
      .then((res) => {
        if (!active) {
          return;
        }
        setPayload(res as ResearchResponse);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setPayload(null);
        setError(err.message || "研报面板加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [symbol]);

  if (loading) {
    return <div className="helper">研报与业绩预告加载中...</div>;
  }

  if (error) {
    return <div className="helper">研报与业绩预告加载失败：{error}</div>;
  }

  return (
    <div className="research-grid">
      <ResearchList title="最新研报" items={payload?.reports ?? []} emptyText="暂无研报数据。" />
      <ResearchList title="业绩预告" items={payload?.earning_forecasts ?? []} emptyText="暂无业绩预告数据。" />
    </div>
  );
}
