import { requestAuthed, requestAuthedJson } from "./core";

export type AdminUser = {
  id: number;
  email: string;
  is_active: boolean;
  is_email_verified: boolean;
  is_admin: boolean;
  created_at?: string | null;
  last_login_at?: string | null;
};

export type AdminUserPage = {
  items: AdminUser[];
  total: number;
  limit: number;
  offset: number;
};

export type AdminSystemStatus = {
  app_name: string;
  database_url: string;
  redis_url: string;
  cache_stats: {
    memory_cache?: {
      size: number;
      max_size: number;
      [key: string]: unknown;
    };
    redis_cache?: {
      keyspace_hits?: number;
      keyspace_misses?: number;
      total_commands_processed?: number;
      [key: string]: unknown;
    };
  };
};

export type AdminClearCacheResult = {
  cleared_count: number;
  pattern: string | null;
};

export type AdminAccessLog = {
  method: string;
  path: string;
  client_ip: string;
  status: number;
  duration_ms: number;
  timestamp: string;
};

export type AdminAccessStats = {
  total_requests: number;
  unique_ips: number;
  top_ips: { ip: string; count: number }[];
  status_distribution: { status: number; count: number }[];
  path_distribution: { path: string; count: number }[];
  hourly_counts: { hour: string; count: number }[];
};

export async function getAdminUsers(token: string, params?: { limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return requestAuthed<AdminUserPage>(`/api/admin/users${suffix ? `?${suffix}` : ""}`, token, {
    label: "admin-users",
  });
}

export async function updateAdminUser(
  token: string,
  userId: number,
  payload: { is_active?: boolean; is_admin?: boolean },
) {
  return requestAuthedJson<AdminUser>(`/api/admin/users/${userId}`, payload, token, {
    method: "PATCH",
    label: "admin-user-update",
  });
}

export async function getAdminSystemStatus(token: string) {
  return requestAuthed<AdminSystemStatus>("/api/admin/system", token, {
    label: "admin-system",
  });
}

export async function clearAdminCache(token: string, payload: { pattern?: string | null }) {
  return requestAuthedJson<AdminClearCacheResult>("/api/admin/system/clear-cache", payload, token, {
    label: "admin-clear-cache",
  });
}

export async function getAdminAccessLogs(token: string, limit = 200) {
  return requestAuthed<AdminAccessLog[]>(`/api/admin/access/logs?limit=${limit}`, token, {
    label: "admin-access-logs",
  });
}

export async function getAdminAccessStats(token: string) {
  return requestAuthed<AdminAccessStats>("/api/admin/access/stats", token, {
    label: "admin-access-stats",
  });
}
