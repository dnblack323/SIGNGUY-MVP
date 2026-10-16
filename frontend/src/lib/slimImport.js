import api from "@/lib/api";

function formData({ file, passphrase, targetTenantId, confirmationPhrase, importUnassigned }) {
  const data = new FormData();
  data.append("file", file);
  data.append("passphrase", passphrase);
  data.append("target_tenant_id", targetTenantId);
  if (confirmationPhrase !== undefined) data.append("confirmation_phrase", confirmationPhrase);
  if (importUnassigned !== undefined) data.append("import_unassigned", importUnassigned ? "true" : "false");
  return data;
}

export async function previewSlimImport(payload) {
  const response = await api.post("/slim-import/preview", formData(payload), {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function confirmSlimImport(payload) {
  const response = await api.post("/slim-import/confirm", formData(payload), {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}
