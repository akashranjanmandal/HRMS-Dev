"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, clearToken, getToken, setToken } from "./api";

/** Mirrors MeOut in backend/app/schemas/auth.py. */
export interface CurrentUser {
  id: number;
  email: string;
  role_code: string;
  role_name: string;
  permissions: string[];
}

/** Mirrors LoginOut in backend/app/schemas/auth.py. */
interface LoginOut {
  mfa_required: boolean;
  access_token?: string | null;
}

interface AuthState {
  user: CurrentUser | null;
  loading: boolean;
  /** Step 1: email + password. Returns true when an OTP step is required. */
  login: (email: string, password: string) => Promise<{ mfaRequired: boolean }>;
  /** Step 2: email + the emailed one-time code. */
  verifyOtp: (email: string, code: string) => Promise<CurrentUser>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  /** True only if the signed-in user holds every code given. */
  hasPermission: (...codes: string[]) => boolean;
  /** True if the signed-in user holds any of the codes given. */
  hasAnyPermission: (...codes: string[]) => boolean;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.get<CurrentUser>("/api/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post<LoginOut>("/api/auth/login", { email, password });
    if (res.mfa_required || !res.access_token) {
      return { mfaRequired: true };
    }
    setToken(res.access_token);
    setUser(await api.get<CurrentUser>("/api/auth/me"));
    return { mfaRequired: false };
  }, []);

  const verifyOtp = useCallback(async (email: string, code: string) => {
    const res = await api.post<LoginOut>("/api/auth/verify-otp", { email, code });
    if (!res.access_token) {
      throw new Error("Sign-in did not return an access token");
    }
    setToken(res.access_token);
    const me = await api.get<CurrentUser>("/api/auth/me");
    setUser(me);
    return me;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } catch {
      /* best effort — the token may already be invalid */
    }
    clearToken();
    setUser(null);
    window.location.href = "/login";
  }, []);

  const hasPermission = useCallback(
    (...codes: string[]) => !!user && codes.every((c) => user.permissions.includes(c)),
    [user]
  );

  const hasAnyPermission = useCallback(
    (...codes: string[]) => !!user && codes.some((c) => user.permissions.includes(c)),
    [user]
  );

  return (
    <AuthContext.Provider
      value={{ user, loading, login, verifyOtp, logout, refresh, hasPermission, hasAnyPermission }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
