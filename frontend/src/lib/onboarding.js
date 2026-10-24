import api from "@/lib/api";

export async function getOnboardingDashboard() {
  return (await api.get("/onboarding/dashboard")).data;
}

export async function updateOnboardingTask(taskKey, payload) {
  return (await api.post(`/onboarding/tasks/${taskKey}/status`, payload)).data;
}

export async function saveOnboardingPosition(payload) {
  return (await api.post("/onboarding/position", payload)).data;
}

export async function getSetupPackageHandoff() {
  return (await api.get("/onboarding/setup-package-handoff")).data;
}

export async function updateSetupPackageHandoff(payload) {
  return (await api.post("/onboarding/setup-package-handoff", payload)).data;
}

/**
 * Shared Help link contract: article links use `/help/docs?article=<slug>`.
 * Until the Help Center resolves the `article` param the route simply opens
 * the docs index, so a missing article degrades gracefully.
 */
export function helpHref(slug) {
  return slug ? `/help/docs?article=${encodeURIComponent(slug)}` : "/help/docs";
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
