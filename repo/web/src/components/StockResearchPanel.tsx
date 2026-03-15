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
                    Open
                  </a>
                ) : null}
              </div>
              <div className="research-item-meta">
                <span>{item.published_at ? new Date(item.published_at).toLocaleString("zh-CN") : "Unknown time"}</span>
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
        setError(err.message || "Failed to load research panel");
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
    return <div className="helper">Loading research panel...</div>;
  }

  if (error) {
    return <div className="helper">Research panel failed: {error}</div>;
  }

  return (
    <div className="research-grid">
      <ResearchList
        title="Research Reports"
        items={payload?.reports ?? []}
        emptyText="No research reports available."
      />
      <ResearchList
        title="Earning Forecasts"
        items={payload?.earning_forecasts ?? []}
        emptyText="No earning forecasts available."
      />
    </div>
  );
}
