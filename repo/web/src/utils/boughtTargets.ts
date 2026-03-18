import { getAuthUserId } from "./auth";

export type BoughtTarget = {
  symbol: string;
  buyPrice: number;
  lots: number;
  buyDate: string;
  fee: number;
  note: string;
  createdAt: number;
  updatedAt: number;
};

const BOUGHT_TARGETS_KEY = "kiloquant_bought_targets";
const BOUGHT_TARGETS_KEY_BY_USER_PREFIX = "kiloquant_bought_targets_by_user";
const MAX_BOUGHT_TARGETS = 200;

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function normalizeSymbol(symbol: string) {
  return (symbol || "").trim().toUpperCase();
}

function normalizeUserId(value?: number | null): number | null {
  const parsed = Number(value ?? 0);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return Math.floor(parsed);
}

function getScopedKeyByUserId(userId: number) {
  return `${BOUGHT_TARGETS_KEY_BY_USER_PREFIX}:${userId}`;
}

function resolveScopedKey(explicitUserId?: number | null) {
  const userId = normalizeUserId(explicitUserId) ?? normalizeUserId(getAuthUserId());
  if (!userId) {
    return { key: BOUGHT_TARGETS_KEY, userId: null as number | null };
  }
  return { key: getScopedKeyByUserId(userId), userId };
}

function isPositiveNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function isNonNegativeNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function normalizeRecord(raw: any): BoughtTarget | null {
  const symbol = normalizeSymbol(String(raw?.symbol || ""));
  if (!symbol) {
    return null;
  }
  const buyPrice = Number(raw?.buyPrice);
  const lots = Number(raw?.lots);
  const fee = Number(raw?.fee || 0);
  const buyDate = String(raw?.buyDate || "");
  const note = String(raw?.note || "");
  const createdAt = Number(raw?.createdAt || Date.now());
  const updatedAt = Number(raw?.updatedAt || createdAt || Date.now());
  if (!isPositiveNumber(buyPrice) || !isPositiveNumber(lots) || !isNonNegativeNumber(fee)) {
    return null;
  }
  if (!buyDate) {
    return null;
  }
  return {
    symbol,
    buyPrice,
    lots,
    buyDate,
    fee,
    note,
    createdAt,
    updatedAt,
  };
}

function writeBoughtTargets(list: BoughtTarget[], explicitUserId?: number | null) {
  if (!canUseStorage()) {
    return;
  }
  try {
    const { key, userId } = resolveScopedKey(explicitUserId);
    if (userId) {
      migrateLegacyBoughtTargetsIfNeeded(userId);
    }
    window.localStorage.setItem(key, JSON.stringify(list.slice(0, MAX_BOUGHT_TARGETS)));
  } catch {
    // Ignore localStorage failures.
  }
}

export function replaceBoughtTargets(items: BoughtTarget[]): BoughtTarget[] {
  const unique = new Set<string>();
  const normalizedItems: BoughtTarget[] = [];
  for (const item of items || []) {
    const normalized = normalizeRecord(item);
    if (!normalized || unique.has(normalized.symbol)) {
      continue;
    }
    unique.add(normalized.symbol);
    normalizedItems.push(normalized);
    if (normalizedItems.length >= MAX_BOUGHT_TARGETS) {
      break;
    }
  }
  normalizedItems.sort((a, b) => b.updatedAt - a.updatedAt);
  writeBoughtTargets(normalizedItems);
  return normalizedItems;
}

function parseBoughtTargetList(raw: string | null): BoughtTarget[] {
  if (!raw) {
    return [];
  }
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) {
    return [];
  }
  const unique = new Set<string>();
  const result: BoughtTarget[] = [];
  for (const item of parsed) {
    const normalized = normalizeRecord(item);
    if (!normalized || unique.has(normalized.symbol)) {
      continue;
    }
    unique.add(normalized.symbol);
    result.push(normalized);
    if (result.length >= MAX_BOUGHT_TARGETS) {
      break;
    }
  }
  result.sort((a, b) => b.updatedAt - a.updatedAt);
  return result;
}

function readBoughtTargetsByKey(key: string): BoughtTarget[] {
  if (!canUseStorage()) {
    return [];
  }
  try {
    return parseBoughtTargetList(window.localStorage.getItem(key));
  } catch {
    return [];
  }
}

function migrateLegacyBoughtTargetsIfNeeded(userId: number) {
  if (!canUseStorage()) {
    return;
  }
  try {
    const scopedKey = getScopedKeyByUserId(userId);
    if (window.localStorage.getItem(scopedKey)) {
      return;
    }
    const legacy = readBoughtTargetsByKey(BOUGHT_TARGETS_KEY);
    if (legacy.length === 0) {
      return;
    }
    window.localStorage.setItem(scopedKey, JSON.stringify(legacy));
  } catch {
    // Ignore localStorage failures.
  }
}

export function readBoughtTargets(): BoughtTarget[] {
  const { key, userId } = resolveScopedKey();
  if (userId) {
    migrateLegacyBoughtTargetsIfNeeded(userId);
  }
  return readBoughtTargetsByKey(key);
}

export function getBoughtTarget(symbol: string): BoughtTarget | null {
  const normalized = normalizeSymbol(symbol);
  if (!normalized) {
    return null;
  }
  return readBoughtTargets().find((item) => item.symbol === normalized) || null;
}

export function upsertBoughtTarget(payload: {
  symbol: string;
  buyPrice: number;
  lots: number;
  buyDate: string;
  fee?: number;
  note?: string;
}): BoughtTarget[] {
  const symbol = normalizeSymbol(payload.symbol);
  if (!symbol) {
    return readBoughtTargets();
  }
  const buyPrice = Number(payload.buyPrice);
  const lots = Number(payload.lots);
  const fee = Number(payload.fee || 0);
  const buyDate = String(payload.buyDate || "");
  if (!isPositiveNumber(buyPrice) || !isPositiveNumber(lots) || !isNonNegativeNumber(fee) || !buyDate) {
    return readBoughtTargets();
  }
  const now = Date.now();
  const current = readBoughtTargets();
  const existing = current.find((item) => item.symbol === symbol);
  const nextItem: BoughtTarget = {
    symbol,
    buyPrice,
    lots,
    buyDate,
    fee,
    note: String(payload.note || ""),
    createdAt: existing?.createdAt || now,
    updatedAt: now,
  };
  const next = [nextItem, ...current.filter((item) => item.symbol !== symbol)].slice(0, MAX_BOUGHT_TARGETS);
  writeBoughtTargets(next);
  return next;
}

export function removeBoughtTarget(symbol: string): BoughtTarget[] {
  const normalized = normalizeSymbol(symbol);
  if (!normalized) {
    return readBoughtTargets();
  }
  const next = readBoughtTargets().filter((item) => item.symbol !== normalized);
  writeBoughtTargets(next);
  return next;
}
