import api from "@/lib/api";

export async function getAssistantCatalog() {
  const { data } = await api.get("/assistant/catalog");
  return data;
}

export async function listAssistantConversations(params = {}) {
  const { data } = await api.get("/assistant/conversations", { params });
  return data.items || [];
}

export async function getAssistantConversation(conversationId) {
  const { data } = await api.get(`/assistant/conversations/${conversationId}`);
  return data;
}

export async function sendAssistantMessage(payload) {
  const { data } = await api.post("/assistant/messages", payload);
  return data;
}

export async function proposeAssistantAction(payload) {
  const { data } = await api.post("/assistant/actions/proposals", payload);
  return data;
}

export async function editAssistantProposal(proposalId, payload) {
  const { data } = await api.patch(`/assistant/actions/proposals/${proposalId}`, payload);
  return data;
}

export async function confirmAssistantProposal(proposalId) {
  const { data } = await api.post(`/assistant/actions/proposals/${proposalId}/confirm`);
  return data;
}

export async function cancelAssistantProposal(proposalId) {
  const { data } = await api.post(`/assistant/actions/proposals/${proposalId}/cancel`);
  return data;
}

export async function executeAssistantProposal(proposalId, idempotencyKey) {
  const { data } = await api.post(`/assistant/actions/proposals/${proposalId}/execute`, {}, { headers: { "Idempotency-Key": idempotencyKey } });
  return data;
}

export async function getVoiceConfig() {
  const { data } = await api.get("/assistant/voice/config");
  return data;
}

export async function createVoiceSession(payload) {
  const { data } = await api.post("/assistant/voice/sessions", payload);
  return data;
}
