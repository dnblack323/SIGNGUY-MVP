import api from "@/lib/api";

export async function listFormTemplates(params = {}) {
  const r = await api.get("/forms/templates", { params });
  return r.data.items || [];
}

export async function createFormTemplate(payload) {
  const r = await api.post("/forms/templates", payload);
  return r.data;
}

export async function updateFormTemplate(id, payload) {
  const r = await api.patch(`/forms/templates/${id}`, payload);
  return r.data;
}

export async function publishFormTemplate(id) {
  const r = await api.post(`/forms/templates/${id}/publish`);
  return r.data;
}

export async function archiveFormTemplate(id) {
  const r = await api.post(`/forms/templates/${id}/archive`);
  return r.data;
}

export async function duplicateFormTemplate(id) {
  const r = await api.post(`/forms/templates/${id}/duplicate`);
  return r.data;
}

export async function listFormResponses(params = {}) {
  const r = await api.get("/forms/responses", { params });
  return r.data.items || [];
}

export async function getPublicFormRequest(token) {
  const r = await api.get(`/public/forms/requests/${token}`);
  return r.data;
}

export async function submitPublicFormResponse(token, payload) {
  const r = await api.post(
    `/public/forms/requests/${token}/responses`,
    payload,
  );
  return r.data;
}
