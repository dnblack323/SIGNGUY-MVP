import api from "@/lib/api";

export async function getBillingState() {
  try {
    const { data } = await api.get("/billing/state");
    return data;
  } catch (err) {
    if (err?.response?.status === 404) {
      return null;
    }
    throw err;
  }
}

export async function ensureBillingAccount(payload = {}) {
  const { data } = await api.post("/billing/account", payload);
  return data;
}

export async function startFreeTrial() {
  const { data } = await api.post("/billing/trials/free");
  return data;
}

export async function startExtendedTrialCheckout({ successUrl, cancelUrl }) {
  const { data } = await api.post("/billing/trials/extended-checkout", {
    idempotency_key: `extended-${Date.now()}`,
    success_url: successUrl,
    cancel_url: cancelUrl,
  });
  return data;
}

export async function createSubscriptionCheckout({ priceId, successUrl, cancelUrl }) {
  const { data } = await api.post("/billing/checkout-sessions", {
    session_type: "subscription",
    price_id: priceId,
    idempotency_key: `subscription-${priceId}-${Date.now()}`,
    success_url: successUrl,
    cancel_url: cancelUrl,
  });
  return data;
}

export async function createSetupPackageCheckout({ packageKey, successUrl, cancelUrl }) {
  const { data } = await api.post("/billing/setup-packages/checkout", {
    package_key: packageKey,
    idempotency_key: `setup-${packageKey}-${Date.now()}`,
    success_url: successUrl,
    cancel_url: cancelUrl,
  });
  return data;
}

export async function createBillingPortalSession(returnUrl) {
  const { data } = await api.post("/billing/portal-sessions", { return_url: returnUrl });
  return data;
}

export async function scheduleSubscriptionCancellation(subscriptionId, reason) {
  const { data } = await api.post(`/billing/subscriptions/${subscriptionId}/cancel`, { reason });
  return data;
}

export async function listCommercialProducts() {
  const { data } = await api.get("/commercial/catalog/products", { params: { status: "active" } });
  return data?.items || [];
}

export async function listCommercialPrices() {
  const { data } = await api.get("/commercial/catalog/prices");
  return data?.items || [];
}

