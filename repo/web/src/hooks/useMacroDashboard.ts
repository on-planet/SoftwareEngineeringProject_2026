import { useEffect, useMemo, useState } from "react";

import {
  ApiPage,
  BondMarketQuoteItem,
  BondMarketTradeItem,
  FxPairQuoteItem,
  FxSpotQuoteItem,
  FxSwapQuoteItem,
  buildMacroSeriesQueryKey,
  buildMacroSnapshotQueryKey,
  getBondMarketQuotes,
  getBondMarketTrades,
  getFxPairQuotes,
  getFxSpotQuotes,
  getFxSwapQuotes,
  getMacroSeries,
  getMacroSnapshot,
  getMacroSeriesQueryOptions,
  getMacroSnapshotQueryOptions,
} from "../services/api";
import { useApiQuery } from "./useApiQuery";
import {
  buildMacroSeriesChartOption,
  buildSnapshotCard,
  MacroItem,
  MacroSeries,
  paginate,
  SNAPSHOT_CARD_LIMIT,
  SNAPSHOT_PAGE_LIMIT,
  SnapshotCard,
  SortOrder,
} from "../components/macro/macroUtils";

const REFERENCE_PANEL_LIMIT = 60;

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
  const [selectedKey, setSelectedKey] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [search, setSearch] = useState("");
  const [country, setCountry] = useState("");
  const [family, setFamily] = useState("");
  const [snapshotPage, setSnapshotPage] = useState(1);
  const [sort, setSort] = useState<SortOrder>("desc");
  const [referencePanels, setReferencePanels] = useState<MacroReferencePanels>(createReferencePanels);

  const snapshotCacheKey = useMemo(() => buildMacroSnapshotQueryKey(), []);
  const snapshotQuery = useApiQuery<MacroItem[]>(
    snapshotCacheKey,
    loadLatestMacroSnapshotItems,
    getMacroSnapshotQueryOptions(snapshotCacheKey),
  );
  const snapshotItems = snapshotQuery.data ?? [];

  useEffect(() => {
    let active = true;
    setReferencePanels(createReferencePanels());

    Promise.allSettled([
      getBondMarketQuotes({ limit: REFERENCE_PANEL_LIMIT, sort: "asc" }),
      getBondMarketTrades({ limit: REFERENCE_PANEL_LIMIT, sort: "asc" }),
      getFxSpotQuotes({ limit: REFERENCE_PANEL_LIMIT, sort: "asc" }),
      getFxSwapQuotes({ limit: REFERENCE_PANEL_LIMIT, sort: "asc" }),
      getFxPairQuotes({ limit: REFERENCE_PANEL_LIMIT, sort: "asc" }),
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
      if (selectedKey) {
        setSelectedKey("");
      }
      return;
    }
    if (!visibleCards.some((item) => item.key === selectedKey)) {
      setSelectedKey(visibleCards[0].key);
    }
  }, [selectedKey, visibleCards]);

  useEffect(() => {
    setSnapshotPage(1);
  }, [country, family, search, sort]);

  const seriesCacheKey = useMemo(
    () => (selectedKey ? buildMacroSeriesQueryKey(selectedKey, start, end) : null),
    [end, selectedKey, start],
  );
  const seriesQuery = useApiQuery<MacroSeries>(
    seriesCacheKey,
    () =>
      getMacroSeries(selectedKey, {
        start: start || undefined,
        end: end || undefined,
      }) as Promise<MacroSeries>,
    seriesCacheKey ? getMacroSeriesQueryOptions(seriesCacheKey) : undefined,
  );
  const series = seriesQuery.data ?? null;

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
    if (!series || !series.items.length || !selectedCard) {
      return null;
    }
    return buildMacroSeriesChartOption(selectedCard, series);
  }, [selectedCard, series]);

  const latestPoint = series?.items?.[series.items.length - 1] ?? null;
  const loading = snapshotQuery.isLoading && snapshotItems.length === 0;
  const seriesLoading = Boolean(selectedKey) && seriesQuery.isLoading && !series;
  const error = snapshotQuery.error?.message ?? seriesQuery.error?.message ?? null;

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
