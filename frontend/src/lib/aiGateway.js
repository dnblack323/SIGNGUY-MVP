import api from "@/lib/api";

export async function getAICreditAccount() {
  const { data } = await api.get("/ai/credits/account");
  return data;
}

export async function listAICreditLedger(limit = 100) {
  const { data } = await api.get("/ai/credits/ledger", { params: { limit } });
  return data.items || [];
}

export async function listAIHistory(limit = 100) {
  const { data } = await api.get("/ai/history", { params: { limit } });
  return data.items || [];
}

export async function listAIAlerts(status) {
  const { data } = await api.get("/ai/alerts", { params: status ? { status } : {} });
  return data.items || [];
}

export async function getPlatformAIDashboard() {
  const { data } = await api.get("/ai/platform/dashboard");
  return data;
}

export async function listGovernancePolicies() {
  const { data } = await api.get("/ai/platform/governance-policies");
  return data.items || [];
}

export async function listAIProviders() {
  const { data } = await api.get("/ai/platform/providers");
  return data.items || [];
}

export async function listAIModels() {
  const { data } = await api.get("/ai/platform/models");
  return data.items || [];
}
