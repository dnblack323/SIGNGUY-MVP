import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import portalApi from "./portalApi";

const PortalAuthContext = createContext(null);

export function PortalAuthProvider({ children }) {
  const [identity, setIdentity] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const token = localStorage.getItem("sg_portal_token");
    if (!token) { setIdentity(null); setPermissions([]); setLoading(false); return; }
    try {
      const r = await portalApi.get("/portal/auth/me");
      setIdentity(r.data.identity);
      setPermissions(r.data.permissions || []);
    } catch { setIdentity(null); setPermissions([]); }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = useCallback(async ({ email, password, tenant_slug }) => {
    const r = await portalApi.post("/portal/auth/login", { email, password, tenant_slug });
    localStorage.setItem("sg_portal_token", r.data.token);
    setIdentity(r.data.identity);
    setPermissions(r.data.identity.permissions || []);
  }, []);

  const verifyMagicLink = useCallback(async (token) => {
    const r = await portalApi.post("/portal/auth/magic-link/verify", { token });
    localStorage.setItem("sg_portal_token", r.data.token);
    setIdentity(r.data.identity);
    setPermissions(r.data.identity.permissions || []);
  }, []);

  const requestMagicLink = useCallback(async ({ email, tenant_slug }) => {
    await portalApi.post("/portal/auth/magic-link", { email, tenant_slug });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("sg_portal_token");
    setIdentity(null); setPermissions([]);
    window.location.assign("/portal/login");
  }, []);

  const value = useMemo(() => ({
    identity, permissions, loading,
    hasPerm: (p) => permissions.includes(p),
    login, verifyMagicLink, requestMagicLink, logout, refresh,
  }), [identity, permissions, loading, login, verifyMagicLink, requestMagicLink, logout, refresh]);

  return <PortalAuthContext.Provider value={value}>{children}</PortalAuthContext.Provider>;
}

export function usePortalAuth() {
  const ctx = useContext(PortalAuthContext);
  if (!ctx) throw new Error("usePortalAuth outside provider");
  return ctx;
}
