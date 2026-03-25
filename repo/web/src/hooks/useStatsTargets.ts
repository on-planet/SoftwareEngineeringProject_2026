import { Dispatch, FormEvent, KeyboardEvent, SetStateAction, useEffect, useState } from "react";

import {
  BoughtTargetItem,
  deleteMyBoughtTarget,
  deleteMyWatchTarget,
  getMyBoughtTargets,
  getMyWatchTargets,
  upsertMyBoughtTarget,
  upsertMyBoughtTargetsBatch,
  upsertMyWatchTarget,
  upsertMyWatchTargetsBatch,
} from "../services/api";
import {
  BoughtTarget,
  getBoughtTarget,
  readBoughtTargets,
  removeBoughtTarget,
  replaceBoughtTargets,
  upsertBoughtTarget,
} from "../utils/boughtTargets";
import { addWatchTarget, readWatchTargets, removeWatchTarget, replaceWatchTargets } from "../utils/watchTargets";

export type BuyFormState = {
  symbol: string;
  buyPrice: string;
  lots: string;
  buyDate: string;
  fee: string;
  note: string;
};

type UseStatsTargetsOptions = {
  authToken: string | null;
  authed: boolean;
  routeKey: string;
  setSymbol: Dispatch<SetStateAction<string>>;
};

export type UseStatsTargetsResult = {
  watchTargets: string[];
  selectedWatchSymbols: string[];
  watchInput: string;
  watchError: string | null;
  boughtTargets: BoughtTarget[];
  buyModalOpen: boolean;
  buyModalError: string | null;
  pendingBuySymbols: string[];
  buyForm: BuyFormState;
  setWatchInput: (value: string) => void;
  setBuyForm: Dispatch<SetStateAction<BuyFormState>>;
  handleToggleWatchSelection: (target: string) => void;
  handleToggleSelectAllWatch: () => void;
  handleQuickAddWatchTarget: () => void;
  handleRemoveWatchTarget: (target: string) => void;
  handleBatchRemoveSelectedWatch: () => void;
  handleAddSelectedToBought: () => void;
  handleAddSingleToBought: (target: string) => void;
  handleSaveBoughtTarget: (event: FormEvent<HTMLFormElement>) => void;
  handleCancelBuyModal: () => void;
  handleBuyFormKeyDown: (event: KeyboardEvent<HTMLFormElement>) => void;
  handleRemoveBoughtTarget: (targetSymbol: string) => void;
  openBuyModal: (targetSymbol: string, queue?: string[]) => void;
};

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

function buildInitialBuyForm(): BuyFormState {
  return {
    symbol: "",
    buyPrice: "",
    lots: "",
    buyDate: todayText(),
    fee: "",
    note: "",
  };
}

function buildBuyForm(symbolValue: string, existing?: BoughtTarget | null): BuyFormState {
  return {
    symbol: symbolValue,
    buyPrice: existing ? String(existing.buyPrice) : "",
    lots: existing ? String(existing.lots) : "1",
    buyDate: existing?.buyDate || todayText(),
    fee: existing && existing.fee > 0 ? String(existing.fee) : "",
    note: existing?.note || "",
  };
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

export function useStatsTargets({
  authToken,
  authed,
  routeKey,
  setSymbol,
}: UseStatsTargetsOptions): UseStatsTargetsResult {
  const [watchTargets, setWatchTargets] = useState<string[]>([]);
  const [selectedWatchSymbols, setSelectedWatchSymbols] = useState<string[]>([]);
  const [watchInput, setWatchInputState] = useState("");
  const [watchError, setWatchError] = useState<string | null>(null);
  const [boughtTargets, setBoughtTargets] = useState<BoughtTarget[]>([]);
  const [buyModalOpen, setBuyModalOpen] = useState(false);
  const [buyModalError, setBuyModalError] = useState<string | null>(null);
  const [pendingBuySymbols, setPendingBuySymbols] = useState<string[]>([]);
  const [buyForm, setBuyForm] = useState<BuyFormState>(buildInitialBuyForm);

  useEffect(() => {
    setWatchTargets(readWatchTargets());
    setBoughtTargets(readBoughtTargets());
  }, [routeKey, authToken]);

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

  const openBuyModal = (targetSymbol: string, queue: string[] = []) => {
    const symbolValue = normalizeSymbol(targetSymbol);
    if (!symbolValue) {
      return;
    }
    const existing = getBoughtTarget(symbolValue);
    setBuyForm(buildBuyForm(symbolValue, existing));
    setPendingBuySymbols(queue);
    setBuyModalError(null);
    setBuyModalOpen(true);
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
    setWatchInputState("");
    setWatchError(null);
    if (authToken) {
      void upsertMyWatchTarget(authToken, target).catch(() => {
        setWatchError("已写入本地，云端同步失败");
      });
    }
  };

  const handleRemoveWatchTarget = (target: string) => {
    const next = removeWatchTarget(target);
    setWatchTargets(next);
    setSelectedWatchSymbols((prev) => prev.filter((item) => item !== target));
    setSymbol((current) => (current === target ? "" : current));
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
    const removed = [...selectedWatchSymbols];
    setSelectedWatchSymbols([]);
    if (removed.length > 0) {
      setSymbol((current) => (removed.includes(current) ? "" : current));
    }
    if (authToken && removed.length > 0) {
      void Promise.allSettled(removed.map((item) => deleteMyWatchTarget(authToken, item))).then(() => undefined);
    }
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
      setBuyModalError("买入价格必须大于 0");
      return;
    }
    if (!Number.isFinite(lots) || lots <= 0) {
      setBuyModalError("买入手数必须大于 0");
      return;
    }
    if (!Number.isFinite(fee) || fee < 0) {
      setBuyModalError("手续费不能小于 0");
      return;
    }
    if (!buyForm.buyDate) {
      setBuyModalError("请选择买入日期");
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
    setPendingBuySymbols([]);
    setBuyModalError(null);
  };

  const handleCancelBuyModal = () => {
    setBuyModalOpen(false);
    setPendingBuySymbols([]);
    setBuyModalError(null);
    setBuyForm(buildInitialBuyForm());
  };

  const handleBuyFormKeyDown = (event: KeyboardEvent<HTMLFormElement>) => {
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

  return {
    watchTargets,
    selectedWatchSymbols,
    watchInput,
    watchError,
    boughtTargets,
    buyModalOpen,
    buyModalError,
    pendingBuySymbols,
    buyForm,
    setWatchInput: setWatchInputState,
    setBuyForm,
    handleToggleWatchSelection,
    handleToggleSelectAllWatch,
    handleQuickAddWatchTarget,
    handleRemoveWatchTarget,
    handleBatchRemoveSelectedWatch,
    handleAddSelectedToBought,
    handleAddSingleToBought,
    handleSaveBoughtTarget,
    handleCancelBuyModal,
    handleBuyFormKeyDown,
    handleRemoveBoughtTarget,
    openBuyModal,
  };
}
