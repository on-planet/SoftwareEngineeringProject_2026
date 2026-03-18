import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";

import { PerformanceComparisonPanel } from "../components/PerformanceComparisonPanel";
import { PortfolioAnalysisPanel } from "../components/PortfolioAnalysisPanel";
import { StatsDashboard } from "../components/StatsDashboard";
import {
  BoughtTargetItem,
  deleteMyBoughtTarget,
  deleteMyWatchTarget,
  getCurrentUser,
  getMyBoughtTargets,
  getMyWatchTargets,
  upsertMyBoughtTarget,
  upsertMyBoughtTargetsBatch,
  upsertMyWatchTarget,
  upsertMyWatchTargetsBatch,
} from "../services/api";
import { AUTH_CHANGED_EVENT, clearAuthToken, getAuthToken } from "../utils/auth";
import {
  BoughtTarget,
  getBoughtTarget,
  readBoughtTargets,
  removeBoughtTarget,
  replaceBoughtTargets,
  upsertBoughtTarget,
} from "../utils/boughtTargets";
import { addWatchTarget, readWatchTargets, removeWatchTarget, replaceWatchTargets } from "../utils/watchTargets";

type BuyFormState = {
  symbol: string;
  buyPrice: string;
  lots: string;
  buyDate: string;
  fee: string;
  note: string;
};

type StatsViewTab = "portfolio" | "performance" | "events" | "news";
type PortfolioViewTab = "watch" | "bought";
type StatsTargetTab = "watch" | "bought";

