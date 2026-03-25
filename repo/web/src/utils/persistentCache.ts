export type PersistentCacheEntry<T> = {
  savedAt: number;
  value: T;
};

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function buildKey(key: string) {
  return `market-dashboard:${key}`;
}

export function getPersistentCacheEntry<T>(key: string, maxAgeMs: number): PersistentCacheEntry<T> | null {
  if (!canUseStorage()) {
    return null;
  }
  try {
    const storageKey = buildKey(key);
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) {
      return null;
    }
    const envelope = JSON.parse(raw) as PersistentCacheEntry<T>;
    if (!envelope || typeof envelope.savedAt !== "number") {
      window.localStorage.removeItem(storageKey);
      return null;
    }
    if (Date.now() - envelope.savedAt > maxAgeMs) {
      return null;
    }
    return envelope;
  } catch {
    return null;
  }
}

export function readPersistentCache<T>(key: string, maxAgeMs: number): T | null {
  const entry = getPersistentCacheEntry<T>(key, maxAgeMs);
  return entry?.value ?? null;
}

export function writePersistentCache<T>(key: string, value: T) {
  if (!canUseStorage()) {
    return;
  }
  try {
    const envelope: PersistentCacheEntry<T> = { savedAt: Date.now(), value };
    window.localStorage.setItem(buildKey(key), JSON.stringify(envelope));
  } catch {
    // Ignore quota and serialization failures; network response remains the source of truth.
  }
}

export function removePersistentCache(key: string) {
  if (!canUseStorage()) {
    return;
  }
  try {
    window.localStorage.removeItem(buildKey(key));
  } catch {
    // Ignore storage failures while clearing stale cache entries.
  }
}
