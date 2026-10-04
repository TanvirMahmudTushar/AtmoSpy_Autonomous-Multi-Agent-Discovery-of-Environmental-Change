"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
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
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null)) // stale/expired token — drop it silently
      .finally(() => setLoading(false));
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
