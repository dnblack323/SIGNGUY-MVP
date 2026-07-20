import api from "@/lib/api";

export async function getOnboardingDashboard() {
  return (await api.get("/onboarding/dashboard")).data;
}

export async function updateOnboardingTask(taskKey, payload) {
  return (await api.post(`/onboarding/tasks/${taskKey}/status`, payload)).data;
}

export async function applyCompanyProfile(payload) {
  return (await api.post("/onboarding/company-profile/apply", payload)).data;
}

export async function submitPricingScenario(payload) {
  return (await api.post("/onboarding/pricing/scenario", payload)).data;
}

export async function applyPricingScenario(submissionId, acceptedShopDefaults) {
  return (await api.post(`/onboarding/pricing/scenario/${submissionId}/apply`, { accepted_shop_defaults: acceptedShopDefaults })).data;
}

export async function createHistoricalInvoiceImport(payload) {
  return (await api.post("/onboarding/historical-invoices", payload)).data;
}

export async function getPlaceholderRegistry() {
  return (await api.get("/onboarding/placeholders")).data;
}

export async function previewPlaceholders(payload) {
  return (await api.post("/onboarding/placeholders/preview", payload)).data;
}

export async function createTemplateExercise(payload) {
  return (await api.post("/onboarding/template-exercises", payload)).data;
}

export async function getSetupPackageHandoff() {
  return (await api.get("/onboarding/setup-package-handoff")).data;
}

export async function updateSetupPackageHandoff(payload) {
  return (await api.post("/onboarding/setup-package-handoff", payload)).data;
}

export async function recordTestPortal(payload) {
  return (await api.post("/onboarding/test-portal", { result: payload })).data;
}

export async function searchHelp(params = {}) {
  return (await api.get("/help/articles", { params })).data;
}

export async function getHelpArticle(slug) {
  return (await api.get(`/help/articles/${slug}`)).data;
}

export async function getContextualHelp(surfaceKey, params = {}) {
  return (await api.get(`/help/contextual/${surfaceKey}`, { params })).data;
}

export async function sendHelpFeedback(payload) {
  return (await api.post("/help/feedback", payload)).data;
}

export async function createSupportEscalation(payload) {
  return (await api.post("/help/support/escalations", payload)).data;
}

export async function getFailedSubscriptionGuidance() {
  return (await api.get("/help/billing/failed-subscription")).data;
}
