import api from "@/lib/api";

export async function listWebstores(params = {}) {
  const r = await api.get("/webstores", { params });
  return r.data;
}

export async function getWebstore(id) {
  const r = await api.get(`/webstores/${id}`);
  return r.data;
}

export async function createWebstoreOwner(payload) {
  const r = await api.post("/webstores/owners", payload);
  return r.data;
}

export async function createWebstore(payload) {
  const r = await api.post("/webstores", payload);
  return r.data;
}

export async function getWebstoreSetupProgress(id) {
  const r = await api.get(`/webstores/${id}/setup-progress`);
  return r.data;
}

export async function listWebstoreAssignments(id) {
  const r = await api.get(`/webstores/${id}/assignments`);
  return r.data.items || [];
}

export async function createWebstoreAssignment(id, payload) {
  const r = await api.post(`/webstores/${id}/assignments`, payload);
  return r.data;
}

export async function resendWebstoreInvitation(id, assignmentId) {
  const r = await api.post(`/webstores/${id}/assignments/${assignmentId}/resend`);
  return r.data;
}

export async function revokeWebstoreAssignment(id, assignmentId, reason) {
  const r = await api.post(`/webstores/${id}/assignments/${assignmentId}/revoke`, { reason });
  return r.data;
}

export async function getWebstoreQuestionnaire(id) {
  const r = await api.get(`/webstores/${id}/questionnaire`);
  return r.data;
}

export async function getWebstoreQuestionnaireResponse(id) {
  const r = await api.get(`/webstores/${id}/questionnaire-response`);
  return r.data;
}

export async function previewWebstoreAnswerApplication(id, payload) {
  const r = await api.post(`/webstores/${id}/questionnaire/apply-preview`, payload);
  return r.data;
}

export async function applyWebstoreAnswers(id, payload) {
  const r = await api.post(`/webstores/${id}/questionnaire/apply`, payload);
  return r.data;
}

export async function reverseWebstoreAnswerApplication(id, applicationId, payload) {
  const r = await api.post(`/webstores/${id}/answer-applications/${applicationId}/reverse`, payload);
  return r.data;
}

export async function listWebstoreSetupFiles(id) {
  const r = await api.get(`/webstores/${id}/setup-files`);
  return r.data.items || [];
}

export async function uploadWebstoreSetupFile(id, formData) {
  const r = await api.post(`/webstores/${id}/setup-files`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return r.data;
}

export async function listProductTemplates() {
  const r = await api.get("/webstores/product-templates/list", { params: { active: true } });
  return r.data.items || [];
}

export async function createProductFromTemplate(webstoreId, payload) {
  const r = await api.post(`/webstores/${webstoreId}/products`, payload);
  return r.data;
}

export async function updateWebstore(webstoreId, payload) {
  const r = await api.patch(`/webstores/${webstoreId}`, payload);
  return r.data;
}

export async function generateLaunchPacket(webstoreId, payload = {}) {
  const r = await api.post(`/webstores/${webstoreId}/launch-packets`, payload);
  return r.data;
}

export async function sendLaunchPacket(webstoreId, packetId) {
  const r = await api.post(`/webstores/${webstoreId}/launch-packets/${packetId}/send`);
  return r.data;
}

export async function getLaunchReadiness(webstoreId) {
  const r = await api.get(`/webstores/${webstoreId}/launch-readiness`);
  return r.data;
}

export async function setWebstoreStatus(webstoreId, status, reason) {
  const r = await api.post(`/webstores/${webstoreId}/status`, { status, reason });
  return r.data;
}

export async function getWebstoreReports(webstoreId) {
  const r = await api.get(`/webstores/${webstoreId}/reports`);
  return r.data;
}

export async function getWebstoreBranding(webstoreId) {
  const r = await api.get(`/webstores/${webstoreId}/branding`);
  return r.data;
}

export async function saveWebstoreBrandingDraft(webstoreId, content) {
  const r = await api.patch(`/webstores/${webstoreId}/branding/draft`, { content });
  return r.data;
}

export async function requestWebstoreBrandingReview(webstoreId, note = "") {
  const r = await api.post(`/webstores/${webstoreId}/branding/request-review`, { note });
  return r.data;
}

export async function publishWebstoreBranding(webstoreId) {
  const r = await api.post(`/webstores/${webstoreId}/branding/publish`);
  return r.data;
}
