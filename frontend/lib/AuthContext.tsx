"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { ApiError, api, getToken, setToken } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName?: string) => Promise<void>;
  loginAsGuest: () => Promise<void>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Only a 401 means the token is bad. Anything else (the free-tier backend
    // waking up, a network blip, a 5xx) is retried, and the token is kept
    // either way: dropping it would sign the user out for good, and a guest
    // has no way to sign back in to their account.
    let cancelled = false;
    (async () => {
      const retryDelays = [2000, 5000, 10000, 20000];
      for (let attempt = 0; getToken(); attempt++) {
        try {
          const me = await api.me();
          if (!cancelled) setUser(me);
          break;
        } catch (err) {
          if (err instanceof ApiError && err.status === 401) {
            setToken(null);
            break;
          }
          if (attempt >= retryDelays.length || cancelled) break;
          await new Promise((r) => setTimeout(r, retryDelays[attempt]));
        }
      }
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const res = await api.login(email, password);
      setToken(res.access_token);
      setUser(res.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
      throw err;
    }
  }, []);

  const signup = useCallback(async (email: string, password: string, displayName?: string) => {
    setError(null);
    try {
      const res = await api.signup(email, password, displayName);
      setToken(res.access_token);
      setUser(res.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign up failed.");
      throw err;
    }
  }, []);

  const loginAsGuest = useCallback(async () => {
    setError(null);
    try {
      const res = await api.guestLogin();
      setToken(res.access_token);
      setUser(res.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start a guest session.");
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return (
    <AuthContext.Provider value={{ user, loading, error, login, signup, loginAsGuest, logout, clearError }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
