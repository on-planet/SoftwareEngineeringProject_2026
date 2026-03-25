import { useEffect, useMemo, useState } from "react";

import {
  ApiPage,
  BondMarketQuoteItem,
  BondMarketTradeItem,
  FxPairQuoteItem,
  FxSpotQuoteItem,
  FxSwapQuoteItem,
  getBondMarketQuotes,
  getBondMarketTrades,
  getFxPairQuotes,
  getFxSpotQuotes,
  getFxSwapQuotes,
  getMacroSeries,
  getMacroSnapshot,
} from "../services/api";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";
import {
  buildMacroSeriesCacheKey,
  buildMacroSeriesChartOption,
  buildMacroSnapshotCacheKey,
  buildSnapshotCard,
  MACRO_SERIES_CACHE_TTL_MS,
  MACRO_SNAPSHOT_CACHE_TTL_MS,
  MacroItem,
  MacroSeries,
  paginate,
  SNAPSHOT_CARD_LIMIT,
  SNAPSHOT_PAGE_LIMIT,
  SnapshotCard,
  SortOrder,
} from "../components/macro/macroUtils";

async function loadLatestMacroSnapshotItems(): Promise<MacroItem[]> {
  const merged: MacroItem[] = [];
  const pageSize = SNAPSHOT_PAGE_LIMIT;
  let offset = 0;
  let total = Number.POSITIVE_INFINITY;

  while (offset < total) {
    const response = await getMacroSnapshot({
      limit: pageSize,
      offset,
      sort: "desc",
    });
    const items = response.items ?? [];
    merged.push(...items);
    total = Number(response.total ?? merged.length);
    if (items.length < pageSize) {
      break;
    }
    offset += pageSize;
  }

  return merged.sort((left, right) => left.key.localeCompare(right.key));
}

type MacroReferencePanel<T> = {
  items: T[];
  total: number;
  loading: boolean;
  error: string | null;
};

type MacroReferencePanels = {
  bondQuotes: MacroReferencePanel<BondMarketQuoteItem>;
  bondTrades: MacroReferencePanel<BondMarketTradeItem>;
  fxSpot: MacroReferencePanel<FxSpotQuoteItem>;
  fxSwap: MacroReferencePanel<FxSwapQuoteItem>;
  fxPair: MacroReferencePanel<FxPairQuoteItem>;
};

function createReferencePanel<T>(): MacroReferencePanel<T> {
  return {
    items: [],
    total: 0,
    loading: true,
    error: null,
  };
}

function createReferencePanels(): MacroReferencePanels {
  return {
    bondQuotes: createReferencePanel<BondMarketQuoteItem>(),
    bondTrades: createReferencePanel<BondMarketTradeItem>(),
    fxSpot: createReferencePanel<FxSpotQuoteItem>(),
    fxSwap: createReferencePanel<FxSwapQuoteItem>(),
    fxPair: createReferencePanel<FxPairQuoteItem>(),
  };
}

function resolveReferencePanel<T>(result: PromiseSettledResult<ApiPage<T>>): MacroReferencePanel<T> {
  if (result.status === "fulfilled") {
    return {
      items: result.value.items ?? [],
      total: Number(result.value.total ?? result.value.items?.length ?? 0),
      loading: false,
      error: null,
    };
  }
  return {
    items: [],
    total: 0,
    loading: false,
    error: result.reason instanceof Error ? result.reason.message : String(result.reason),
  };
}

export type MacroDashboardModel = ReturnType<typeof useMacroDashboard>;

