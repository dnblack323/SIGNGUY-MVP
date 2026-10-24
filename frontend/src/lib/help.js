import api from "@/lib/api";

/**
 * Stable article slugs that Guided Onboarding and other screens link to.
 * Keep in sync with backend/app/help_content/catalog.py and
 * docs/modules/help_article_slug_registry.md.
 */
export const HELP_ARTICLE_SLUGS = {
  gettingStarted: "getting-started",
  companyProfile: "company-profile",
  pricingSetup: "pricing-setup",
  employeesAndPermissions: "employees-and-permissions",
  productionWorkflow: "production-workflow",
  customerPortal: "customer-portal",
  firstOrder: "first-order",
  webstoreSetup: "webstore-setup",
};

/** `/help/docs?article=<slug>`: opens Documentation on that article. */
export function helpDocsPath(slug, extra = {}) {
  const params = new URLSearchParams();
  if (slug) params.set("article", slug);
  Object.entries(extra).forEach(([key, value]) => value && params.set(key, value));
  const query = params.toString();
  return query ? `/help/docs?${query}` : "/help/docs";
}

export async function listHelpArticles(params = {}) {
  return (await api.get("/help/articles", { params })).data;
}

export async function getHelpArticle(slug) {
  return (await api.get(`/help/articles/${encodeURIComponent(slug)}`)).data;
}

export async function listHelpCategories() {
  return (await api.get("/help/categories")).data;
}

export async function getContextualHelp(surfaceKey, params = {}) {
  return (await api.get(`/help/contextual/${surfaceKey}`, { params })).data;
}

export async function sendHelpFeedback(payload) {
  return (await api.post("/help/feedback", payload)).data;
}

export async function getFailedSubscriptionGuidance() {
  return (await api.get("/help/billing/failed-subscription")).data;
}
