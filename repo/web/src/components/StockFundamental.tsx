import React, { useEffect, useState } from "react";

import { getFundamental, getStock } from "../services/api";
import { formatNumber } from "../utils/format";

type StockProfile = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
};

type Fundamental = {
  symbol: string;
  score: number;
  summary: string;
  updated_at: string;
} | null;

type Props = {
  symbol: string;
};

export function StockFundamental({ symbol }: Props) {
  const [profile, setProfile] = useState<StockProfile | null>(null);
  const [fundamental, setFundamental] = useState<Fundamental>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([getStock(symbol), getFundamental(symbol)])
      .then(([profileRes, fundamentalRes]) => {
        if (!active) {
          return;
        }
        setProfile(profileRes as StockProfile);
        setFundamental(fundamentalRes as Fundamental);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "Failed to load stock profile");
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
    return <div className="card helper">Loading stock profile...</div>;
  }

  if (error) {
    return <div className="card helper">Stock profile failed: {error}</div>;
  }

  if (!profile) {
    return <div className="card helper">No stock profile available.</div>;
  }

  return (
    <div className="card">
      <div className="stock-profile-header">
        <div>
          <div className="stock-profile-title">{profile.name || profile.symbol}</div>
          <div className="helper">
            {profile.symbol} · {profile.market}
          </div>
        </div>
        <div className="stock-profile-meta">
          <div className="helper">Sector</div>
          <div>{profile.sector || "Unknown"}</div>
        </div>
      </div>
      <div className="stock-profile-score">
        <div className="helper">Fundamental Score</div>
        <div className="stock-score-value">{fundamental ? formatNumber(fundamental.score) : "-"}</div>
      </div>
      <div className="stock-summary">{fundamental?.summary ?? "No summary available."}</div>
      {fundamental?.updated_at ? (
        <div className="helper" style={{ marginTop: 12 }}>
          Updated at {new Date(fundamental.updated_at).toLocaleString("zh-CN")}
        </div>
      ) : null}
    </div>
  );
}
