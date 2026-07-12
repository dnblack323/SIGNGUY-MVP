import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import employeePortalApi, { TOKEN_KEY } from "./employeePortalApi";

const EmployeePortalAuthContext = createContext(null);

export function EmployeePortalAuthProvider({ children }) {
  const [identity, setIdentity] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) { setIdentity(null); setPermissions([]); setLoading(false); return; }
    try {
      const r = await employeePortalApi.get("/portal/auth/me");
      setIdentity(r.data.identity);
      setPermissions(r.data.permissions || []);
    } catch { setIdentity(null); setPermissions([]); }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = useCallback(async ({ email, password, tenant_slug }) => {
    const r = await employeePortalApi.post("/portal/auth/login", { email, password, tenant_slug });
    localStorage.setItem(TOKEN_KEY, r.data.token);
    setIdentity(r.data.identity);
    setPermissions(r.data.identity.permissions || []);
  }, []);

  const verifyMagicLink = useCallback(async (token) => {
    const r = await employeePortalApi.post("/portal/auth/magic-link/verify", { token });
    localStorage.setItem(TOKEN_KEY, r.data.token);
    setIdentity(r.data.identity);
    setPermissions(r.data.identity.permissions || []);
  }, []);

  const requestMagicLink = useCallback(async ({ email, tenant_slug }) => {
    await employeePortalApi.post("/portal/auth/magic-link", { email, tenant_slug });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setIdentity(null); setPermissions([]);
    window.location.assign("/portal/employee/login");
  }, []);

  const value = useMemo(() => ({
    identity, permissions, loading,
    hasPerm: (p) => permissions.includes(p),
    login, verifyMagicLink, requestMagicLink, logout, refresh,
  }), [identity, permissions, loading, login, verifyMagicLink, requestMagicLink, logout, refresh]);

  return <EmployeePortalAuthContext.Provider value={value}>{children}</EmployeePortalAuthContext.Provider>;
}

export function useEmployeePortalAuth() {
  const ctx = useContext(EmployeePortalAuthContext);
  if (!ctx) throw new Error("useEmployeePortalAuth outside provider");
  return ctx;
}
