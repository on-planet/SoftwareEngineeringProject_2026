import { useEffect, useMemo, useRef, useState } from "react";

import {
  ApiQueryOptions,
  ApiQuerySnapshot,
  getApiQuerySnapshot,
  invalidateApiQueries,
  runApiQuery,
  subscribeApiQuery,
} from "../services/api";

type QueryKey = string | readonly unknown[] | null;

type QueryState<T> = ApiQuerySnapshot<T> & {
  refetch: (overrideFetcher?: () => Promise<T>) => Promise<T | undefined>;
  invalidate: () => void;
};

function serializeQueryKey(key: QueryKey) {
  if (!key) {
    return null;
  }
  return typeof key === "string" ? key : JSON.stringify(key);
}

function idleQueryState<T>(): ApiQuerySnapshot<T> {
  return {
    data: undefined,
    error: null,
    isLoading: false,
    isFetching: false,
    updatedAt: null,
  };
}

export function useApiQuery<T>(
  key: QueryKey,
  fetcher: () => Promise<T>,
  options?: ApiQueryOptions,
): QueryState<T> {
  const cacheKey = useMemo(() => serializeQueryKey(key), [key]);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const [snapshot, setSnapshot] = useState<ApiQuerySnapshot<T>>(() => {
    if (!cacheKey) {
      return idleQueryState<T>();
    }
    return getApiQuerySnapshot<T>(cacheKey, options, { hydrateFromPersistence: false });
  });

  useEffect(() => {
    if (!cacheKey) {
      setSnapshot(idleQueryState<T>());
      return;
    }

    setSnapshot(getApiQuerySnapshot<T>(cacheKey, options));
    const unsubscribe = subscribeApiQuery(cacheKey, () => {
      setSnapshot(getApiQuerySnapshot<T>(cacheKey, options));
    });

    void runApiQuery(cacheKey, () => fetcherRef.current(), options).catch(() => undefined);
    return unsubscribe;
  }, [
    cacheKey,
    options?.backgroundRefresh,
    options?.cache,
    options?.cacheTimeMs,
    options?.force,
    options?.label,
    options?.persist?.key,
    options?.persist?.maxAgeMs,
    options?.retry,
    options?.retryDelayMs,
    options?.staleTimeMs,
  ]);

  const refetch = async (overrideFetcher?: () => Promise<T>) => {
    if (!cacheKey) {
      return undefined;
    }
    try {
      return await runApiQuery(cacheKey, overrideFetcher ?? (() => fetcherRef.current()), {
        ...options,
        force: true,
      });
    } catch {
      return undefined;
    }
  };

  const invalidate = () => {
    if (!cacheKey) {
      return;
    }
    invalidateApiQueries(cacheKey);
  };

  return {
    ...snapshot,
    refetch,
    invalidate,
  };
}
