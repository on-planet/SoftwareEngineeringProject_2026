type CacheEnvelope<T> = {
  savedAt: number;
  value: T;
};

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function buildKey(key: string) {
  return `market-dashboard:${key}`;
}

export function readPersistentCache<T>(key: string, maxAgeMs: number): T | null {
  if (!canUseStorage()) {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(buildKey(key));
    if (!raw) {
      return null;
    }
    const envelope = JSON.parse(raw) as CacheEnvelope<T>;
    if (!envelope || typeof envelope.savedAt !== "number") {
      window.localStorage.removeItem(buildKey(key));
      return null;
    }
    if (Date.now() - envelope.savedAt > maxAgeMs) {
      return null;
    }
    return envelope.value ?? null;
  } catch {
    return null;
  }
}

export function writePersistentCache<T>(key: string, value: T) {
  if (!canUseStorage()) {
    return;
  }
  try {
    const envelope: CacheEnvelope<T> = { savedAt: Date.now(), value };
    window.localStorage.setItem(buildKey(key), JSON.stringify(envelope));
  } catch {
    // Ignore quota and serialization failures; network response remains the source of truth.
  }
}
