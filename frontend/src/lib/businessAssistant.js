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

export async function recordVoiceUsage(voiceSessionId, payload) {
  const { data } = await api.post(`/assistant/voice/sessions/${voiceSessionId}/usage`, payload);
  return data;
}

export async function listAssistantQuickActions(params = {}) {
  const { data } = await api.get("/assistant/quick-actions", { params });
  return data.items || [];
}

export async function createStudioDelegation(payload) {
  const { data } = await api.post("/assistant/delegations/studio", payload);
  return data;
}

export async function listAssistantMemory() {
  const { data } = await api.get("/assistant/memory");
  return data.items || [];
}

export async function saveAssistantMemory(payload) {
  const { data } = await api.post("/assistant/memory", payload);
  return data;
}

export async function deleteAssistantMemory(memoryId) {
  const { data } = await api.delete(`/assistant/memory/${memoryId}`);
  return data;
}

export async function listAssistantRoutines() {
  const { data } = await api.get("/assistant/routines");
  return data.items || [];
}

export async function createAssistantRoutine(payload) {
  const { data } = await api.post("/assistant/routines", payload);
  return data;
}

export async function updateAssistantRoutine(routineId, payload) {
  const { data } = await api.patch(`/assistant/routines/${routineId}`, payload);
  return data;
}

export async function disableAssistantRoutine(routineId) {
  const { data } = await api.post(`/assistant/routines/${routineId}/disable`);
  return data;
}

export async function enableAssistantRoutine(routineId) {
  const { data } = await api.post(`/assistant/routines/${routineId}/enable`);
  return data;
}

export async function deleteAssistantRoutine(routineId) {
  const { data } = await api.delete(`/assistant/routines/${routineId}`);
  return data;
}

export async function listAssistantInsights(params = {}) {
  const { data } = await api.get("/assistant/insights", { params });
  return data.items || [];
}

export async function dismissAssistantInsight(insightId) {
  const { data } = await api.post(`/assistant/insights/${insightId}/dismiss`);
  return data;
}
