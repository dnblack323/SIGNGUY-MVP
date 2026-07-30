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
      // If we're returning from Google OAuth, GoogleAuthCallback owns the
      // exchange and will call refresh() again once done.
      if (window.location.pathname === "/auth/google/callback") {
        setLoading(false);
        return;
      }

      let bypass = false;
      try {
        const { data: cfg } = await api.get("/auth/dev-config");
        bypass = !!cfg?.dev_bypass;
        setDevBypass(bypass);
      } catch { /* ignore */ }

      let token = localStorage.getItem("signguy.token");

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

  const login = useCallback(async (tenantSlug, email, password) => {
    const { data } = await api.post("/auth/login", { tenant_slug: tenantSlug, email, password });
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