function todayText() {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = `${now.getMonth() + 1}`.padStart(2, "0");
  const dd = `${now.getDate()}`.padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

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

function parseTimestamp(value: string | null | undefined, fallback: number) {
  if (!value) {
    return fallback;
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return parsed;
}

function normalizeRemoteBoughtItem(raw: BoughtTargetItem): BoughtTarget | null {
  const symbol = normalizeSymbol(String(raw?.symbol || ""));
  const buyPrice = Number(raw?.buy_price);
  const lots = Number(raw?.lots);
  const fee = Number(raw?.fee || 0);
  const buyDate = String(raw?.buy_date || "");
  if (!symbol || !Number.isFinite(buyPrice) || buyPrice <= 0 || !Number.isFinite(lots) || lots <= 0) {
    return null;
  }
  if (!Number.isFinite(fee) || fee < 0 || !buyDate) {
    return null;
  }
  const updatedAt = parseTimestamp(raw?.updated_at || null, Date.now());
  const createdAt = parseTimestamp(raw?.created_at || null, updatedAt);
  return {
    symbol,
    buyPrice,
    lots,
    buyDate,
    fee,
    note: String(raw?.note || ""),
    createdAt,
    updatedAt,
  };
}

function mergeBoughtTargets(remoteItems: BoughtTarget[], localItems: BoughtTarget[]) {
  const merged = new Map<string, BoughtTarget>();
  remoteItems.forEach((item) => {
    merged.set(item.symbol, item);
  });
  localItems.forEach((item) => {
    const current = merged.get(item.symbol);
    if (!current || item.updatedAt > current.updatedAt) {
      merged.set(item.symbol, item);
    }
  });
  return Array.from(merged.values()).sort((a, b) => b.updatedAt - a.updatedAt);
}

export default function StatsPage() {
  const router = useRouter();
  const [symbol, setSymbol] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [watchTargets, setWatchTargets] = useState<string[]>([]);
  const [selectedWatchSymbols, setSelectedWatchSymbols] = useState<string[]>([]);
  const [watchInput, setWatchInput] = useState("");
  const [watchError, setWatchError] = useState<string | null>(null);
  const [boughtTargets, setBoughtTargets] = useState<BoughtTarget[]>([]);
  const [buyModalOpen, setBuyModalOpen] = useState(false);
  const [buyModalError, setBuyModalError] = useState<string | null>(null);
  const [pendingBuySymbols, setPendingBuySymbols] = useState<string[]>([]);
  const [buyForm, setBuyForm] = useState<BuyFormState>({
    symbol: "",
    buyPrice: "",
    lots: "",
    buyDate: todayText(),
    fee: "",
    note: "",
  });
  const [authChecked, setAuthChecked] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [statsViewTab, setStatsViewTab] = useState<StatsViewTab>("portfolio");
  const [portfolioViewTab, setPortfolioViewTab] = useState<PortfolioViewTab>("watch");
  const [statsTargetTab, setStatsTargetTab] = useState<StatsTargetTab>("watch");

  const querySymbol = useMemo(() => {
    const value = router.query.symbol;
    if (typeof value !== "string") {
      return "";
    }
    return normalizeSymbol(value);
  }, [router.query.symbol]);

  const boughtSymbols = useMemo(
    () => dedupeSymbols(boughtTargets.map((item) => normalizeSymbol(item.symbol))),
    [boughtTargets],
  );

  const groupedStatsSymbols = useMemo(
    () => (statsTargetTab === "watch" ? dedupeSymbols(watchTargets) : boughtSymbols),
    [statsTargetTab, watchTargets, boughtSymbols],
  );

  const filteredStatsSymbols = useMemo(() => {
    const exact = normalizeSymbol(symbol);
    if (!exact) {
      return groupedStatsSymbols;
    }
    return groupedStatsSymbols.filter((item) => item === exact);
  }, [groupedStatsSymbols, symbol]);

  useEffect(() => {
    let disposed = false;
    const syncAuth = async () => {
      const token = getAuthToken();
      if (!token) {
        if (!disposed) {
          setAuthed(false);
          setAuthToken(null);
          setAuthChecked(true);
        }
        return;
      }
      try {
        await getCurrentUser(token);
        if (!disposed) {
          setAuthed(true);
          setAuthToken(token);
        }
      } catch {
        clearAuthToken();
        if (!disposed) {
          setAuthed(false);
          setAuthToken(null);
        }
      } finally {
        if (!disposed) {
          setAuthChecked(true);
        }
      }
    };

    const handleAuthChanged = () => {
      void syncAuth();
    };

    void syncAuth();
    window.addEventListener(AUTH_CHANGED_EVENT, handleAuthChanged);
    return () => {
      disposed = true;
      window.removeEventListener(AUTH_CHANGED_EVENT, handleAuthChanged);
    };
  }, []);

  useEffect(() => {
    setWatchTargets(readWatchTargets());
    setBoughtTargets(readBoughtTargets());
  }, [router.asPath, authToken]);

  useEffect(() => {
    if (!authed || !authToken) {
      return;
    }
    let active = true;
    const syncFromRemote = async () => {
      try {
        const localWatch = readWatchTargets();
        const localBought = readBoughtTargets();
        const [remoteWatchRaw, remoteBoughtRaw] = await Promise.all([
          getMyWatchTargets(authToken),
          getMyBoughtTargets(authToken),
        ]);
        if (!active) {
          return;
        }

        const remoteWatch = dedupeSymbols((remoteWatchRaw || []).map((item: any) => String(item?.symbol || "")));
        const mergedWatch = dedupeSymbols([...remoteWatch, ...localWatch]);
        const nextWatch = replaceWatchTargets(mergedWatch);
        const hasWatchGap = mergedWatch.some((item) => !remoteWatch.includes(item));
        if (hasWatchGap && mergedWatch.length > 0) {
          void upsertMyWatchTargetsBatch(authToken, mergedWatch).catch(() => undefined);
        }

        const remoteBought = (remoteBoughtRaw || [])
          .map((item) => normalizeRemoteBoughtItem(item))
          .filter((item): item is BoughtTarget => !!item);
        const mergedBought = mergeBoughtTargets(remoteBought, localBought);
        const nextBought = replaceBoughtTargets(mergedBought);
        const remoteBoughtBySymbol = new Map(remoteBought.map((item) => [item.symbol, item]));
        const hasBoughtGap = mergedBought.some((item) => {
          const remote = remoteBoughtBySymbol.get(item.symbol);
          return !remote || item.updatedAt > remote.updatedAt;
        });
        if (hasBoughtGap && mergedBought.length > 0) {
          void upsertMyBoughtTargetsBatch(
            authToken,
            mergedBought.map((item) => ({
              symbol: item.symbol,
              buy_price: item.buyPrice,
              lots: item.lots,
              buy_date: item.buyDate,
              fee: item.fee,
              note: item.note,
            })),
          ).catch(() => undefined);
        }

        setWatchTargets(nextWatch);
        setBoughtTargets(nextBought);
      } catch {
        // Keep local data when remote sync fails.
      }
    };
    void syncFromRemote();
    return () => {
      active = false;
    };
  }, [authed, authToken]);

  useEffect(() => {
    setSelectedWatchSymbols((prev) => prev.filter((item) => watchTargets.includes(item)));
  }, [watchTargets]);

  useEffect(() => {
    if (!querySymbol) {
      return;
    }
    setSymbol(querySymbol);
  }, [querySymbol]);

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

  const handleToggleWatchSelection = (target: string) => {
    setSelectedWatchSymbols((prev) => {
      if (prev.includes(target)) {
        return prev.filter((item) => item !== target);
      }
      return [...prev, target];
    });
  };

  const handleToggleSelectAllWatch = () => {
    if (watchTargets.length === 0) {
      return;
    }
    if (selectedWatchSymbols.length === watchTargets.length) {
      setSelectedWatchSymbols([]);
      return;
    }
    setSelectedWatchSymbols([...watchTargets]);
  };

  const handleQuickAddWatchTarget = () => {
    const target = normalizeSymbol(watchInput);
    if (!target) {
      setWatchError("请输入标的代码");
      return;
    }
    const next = addWatchTarget(target);
    setWatchTargets(next);
    setWatchInput("");
    setWatchError(null);
    if (authToken) {
      void upsertMyWatchTarget(authToken, target).catch(() => {
        setWatchError("已添加到本地，云端同步失败");
      });
    }
  };

  const handleRemoveWatchTarget = (target: string) => {
    const next = removeWatchTarget(target);
    setWatchTargets(next);
    if (symbol === target) {
      setSymbol("");
    }
    if (authToken) {
      void deleteMyWatchTarget(authToken, target).catch(() => {
        setWatchError("本地已删除，云端同步失败");
      });
    }
  };

  const handleBatchRemoveSelectedWatch = () => {
    if (selectedWatchSymbols.length === 0) {
      return;
    }
    let next: string[] = watchTargets;
    for (const item of selectedWatchSymbols) {
      next = removeWatchTarget(item);
    }
    setWatchTargets(next);
    if (selectedWatchSymbols.includes(symbol)) {
      setSymbol("");
    }
    const removed = [...selectedWatchSymbols];
    setSelectedWatchSymbols([]);
    if (authToken && removed.length > 0) {
      void Promise.allSettled(removed.map((item) => deleteMyWatchTarget(authToken, item))).then(() => undefined);
    }
  };

  const openBuyModal = (targetSymbol: string, queue: string[] = []) => {
    const symbolValue = normalizeSymbol(targetSymbol);
    if (!symbolValue) {
      return;
    }
    const existing = getBoughtTarget(symbolValue);
    setBuyForm({
      symbol: symbolValue,
      buyPrice: existing ? String(existing.buyPrice) : "",
      lots: existing ? String(existing.lots) : "1",
      buyDate: existing?.buyDate || todayText(),
      fee: existing && existing.fee > 0 ? String(existing.fee) : "",
      note: existing?.note || "",
    });
    setPendingBuySymbols(queue);
    setBuyModalError(null);
    setBuyModalOpen(true);
  };

  const handleAddSelectedToBought = () => {
    const targets = dedupeSymbols(selectedWatchSymbols);
    if (targets.length === 0) {
      return;
    }
    openBuyModal(targets[0], targets.slice(1));
  };

  const handleAddSingleToBought = (target: string) => {
    const normalized = normalizeSymbol(target);
    if (!normalized) {
      return;
    }
    openBuyModal(normalized, []);
  };

  const handleSaveBoughtTarget = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const symbolValue = normalizeSymbol(buyForm.symbol);
    const buyPrice = Number(buyForm.buyPrice);
    const lots = Number(buyForm.lots);
    const fee = Number(buyForm.fee || 0);
    if (!symbolValue) {
      setBuyModalError("缺少股票代码");
      return;
    }
    if (!Number.isFinite(buyPrice) || buyPrice <= 0) {
      setBuyModalError("购买价格必须大于 0");
      return;
    }
    if (!Number.isFinite(lots) || lots <= 0) {
      setBuyModalError("购买手数必须大于 0");
      return;
    }
    if (!Number.isFinite(fee) || fee < 0) {
      setBuyModalError("手续费不能小于 0");
      return;
    }
    if (!buyForm.buyDate) {
      setBuyModalError("请选择购买日期");
      return;
    }
    const next = upsertBoughtTarget({
      symbol: symbolValue,
      buyPrice,
      lots,
      buyDate: buyForm.buyDate,
      fee,
      note: buyForm.note.trim(),
    });
    setBoughtTargets(next);
    setSymbol(symbolValue);
    if (authToken) {
      void upsertMyBoughtTarget(authToken, {
        symbol: symbolValue,
        buy_price: buyPrice,
        lots,
        buy_date: buyForm.buyDate,
        fee,
        note: buyForm.note.trim(),
      }).catch(() => {
        setBuyModalError("本地已保存，云端同步失败");
      });
    }

    if (pendingBuySymbols.length > 0) {
      const [nextSymbol, ...rest] = pendingBuySymbols;
      openBuyModal(nextSymbol, rest);
      return;
    }
    setBuyModalOpen(false);
    setBuyModalError(null);
  };

  const handleCancelBuyModal = () => {
    setBuyModalOpen(false);
    setPendingBuySymbols([]);
    setBuyModalError(null);
  };

  const handleBuyFormKeyDown = (event: React.KeyboardEvent<HTMLFormElement>) => {
    if (event.key !== "Enter") {
      return;
    }
    const target = event.target as HTMLElement | null;
    if (target instanceof HTMLTextAreaElement) {
      return;
    }
    event.preventDefault();
  };

  const handleRemoveBoughtTarget = (targetSymbol: string) => {
    const next = removeBoughtTarget(targetSymbol);
    setBoughtTargets(next);
    if (authToken) {
      void deleteMyBoughtTarget(authToken, targetSymbol).catch(() => undefined);
    }
  };

  if (!authChecked) {
    return (
      <div className="page">
        <section className="card">
          <div className="helper">正在校验登录状态...</div>
        </section>
      </div>
    );
  }

  if (!authed) {
    return (
      <div className="page">
        <section className="card">
          <h2 className="section-title">统计面板</h2>
          <div className="helper">请先登录后查看统计。</div>
        </section>
      </div>
    );
  }

  return (
    <div className="page">
      <section>
        <h2 className="section-title">统计面板</h2>

        <div className="stats-targets-grid">
          <div className="card">
            <div className="card-title">观察标的（支持多选、批量加入、批量删除）</div>
            <div className="toolbar" style={{ marginBottom: 10 }}>
              <input
                className="input"
                type="text"
                value={watchInput}
                onChange={(event) => setWatchInput(event.target.value)}
                placeholder="输入标的代码后可一键添加观察"
              />
              <button type="button" className="primary-button" onClick={handleQuickAddWatchTarget}>
                一键添加观察
              </button>
            </div>
            <div className="toolbar" style={{ marginBottom: 10 }}>
              <button type="button" className="stock-page-button" onClick={handleToggleSelectAllWatch}>
                {selectedWatchSymbols.length === watchTargets.length && watchTargets.length > 0 ? "取消全选" : "全选"}
              </button>
              <button
                type="button"
                className="stock-page-button"
                onClick={handleBatchRemoveSelectedWatch}
                disabled={selectedWatchSymbols.length === 0}
              >
                {`删除选中（${selectedWatchSymbols.length}）`}
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={handleAddSelectedToBought}
                disabled={selectedWatchSymbols.length === 0}
              >
                {`加入已买（选中${selectedWatchSymbols.length}）`}
              </button>
            </div>
            {watchError ? (
              <div className="helper" style={{ color: "#b91c1c", marginBottom: 8 }}>
                {watchError}
              </div>
            ) : null}
            {watchTargets.length === 0 ? (
              <div className="helper">暂无观察标的，请先在个股详情页加入观察或在此手动添加。</div>
            ) : (
              <div className="stats-watch-list">
                {watchTargets.map((item) => (
                  <div key={item} className="stats-watch-item">
                    <label className="stats-watch-check">
                      <input
                        type="checkbox"
                        checked={selectedWatchSymbols.includes(item)}
                        onChange={() => handleToggleWatchSelection(item)}
                      />
                      <span>{item}</span>
                    </label>
                    <div className="stats-bought-actions">
                      <button
                        type="button"
                        className="stock-page-button"
                        onClick={() => handleSelectWatchTarget(item)}
                        title="定位到该标的统计"
                      >
                        定位
                      </button>
                      <button
                        type="button"
                        className="stock-page-button"
                        onClick={() => handleAddSingleToBought(item)}
                        title="加入已买标的"
                      >
                        加入已买
                      </button>
                      <button
                        type="button"
                        className="stock-page-button"
                        onClick={() => handleRemoveWatchTarget(item)}
                        title="删除观察标的"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card stats-buy-dropzone">
            <div className="card-title">已买标的</div>
            {boughtTargets.length === 0 ? (
              <div className="helper">暂无已买标的，可在左侧观察标的中点击“加入已买”。</div>
            ) : (
              <div className="stats-bought-list">
                {boughtTargets.map((item) => (
                  <div key={item.symbol} className="stats-bought-item">
                    <div>
                      <div style={{ fontWeight: 700 }}>{item.symbol}</div>
                      <div className="helper">{`买入价 ${item.buyPrice} · ${item.lots} 手 · ${item.buyDate}`}</div>
                      <div className="helper">{`手续费 ${item.fee}${item.note ? ` · ${item.note}` : ""}`}</div>
                    </div>
                    <div className="stats-bought-actions">
                      <button
                        type="button"
                        className="stock-page-button"
                        onClick={() => openBuyModal(item.symbol)}
                        title="编辑买入信息"
                      >
                        ⚙
                      </button>
                      <button
                        type="button"
                        className="stock-page-button"
                        onClick={() => handleRemoveBoughtTarget(item.symbol)}
                        title="删除已买标的"
                      >
                        删除已买
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="toolbar" style={{ marginBottom: 12 }}>
          <button
            type="button"
            className="stock-page-button"
            data-active={statsViewTab === "portfolio"}
            onClick={() => setStatsViewTab("portfolio")}
          >
            行业暴露与组合分析
          </button>
          <button
            type="button"
            className="stock-page-button"
            data-active={statsViewTab === "performance"}
            onClick={() => setStatsViewTab("performance")}
          >
            收益图与大盘对比
          </button>
          <button
            type="button"
            className="stock-page-button"
            data-active={statsViewTab === "events"}
            onClick={() => setStatsViewTab("events")}
          >
            事件统计
          </button>
          <button
            type="button"
            className="stock-page-button"
            data-active={statsViewTab === "news"}
            onClick={() => setStatsViewTab("news")}
          >
            新闻统计
          </button>
        </div>

        {statsViewTab === "portfolio" ? (
          <div className="grid" style={{ gap: 12 }}>
            <div className="toolbar">
              <button
                type="button"
                className="stock-page-button"
                data-active={portfolioViewTab === "watch"}
                onClick={() => setPortfolioViewTab("watch")}
              >
                观察标的
              </button>
              <button
                type="button"
                className="stock-page-button"
                data-active={portfolioViewTab === "bought"}
                onClick={() => setPortfolioViewTab("bought")}
              >
                已购买标的
              </button>
            </div>
            <PortfolioAnalysisPanel
              symbols={portfolioViewTab === "watch" ? watchTargets : boughtTargets.map((item) => item.symbol)}
              title={portfolioViewTab === "watch" ? "观察标的行业暴露与组合分析" : "已购买标的行业暴露与组合分析"}
              emptyText={
                portfolioViewTab === "watch"
                  ? "暂无观察标的，请先在个股详情添加观察。"
                  : "暂无已购买标的，请先将观察标的加入已购买。"
              }
              pageSize={10}
            />
          </div>
        ) : (
          statsViewTab === "performance" ? (
            <PerformanceComparisonPanel watchSymbols={watchTargets} boughtTargets={boughtTargets} />
          ) : (
            <div className="grid" style={{ gap: 12 }}>
              <div className="toolbar">
                <button
                  type="button"
                  className="stock-page-button"
                  data-active={statsTargetTab === "watch"}
                  onClick={() => setStatsTargetTab("watch")}
                >
                  观察标的
                </button>
                <button
                  type="button"
                  className="stock-page-button"
                  data-active={statsTargetTab === "bought"}
                  onClick={() => setStatsTargetTab("bought")}
                >
                  已购买标的
                </button>
              </div>
              <div className="toolbar" style={{ marginBottom: 12 }}>
                <input
                  className="input"
                  type="text"
                  value={symbol}
                  onChange={(event) => setSymbol(event.target.value.trim().toUpperCase())}
                  placeholder="筛选标的（可选）"
                />
                <input className="input" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
                <input className="input" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
              </div>
              {filteredStatsSymbols.length === 0 ? (
                <div className="helper">
                  {statsTargetTab === "watch"
                    ? "暂无观察标的，请先在上方添加后再查看统计。"
                    : "暂无已购买标的，请先在上方加入后再查看统计。"}
                </div>
              ) : (
                <StatsDashboard
                  symbols={filteredStatsSymbols}
                  start={start || undefined}
                  end={end || undefined}
                  view={statsViewTab === "events" ? "events" : "news"}
                />
              )}
            </div>
          )
        )}
      </section>

      {buyModalOpen ? (
        <div className="stats-modal-mask">
          <div className="stats-modal-card">
            <h3 style={{ marginTop: 0, marginBottom: 10 }}>
              {`已买标的设置 · ${buyForm.symbol}`}
              {pendingBuySymbols.length > 0 ? `（待处理 ${pendingBuySymbols.length} 个）` : ""}
            </h3>
            <form onSubmit={handleSaveBoughtTarget} onKeyDown={handleBuyFormKeyDown} className="grid" style={{ gap: 10 }}>
              <input className="input" type="text" value={buyForm.symbol} readOnly />
              <input
                className="input"
                type="number"
                min="0"
                step="0.0001"
                value={buyForm.buyPrice}
                onChange={(event) => setBuyForm((prev) => ({ ...prev, buyPrice: event.target.value }))}
                placeholder="购买价格"
                required
              />
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                value={buyForm.lots}
                onChange={(event) => setBuyForm((prev) => ({ ...prev, lots: event.target.value }))}
                placeholder="购买手数"
                required
              />
              <input
                className="input"
                type="date"
                value={buyForm.buyDate}
                onChange={(event) => setBuyForm((prev) => ({ ...prev, buyDate: event.target.value }))}
                required
              />
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                value={buyForm.fee}
                onChange={(event) => setBuyForm((prev) => ({ ...prev, fee: event.target.value }))}
                placeholder="手续费"
              />
              <input
                className="input"
                type="text"
                value={buyForm.note}
                onChange={(event) => setBuyForm((prev) => ({ ...prev, note: event.target.value }))}
                placeholder="备注（可选）"
              />
              {buyModalError ? <div className="helper" style={{ color: "#b91c1c" }}>{buyModalError}</div> : null}
              <div className="stats-modal-actions">
                <button type="button" className="stock-page-button" onClick={handleCancelBuyModal}>
                  取消
                </button>
                <button type="submit" className="primary-button">
                  保存
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
