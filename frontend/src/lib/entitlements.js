/**
 * EC2 — Feature Entitlement helpers.
 *
 * Small client-side wrapper for `/api/entitlements`. The backend remains
 * authoritative — this only decorates the UI (hide/show, "upgrade" badges).
 */
import api from "@/lib/api";

export async function listEntitlements() {
  const res = await api.get("/entitlements");
  return res.data || { items: [], total: 0 };
}

export async function checkEntitlement(featureKey) {
  try {
    const res = await api.get(`/entitlements/${encodeURIComponent(featureKey)}`);
    return { hasAccess: !!res.data?.has_access, entitlement: res.data?.entitlement || null };
  } catch (e) {
    if (e?.response?.status === 404) return { hasAccess: false, entitlement: null };
    throw e;
  }
}
