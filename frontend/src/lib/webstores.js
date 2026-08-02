import api from "@/lib/api";

export async function listWebstores(params = {}) {
  const r = await api.get("/webstores", { params });
  return r.data;
}

export async function getWebstore(id) {
  const r = await api.get(`/webstores/${id}`);
  return r.data;
}

export async function listWebstoreActivity(id, params = {}) {
  const r = await api.get(`/webstores/${id}/activity`, { params });
  return r.data;
}

export async function transitionWebstoreLifecycle(id, payload) {
  const r = await api.post(`/webstores/${id}/lifecycle`, payload);
  return r.data;
}

export async function listWebstoreLifecycleEvents(id, params = {}) {
  const r = await api.get(`/webstores/${id}/lifecycle-events`, { params });
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

export async function sendWebstoreQuestionnaire(id, payload = {}) {
  const r = await api.post(`/webstores/${id}/questionnaire/send`, payload);
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
  const r = await api.get("/webstores/product-templates/list");
  return r.data.items || [];
}

export async function createProductTemplate(payload) {
  const r = await api.post("/webstores/product-templates", payload);
  return r.data;
}

export async function updateProductTemplate(templateId, payload) {
  const r = await api.patch(`/webstores/product-templates/${templateId}`, payload);
  return r.data;
}

export async function archiveProductTemplate(templateId, payload) {
  const r = await api.post(`/webstores/product-templates/${templateId}/archive`, payload);
  return r.data;
}

export async function restoreProductTemplate(templateId, payload) {
  const r = await api.post(`/webstores/product-templates/${templateId}/restore`, payload);
  return r.data;
}

export async function createProductFromTemplate(webstoreId, payload) {
  const r = await api.post(`/webstores/${webstoreId}/products`, payload);
  return r.data;
}

export async function updateWebstoreProduct(webstoreId, productId, payload) {
  const r = await api.patch(`/webstores/${webstoreId}/products/${productId}`, payload);
  return r.data;
}

export async function archiveWebstoreProduct(webstoreId, productId, payload) {
  const r = await api.post(`/webstores/${webstoreId}/products/${productId}/archive`, payload);
  return r.data;
}

export async function restoreWebstoreProduct(webstoreId, productId, payload) {
  const r = await api.post(`/webstores/${webstoreId}/products/${productId}/restore`, payload);
  return r.data;
}

export async function listWebstoreProductCategories(webstoreId, params = {}) {
  const r = await api.get(`/webstores/${webstoreId}/product-categories`, { params });
  return r.data;
}

export async function listWebstoreArtwork(webstoreId, params = {}) {
  const r = await api.get(`/webstores/${webstoreId}/artwork`, { params });
  return r.data.items || [];
}

export async function listWebstoreMockups(webstoreId, params = {}) {
  const r = await api.get(`/webstores/${webstoreId}/mockups`, { params });
  return r.data.items || [];
}

export async function createWebstoreProductCategory(webstoreId, payload) {
  const r = await api.post(`/webstores/${webstoreId}/product-categories`, payload);
  return r.data;
}

export async function updateWebstoreProductCategory(webstoreId, categoryId, payload) {
  const r = await api.patch(`/webstores/${webstoreId}/product-categories/${categoryId}`, payload);
  return r.data;
}

export async function archiveWebstoreProductCategory(webstoreId, categoryId, payload) {
  const r = await api.post(`/webstores/${webstoreId}/product-categories/${categoryId}/archive`, payload);
  return r.data;
}

export async function restoreWebstoreProductCategory(webstoreId, categoryId, payload) {
  const r = await api.post(`/webstores/${webstoreId}/product-categories/${categoryId}/restore`, payload);
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

export async function updateWebstoreChangeRequest(webstoreId, requestId, payload) {
  const r = await api.post(`/webstores/${webstoreId}/change-requests/${requestId}`, payload);
  return r.data;
}

export async function getLaunchReadiness(webstoreId) {
  const r = await api.get(`/webstores/${webstoreId}/launch-readiness`);
  return r.data;
}

export async function getWebstorePaymentProviderStatus(webstoreId) {
  const r = await api.get(`/webstores/${webstoreId}/payment-provider`);
  return r.data;
}

export async function requestWebstorePaymentProviderAction(webstoreId, action) {
  const r = await api.post(`/webstores/${webstoreId}/payment-provider/${action}`);
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
