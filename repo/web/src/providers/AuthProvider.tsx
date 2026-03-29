import React, { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { getCurrentUser } from "../services/api";
import {
  AUTH_CHANGED_EVENT,
  clearAuthToken,
  getAdminModeEnabled,
  getAuthToken,
  setAdminModeEnabled,
} from "../utils/auth";

type AuthContextValue = {
  token: string | null;
  user: any;
  authEmail: string | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isAdminMode: boolean;
  isLoading: boolean;
  setAdminMode: (enabled: boolean) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<any>(null);
  const [isAdminMode, setIsAdminMode] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;

    const syncAuth = async () => {
      const nextToken = getAuthToken();
      if (!nextToken) {
        if (!active) {
          return;
        }
        setToken(null);
        setUser(null);
        setIsAdminMode(false);
        setIsLoading(false);
        return;
      }

      if (active) {
        setToken(nextToken);
        setIsLoading(true);
      }
      try {
        const nextUser = await getCurrentUser(nextToken);
        if (!active) {
          return;
        }
        const nextIsAdmin =
          !!nextUser && (Boolean(nextUser?.is_admin) || String(nextUser?.account || nextUser?.email || "").toLowerCase() === "admin");
        setToken(nextToken);
        setUser(nextUser);
        if (!nextIsAdmin) {
          setAdminModeEnabled(false);
        }
        setIsAdminMode(nextIsAdmin && getAdminModeEnabled());
      } catch {
        clearAuthToken();
        if (!active) {
          return;
        }
        setToken(null);
        setUser(null);
        setIsAdminMode(false);
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    };

    void syncAuth();
    window.addEventListener(AUTH_CHANGED_EVENT, syncAuth);
    return () => {
      active = false;
      window.removeEventListener(AUTH_CHANGED_EVENT, syncAuth);
    };
  }, []);

  const handleSetAdminMode = (enabled: boolean) => {
    setAdminModeEnabled(enabled);
    setIsAdminMode(enabled);
  };

  const value = useMemo<AuthContextValue>(() => {
    const authEmail = user ? String(user?.account || user?.email || "") || null : null;
    const isAdmin = !!token && !!user && (Boolean(user?.is_admin) || authEmail === "admin");
    return {
      token,
      user,
      authEmail,
      isAuthenticated: !!token && !!user,
      isAdmin,
      isAdminMode: isAdmin && isAdminMode,
      isLoading,
      setAdminMode: handleSetAdminMode,
    };
  }, [handleSetAdminMode, isAdminMode, isLoading, token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return value;
}