export function useMacroDashboard() {
  const [snapshotItems, setSnapshotItems] = useState<MacroItem[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [series, setSeries] = useState<MacroSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [search, setSearch] = useState("");
  const [country, setCountry] = useState("");
  const [family, setFamily] = useState("");
  const [snapshotPage, setSnapshotPage] = useState(1);
  const [sort, setSort] = useState<SortOrder>("desc");
  const [referencePanels, setReferencePanels] = useState<MacroReferencePanels>(createReferencePanels);

  useEffect(() => {
    let active = true;
    const cachedItems = readPersistentCache<MacroItem[]>(buildMacroSnapshotCacheKey(), MACRO_SNAPSHOT_CACHE_TTL_MS);
    if (cachedItems?.length) {
      setSnapshotItems(cachedItems);
      setLoading(false);
    } else {
      setLoading(true);
    }

    loadLatestMacroSnapshotItems()
      .then((items) => {
        if (!active) return;
        setSnapshotItems(items);
        writePersistentCache(buildMacroSnapshotCacheKey(), items);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setSnapshotItems([]);
        setError(err.message || "宏观快照加载失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setReferencePanels(createReferencePanels());

    Promise.allSettled([
      getBondMarketQuotes({ limit: 6, sort: "asc" }),
      getBondMarketTrades({ limit: 6, sort: "asc" }),
      getFxSpotQuotes({ limit: 8, sort: "asc" }),
      getFxSwapQuotes({ limit: 8, sort: "asc" }),
      getFxPairQuotes({ limit: 8, sort: "asc" }),
    ]).then((results) => {
      if (!active) {
        return;
      }
      setReferencePanels({
        bondQuotes: resolveReferencePanel(results[0] as PromiseSettledResult<ApiPage<BondMarketQuoteItem>>),
        bondTrades: resolveReferencePanel(results[1] as PromiseSettledResult<ApiPage<BondMarketTradeItem>>),
        fxSpot: resolveReferencePanel(results[2] as PromiseSettledResult<ApiPage<FxSpotQuoteItem>>),
        fxSwap: resolveReferencePanel(results[3] as PromiseSettledResult<ApiPage<FxSwapQuoteItem>>),
        fxPair: resolveReferencePanel(results[4] as PromiseSettledResult<ApiPage<FxPairQuoteItem>>),
      });
    });

    return () => {
      active = false;
    };
  }, []);

  const cards = useMemo(() => snapshotItems.map(buildSnapshotCard), [snapshotItems]);

  const visibleCards = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return cards
      .filter((item) => (country ? item.country === country : true))
      .filter((item) => (family ? item.family === family : true))
      .filter((item) => {
        if (!keyword) return true;
        return [item.key, item.label, item.countryLabel, item.family].join(" ").toLowerCase().includes(keyword);
      })
      .sort((left, right) => {
        const dateCompare = left.date.localeCompare(right.date);
        if (dateCompare !== 0) {
          return sort === "asc" ? dateCompare : -dateCompare;
        }
        return left.label.localeCompare(right.label);
      });
  }, [cards, country, family, search, sort]);

  useEffect(() => {
    if (!visibleCards.length) {
      if (selectedKey) setSelectedKey("");
      return;
    }
    if (!visibleCards.some((item) => item.key === selectedKey)) {
      setSelectedKey(visibleCards[0].key);
    }
  }, [selectedKey, visibleCards]);

  useEffect(() => {
    setSnapshotPage(1);
  }, [country, family, search, sort]);

  useEffect(() => {
    if (!selectedKey) {
      setSeries(null);
      setSeriesLoading(false);
      return;
    }

    let active = true;
    const cacheKey = buildMacroSeriesCacheKey(selectedKey, start, end);
    const cachedSeries = readPersistentCache<MacroSeries>(cacheKey, MACRO_SERIES_CACHE_TTL_MS);
    if (cachedSeries?.items?.length) {
      setSeries(cachedSeries);
      setSeriesLoading(false);
    } else {
      setSeriesLoading(true);
    }

    getMacroSeries(selectedKey, {
      start: start || undefined,
      end: end || undefined,
    })
      .then((payload) => {
        if (!active) return;
        setSeries(payload as MacroSeries);
        writePersistentCache(cacheKey, payload as MacroSeries);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setSeries(null);
        setError(err.message || "宏观序列加载失败");
      })
      .finally(() => {
        if (active) setSeriesLoading(false);
      });

    return () => {
      active = false;
    };
  }, [end, selectedKey, start]);

  const countryOptions = useMemo(
    () => Array.from(new Set(cards.map((item) => item.country))).sort((left, right) => left.localeCompare(right)),
    [cards],
  );

  const familyOptions = useMemo(
    () => Array.from(new Set(cards.map((item) => item.family))).sort((left, right) => left.localeCompare(right)),
    [cards],
  );

  const pagedSnapshots = useMemo(
    () => paginate(visibleCards, snapshotPage, SNAPSHOT_CARD_LIMIT),
    [snapshotPage, visibleCards],
  );

  useEffect(() => {
    if (pagedSnapshots.page !== snapshotPage) {
      setSnapshotPage(pagedSnapshots.page);
    }
  }, [pagedSnapshots.page, snapshotPage]);

  const selectedCard = useMemo<SnapshotCard | null>(
    () => visibleCards.find((item) => item.key === selectedKey) ?? null,
    [selectedKey, visibleCards],
  );

  const chartOption = useMemo(() => {
    if (!series || !series.items.length || !selectedCard) return null;
    return buildMacroSeriesChartOption(selectedCard, series);
  }, [selectedCard, series]);

  const latestPoint = series?.items?.[series.items.length - 1] ?? null;

  return {
    loading,
    error,
    search,
    setSearch,
    country,
    setCountry,
    family,
    setFamily,
    sort,
    setSort,
    start,
    setStart,
    end,
    setEnd,
    cards,
    visibleCards,
    countryOptions,
    familyOptions,
    snapshotPage,
    setSnapshotPage,
    pagedSnapshots,
    selectedKey,
    setSelectedKey,
    selectedCard,
    series,
    seriesLoading,
    chartOption,
    latestPoint,
    referencePanels,
  };
}
