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
