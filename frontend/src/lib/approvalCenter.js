export function buildApprovalCenterUrl({
  create = false,
  targetType,
  targetId,
  customerId,
  title,
} = {}) {
  const params = new URLSearchParams();
  if (create) params.set("new", "1");
  if (targetType) params.set("target_type", targetType);
  if (targetId) params.set("target_id", targetId);
  if (customerId) params.set("customer_id", customerId);
  if (title) params.set("title", title);
  const query = params.toString();
  return `/approval-center${query ? `?${query}` : ""}`;
}
