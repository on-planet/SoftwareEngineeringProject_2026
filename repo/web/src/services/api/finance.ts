import { ApiPage, request } from "./core";

export type BondMarketQuoteItem = {
  quote_org?: string | null;
  bond_name: string;
  buy_net_price?: number | null;
  sell_net_price?: number | null;
  buy_yield?: number | null;
  sell_yield?: number | null;
  as_of?: string | null;
  source?: string | null;
};

export type BondMarketTradeItem = {
  bond_name: string;
  deal_net_price?: number | null;
  latest_yield?: number | null;
  change?: number | null;
  weighted_yield?: number | null;
  volume?: number | null;
  as_of?: string | null;
  source?: string | null;
};

export type FxSpotQuoteItem = {
  currency_pair: string;
  bid?: number | null;
  ask?: number | null;
  as_of?: string | null;
  source?: string | null;
};

export type FxSwapQuoteItem = {
  currency_pair: string;
  one_week?: number | null;
  one_month?: number | null;
  three_month?: number | null;
  six_month?: number | null;
  nine_month?: number | null;
  one_year?: number | null;
  as_of?: string | null;
  source?: string | null;
};

export type FxPairQuoteItem = {
  currency_pair: string;
  bid?: number | null;
  ask?: number | null;
  as_of?: string | null;
  source?: string | null;
};

export async function getBondMarketQuotes(params?: {
  keyword?: string;
  refresh?: boolean;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.keyword) query.set("keyword", params.keyword);
  if (params?.refresh) query.set("refresh", "true");
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<BondMarketQuoteItem>>(`/api/bond/market/quote${suffix ? `?${suffix}` : ""}`);
}

export async function getBondMarketTrades(params?: {
  keyword?: string;
  refresh?: boolean;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.keyword) query.set("keyword", params.keyword);
  if (params?.refresh) query.set("refresh", "true");
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<BondMarketTradeItem>>(`/api/bond/market/trade${suffix ? `?${suffix}` : ""}`);
}

export async function getFxSpotQuotes(params?: {
  pair?: string;
  refresh?: boolean;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.pair) query.set("pair", params.pair);
  if (params?.refresh) query.set("refresh", "true");
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<FxSpotQuoteItem>>(`/api/fx/spot${suffix ? `?${suffix}` : ""}`);
}

export async function getFxSwapQuotes(params?: {
  pair?: string;
  refresh?: boolean;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.pair) query.set("pair", params.pair);
  if (params?.refresh) query.set("refresh", "true");
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<FxSwapQuoteItem>>(`/api/fx/swap${suffix ? `?${suffix}` : ""}`);
}

export async function getFxPairQuotes(params?: {
  pair?: string;
  refresh?: boolean;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.pair) query.set("pair", params.pair);
  if (params?.refresh) query.set("refresh", "true");
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<FxPairQuoteItem>>(`/api/fx/pair${suffix ? `?${suffix}` : ""}`);
}
