import api from "@/lib/api";

export async function getAIStudioCatalog() {
  const { data } = await api.get("/ai-studio/catalog");
  return data;
}

export async function runAIStudioTool(payload) {
  const { data } = await api.post("/ai-studio/runs", payload);
  return data;
}

export async function listGeneratedAssets(params = {}) {
  const { data } = await api.get("/ai-studio/generated-assets", { params });
  return data.items || [];
}

export async function listEditableDrafts() {
  const { data } = await api.get("/ai-studio/drafts");
  return data.items || [];
}

export async function listPromptEntries(params = {}) {
  const { data } = await api.get("/ai-studio/prompts", { params });
  return data.items || [];
}

export async function createPromptEntry(payload) {
  const { data } = await api.post("/ai-studio/prompts", payload);
  return data;
}

export async function publishPromptEntry(promptId) {
  const { data } = await api.post(`/ai-studio/prompts/${promptId}/publish`);
  return data;
}

export async function listAIStudioActivity(params = {}) {
  const { data } = await api.get("/ai-studio/activity", { params });
  return data.items || [];
}

