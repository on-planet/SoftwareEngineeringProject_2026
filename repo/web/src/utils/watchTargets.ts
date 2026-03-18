import { getAuthUserId } from "./auth";

const WATCH_TARGETS_KEY = "kiloquant_watch_targets";
const WATCH_TARGETS_KEY_BY_USER_PREFIX = "kiloquant_watch_targets_by_user";
const MAX_WATCH_TARGETS = 50;

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
  return `${WATCH_TARGETS_KEY_BY_USER_PREFIX}:${userId}`;
}

function resolveScopedKey(explicitUserId?: number | null) {
  const userId = normalizeUserId(explicitUserId) ?? normalizeUserId(getAuthUserId());
  if (!userId) {
    return { key: WATCH_TARGETS_KEY, userId: null as number | null };
  }
  return { key: getScopedKeyByUserId(userId), userId };
}

function parseWatchTargetList(raw: string | null): string[] {
  if (!raw) {
    return [];
  }
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) {
    return [];
  }
  const unique = new Set<string>();
  const result: string[] = [];
  for (const item of parsed) {
    const symbol = normalizeSymbol(String(item || ""));
    if (!symbol || unique.has(symbol)) {
      continue;
    }
    unique.add(symbol);
    result.push(symbol);
    if (result.length >= MAX_WATCH_TARGETS) {
      break;
    }
  }
  return result;
}

function readWatchTargetsByKey(key: string): string[] {
  if (!canUseStorage()) {
    return [];
  }
  try {
    return parseWatchTargetList(window.localStorage.getItem(key));
  } catch {
    return [];
  }
}

function migrateLegacyWatchTargetsIfNeeded(userId: number) {
  if (!canUseStorage()) {
    return;
  }
  try {
    const scopedKey = getScopedKeyByUserId(userId);
    if (window.localStorage.getItem(scopedKey)) {
      return;
    }
    const legacy = readWatchTargetsByKey(WATCH_TARGETS_KEY);
    if (legacy.length === 0) {
      return;
    }
    window.localStorage.setItem(scopedKey, JSON.stringify(legacy));
  } catch {
    // Ignore localStorage failures.
  }
}

export function readWatchTargets(): string[] {
  const { key, userId } = resolveScopedKey();
  if (userId) {
    migrateLegacyWatchTargetsIfNeeded(userId);
  }
  return readWatchTargetsByKey(key);
}

function writeWatchTargets(list: string[], explicitUserId?: number | null) {
  if (!canUseStorage()) {
    return;
  }
  try {
    const { key, userId } = resolveScopedKey(explicitUserId);
    if (userId) {
      migrateLegacyWatchTargetsIfNeeded(userId);
    }
    window.localStorage.setItem(key, JSON.stringify(list));
  } catch {
    // Ignore localStorage write failures.
  }
}

export function replaceWatchTargets(items: string[]): string[] {
  const unique = new Set<string>();
  const next: string[] = [];
  for (const item of items || []) {
    const symbol = normalizeSymbol(String(item || ""));
    if (!symbol || unique.has(symbol)) {
      continue;
    }
    unique.add(symbol);
    next.push(symbol);
    if (next.length >= MAX_WATCH_TARGETS) {
      break;
    }
  }
  writeWatchTargets(next);
  return next;
}

export function addWatchTarget(symbol: string): string[] {
  const normalized = normalizeSymbol(symbol);
  if (!normalized) {
    return readWatchTargets();
  }
  const current = readWatchTargets().filter((item) => item !== normalized);
  const next = [normalized, ...current].slice(0, MAX_WATCH_TARGETS);
  writeWatchTargets(next);
  return next;
}

export function hasWatchTarget(symbol: string): boolean {
  const normalized = normalizeSymbol(symbol);
  if (!normalized) {
    return false;
  }
  return readWatchTargets().includes(normalized);
}

export function removeWatchTarget(symbol: string): string[] {
  const normalized = normalizeSymbol(symbol);
  if (!normalized) {
    return readWatchTargets();
  }
  const next = readWatchTargets().filter((item) => item !== normalized);
  writeWatchTargets(next);
  return next;
}
