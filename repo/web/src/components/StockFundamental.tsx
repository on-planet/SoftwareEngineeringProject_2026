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
        setError(err.message || "加载基本面失败");
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
    return <div>基本面加载中...</div>;
  }

  if (error) {
    return <div>基本面加载失败：{error}</div>;
  }

  if (!profile) {
    return <div>暂无股票信息</div>;
  }

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 16, background: "#fff" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{profile.name}</div>
          <div style={{ color: "#718096", fontSize: 12 }}>{profile.symbol} · {profile.market}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 12, color: "#718096" }}>行业</div>
          <div>{profile.sector}</div>
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <div style={{ fontSize: 12, color: "#718096" }}>综合评分</div>
        <div style={{ fontSize: 28, fontWeight: 700 }}>
          {fundamental ? formatNumber(fundamental.score) : "-"}
        </div>
      </div>
      <div style={{ marginTop: 12, color: "#4a5568", lineHeight: 1.6 }}>
        {fundamental?.summary ?? "暂无评分摘要"}
      </div>
      {fundamental?.updated_at ? (
        <div style={{ marginTop: 8, fontSize: 12, color: "#a0aec0" }}>
          更新时间：{new Date(fundamental.updated_at).toLocaleString("zh-CN")}
        </div>
      ) : null}
    </div>
  );
}
