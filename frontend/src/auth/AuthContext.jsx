import { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import api from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [tenant, setTenant] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [devBypass, setDevBypass] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
      // If we're returning from the Google Sign-In redirect, GoogleAuthCallback
      // owns the exchange (and will call refresh() again once done) — skip the
      // normal check here to avoid a race that flashes the login page.
      if (window.location.hash?.includes("session_id=")) {
        setLoading(false);
        return;
      }
      // Check backend dev bypass status
      let bypass = false;
      try {
        const { data: cfg } = await api.get("/auth/dev-config");
        bypass = !!cfg?.dev_bypass;
        setDevBypass(bypass);
      } catch { /* ignore */ }

      let token = localStorage.getItem("signguy.token");

      // Auto-login via dev bypass if there's no token
      if (!token && bypass) {
        try {
          const { data } = await api.post("/auth/dev-login");
          localStorage.setItem("signguy.token", data.access_token);
          setUser(data.user); setTenant(data.tenant); setPermissions(data.permissions || []);
          setLoading(false);
          return;
        } catch { /* fall through to unauth state */ }
      }

      if (!token) {
        setUser(null); setTenant(null); setPermissions([]);
        setLoading(false);
        return;
      }
      const { data } = await api.get("/auth/me");
      setUser(data.user);
      setTenant(data.tenant);
      setPermissions(data.permissions || []);
    } catch (e) {
      setUser(null); setTenant(null); setPermissions([]);
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = useCallback(async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("signguy.token", data.access_token);
    setUser(data.user); setTenant(data.tenant); setPermissions(data.permissions || []);
    return data;
  }, []);

  const registerTenant = useCallback(async (payload) => {
    const { data } = await api.post("/auth/register-tenant", payload);
    localStorage.setItem("signguy.token", data.access_token);
    setUser(data.user); setTenant(data.tenant); setPermissions(data.permissions || []);
    return data;
  }, []);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch { /* ignore */ }
    localStorage.removeItem("signguy.token");
    setUser(null); setTenant(null); setPermissions([]);
    // In dev bypass mode, /login page will just auto-relogin \u2014 so stay on /login and let the user
    // pick a real account, or refresh to re-enter Dev Shop.
    window.location.href = "/login";
  }, []);

  const value = useMemo(() => ({
    user, tenant, permissions, loading, error, devBypass,
    hasPerm: (perm) => permissions.includes(perm),
    hasAny: (list) => list.some((p) => permissions.includes(p)),
    refresh, login, registerTenant, logout,
  }), [user, tenant, permissions, loading, error, devBypass, refresh, login, registerTenant, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
