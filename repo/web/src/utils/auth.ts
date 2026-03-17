const AUTH_TOKEN_KEY = "kiloquant_auth_token";
export const AUTH_CHANGED_EVENT = "kiloquant:auth-token-changed";

function parseJwtPayload(token: string): Record<string, unknown> | null {
  const parts = String(token || "").split(".");
  if (parts.length < 2) {
    return null;
  }
  const payload = parts[1];
  if (!payload) {
    return null;
  }
  try {
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const decoded = window.atob(padded);
    const parsed = JSON.parse(decoded);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getAuthUserId(token?: string | null): number | null {
  if (typeof window === "undefined") {
    return null;
  }
  const rawToken = (token ?? getAuthToken()) || "";
  if (!rawToken) {
    return null;
  }
  const payload = parseJwtPayload(rawToken);
  const sub = Number(payload?.sub ?? 0);
  if (!Number.isFinite(sub) || sub <= 0) {
    return null;
  }
  return Math.floor(sub);
}

export function setAuthToken(token: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

export function clearAuthToken() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}
