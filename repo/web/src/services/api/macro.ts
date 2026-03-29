import { ApiPage, request } from "./core";

export async function getHeatmap(params?: {
  sector?: string;
  market?: string;
  min_change?: number;
  max_change?: number;
  as_of?: string;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.sector) query.set("sector", params.sector);
  if (params?.market) query.set("market", params.market);
  if (params?.min_change !== undefined) query.set("min_change", String(params.min_change));
  if (params?.max_change !== undefined) query.set("max_change", String(params.max_change));
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/heatmap${suffix ? `?${suffix}` : ""}`);
}

export async function getMacro(params?: {
  start?: string;
  end?: string;
  as_of?: string;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/macro${suffix ? `?${suffix}` : ""}`);
}

export async function getMacroSnapshot(params?: {
  as_of?: string;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  const limit = params?.limit !== undefined ? Math.min(Math.max(1, Math.trunc(params.limit)), 200) : undefined;
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.sort) query.set("sort", params.sort);
  if (limit !== undefined) query.set("limit", String(limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<{ key: string; date: string; value: number; score?: number }>>(
    `/api/macro/snapshot${suffix ? `?${suffix}` : ""}`,
    { label: "macro-snapshot" },
  );
}

export async function getMacroSeries(key: string, params?: { start?: string; end?: string }) {
  const query = new URLSearchParams();
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  const suffix = query.toString();
  return request(`/api/macro/series/${encodeURIComponent(key)}${suffix ? `?${suffix}` : ""}`, {
    label: "macro-series",
  });
}

export async function getSectorExposure(params?: {
  market?: string;
  basis?: string;
  limit?: number;
  offset?: number;
  sort?: "asc" | "desc";
  as_of?: string;
}) {
  const query = new URLSearchParams();
  if (params?.market) query.set("market", params.market);
  if (params?.basis) query.set("basis", params.basis);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.sort) query.set("sort", params.sort);
  if (params?.as_of) query.set("as_of", params.as_of);
  const suffix = query.toString();
  return request(`/api/sector/exposure${suffix ? `?${suffix}` : ""}`);
}
