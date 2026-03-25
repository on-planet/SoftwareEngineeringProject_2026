import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";

import {
  PortfolioViewTab,
  StatsPageView,
  StatsTargetTab,
  StatsViewTab,
} from "../components/stats/StatsPageView";
import { useStatsTargets } from "../hooks/useStatsTargets";
import { useAuth } from "../providers/AuthProvider";

function normalizeSymbol(value: string) {
  return (value || "").trim().toUpperCase();
}

function dedupeSymbols(values: string[]) {
  const unique = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const symbol = normalizeSymbol(value);
    if (!symbol || unique.has(symbol)) {
      continue;
    }
    unique.add(symbol);
    result.push(symbol);
  }
  return result;
}

export default function StatsPage() {
  const router = useRouter();
  const [symbol, setSymbol] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [statsViewTab, setStatsViewTab] = useState<StatsViewTab>("portfolio");
  const [portfolioViewTab, setPortfolioViewTab] = useState<PortfolioViewTab>("watch");
  const [statsTargetTab, setStatsTargetTab] = useState<StatsTargetTab>("watch");
  const { isLoading: authLoading, isAuthenticated: authed, token: authToken } = useAuth();

  const querySymbol = useMemo(() => {
    const value = router.query.symbol;
    if (typeof value !== "string") {
      return "";
    }
    return normalizeSymbol(value);
  }, [router.query.symbol]);

  useEffect(() => {
    if (!querySymbol) {
      return;
    }
    setSymbol(querySymbol);
  }, [querySymbol]);

  const targets = useStatsTargets({
    authToken,
    authed,
    routeKey: router.asPath,
    setSymbol,
  });

  const boughtSymbols = useMemo(
    () => dedupeSymbols(targets.boughtTargets.map((item) => normalizeSymbol(item.symbol))),
    [targets.boughtTargets],
  );

  const groupedStatsSymbols = useMemo(
    () => (statsTargetTab === "watch" ? dedupeSymbols(targets.watchTargets) : boughtSymbols),
    [boughtSymbols, statsTargetTab, targets.watchTargets],
  );

  const filteredStatsSymbols = useMemo(() => {
    const exact = normalizeSymbol(symbol);
    if (!exact) {
      return groupedStatsSymbols;
    }
    return groupedStatsSymbols.filter((item) => item === exact);
  }, [groupedStatsSymbols, symbol]);

  const handleSelectWatchTarget = (target: string) => {
    setSymbol(target);
    void router.replace(
      {
        pathname: "/stats",
        query: { symbol: target },
      },
      undefined,
      { shallow: true },
    );
  };

  return (
    <StatsPageView
      authLoading={authLoading}
      authed={authed}
      symbol={symbol}
      start={start}
      end={end}
      statsViewTab={statsViewTab}
      portfolioViewTab={portfolioViewTab}
      statsTargetTab={statsTargetTab}
      filteredStatsSymbols={filteredStatsSymbols}
      targets={targets}
      onSymbolChange={setSymbol}
      onStartChange={setStart}
      onEndChange={setEnd}
      onStatsViewTabChange={setStatsViewTab}
      onPortfolioViewTabChange={setPortfolioViewTab}
      onStatsTargetTabChange={setStatsTargetTab}
      onSelectWatchTarget={handleSelectWatchTarget}
    />
  );
}
