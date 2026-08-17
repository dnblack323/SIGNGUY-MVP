import api from "@/lib/api";

export async function listWrapProjects(params = {}) {
  const r = await api.get("/wrap-lab/projects", { params });
  return r.data;
}

export async function getWrapProject(id) {
  const r = await api.get(`/wrap-lab/projects/${id}`);
  return r.data;
}

export async function searchWrapTargets(params = {}) {
  const r = await api.get("/wrap-lab/targets", { params });
  return r.data;
}

export async function createWrapVehicle(payload) {
  const r = await api.post("/wrap-lab/vehicles", payload);
  return r.data;
}

export async function updateWrapVehicle(id, payload) {
  const r = await api.patch(`/wrap-lab/vehicles/${id}`, payload);
  return r.data;
}

export async function listWrapVehicles(params = {}) {
  const r = await api.get("/wrap-lab/vehicles", { params });
  return r.data;
}

export async function createWrapProject(payload) {
  const r = await api.post("/wrap-lab/projects", payload);
  return r.data;
}

export async function updateWrapProject(id, payload) {
  const r = await api.patch(`/wrap-lab/projects/${id}`, payload);
  return r.data;
}

export async function advanceWrapProject(id, status, reason) {
  const r = await api.post(`/wrap-lab/projects/${id}/status`, { status, reason });
  return r.data;
}

export async function createCoveragePlan(projectId, payload) {
  const r = await api.post(`/wrap-lab/projects/${projectId}/coverage-plans`, payload);
  return r.data;
}

export async function createInspection(projectId, payload) {
  const r = await api.post(`/wrap-lab/projects/${projectId}/inspections`, payload);
  return r.data;
}

export async function updateInspection(inspectionId, payload) {
  const r = await api.patch(`/wrap-lab/inspections/${inspectionId}`, payload);
  return r.data;
}

export async function acknowledgeInspection(inspectionId, payload) {
  const r = await api.post(`/wrap-lab/inspections/${inspectionId}/acknowledgement`, payload);
  return r.data;
}

export async function listInspectionReviewLinks(inspectionId) {
  const r = await api.get(`/wrap-lab/inspections/${inspectionId}/review-links`);
  return r.data;
}

export async function createInspectionReviewLink(inspectionId, payload) {
  const r = await api.post(`/wrap-lab/inspections/${inspectionId}/review-links`, payload);
  return r.data;
}

export async function expireInspectionReviewLink(tokenId) {
  const r = await api.post(`/wrap-lab/inspection-review-links/${tokenId}/expire`);
  return r.data;
}

export async function revokeInspectionReviewLink(tokenId) {
  const r = await api.delete(`/wrap-lab/inspection-review-links/${tokenId}`);
  return r.data;
}

export async function createDesignScene(projectId, payload) {
  const r = await api.post(`/wrap-lab/projects/${projectId}/design-scenes`, payload);
  return r.data;
}

export async function updateDesignLayer(sceneId, layerId, updates) {
  const r = await api.patch(`/wrap-lab/design-scenes/${sceneId}/layers/${layerId}`, { updates });
  return r.data;
}

export async function createPanelPlan(projectId, payload) {
  const r = await api.post(`/wrap-lab/projects/${projectId}/panel-plans`, payload);
  return r.data;
}

export async function generateWrapPacket(projectId, packetType) {
  const r = await api.post(`/wrap-lab/projects/${projectId}/packets`, { packet_type: packetType });
  return r.data;
}

export async function createWrapSchedule(projectId, payload) {
  const r = await api.post(`/wrap-lab/projects/${projectId}/schedules`, payload);
  return r.data;
}

export async function createWrapWarranty(projectId, payload) {
  const r = await api.post(`/wrap-lab/projects/${projectId}/warranties`, payload);
  return r.data;
}

export async function createInstallationRecord(projectId, payload) {
  const r = await api.post(`/wrap-lab/projects/${projectId}/installation-records`, payload);
  return r.data;
}

export async function handoffWrapProject(projectId, payload = {}) {
  const r = await api.post(`/wrap-lab/projects/${projectId}/production-handoff`, payload);
  return r.data;
}

export async function getWrapReports() {
  const r = await api.get("/wrap-lab/reports");
  return r.data;
}
