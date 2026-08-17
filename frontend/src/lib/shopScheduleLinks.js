export function buildShopScheduleUrl({
  view = "appointments",
  create = false,
  customerId,
  contactId,
  quoteId,
  orderId,
  orderItemId,
  workOrderId,
  productionStageId,
  wrapProjectId,
  vehicleInspectionId,
  installationId,
  taskId,
  eventType,
  title,
  sourceType,
  sourceId,
} = {}) {
  const params = new URLSearchParams();
  if (view) params.set("view", view);
  if (create) params.set("new", "1");
  if (customerId) params.set("customer_id", customerId);
  if (contactId) params.set("contact_id", contactId);
  if (quoteId) params.set("quote_id", quoteId);
  if (orderId) params.set("order_id", orderId);
  if (orderItemId) params.set("order_item_id", orderItemId);
  if (workOrderId) params.set("work_order_id", workOrderId);
  if (productionStageId) params.set("production_stage_id", productionStageId);
  if (wrapProjectId) params.set("wrap_project_id", wrapProjectId);
  if (vehicleInspectionId) params.set("vehicle_inspection_id", vehicleInspectionId);
  if (installationId) params.set("installation_id", installationId);
  if (taskId) params.set("task_id", taskId);
  if (eventType) params.set("type", eventType);
  if (title) params.set("title", title);
  if (sourceType) params.set("source_type", sourceType);
  if (sourceId) params.set("source_id", sourceId);
  const query = params.toString();
  return `/shop-schedule${query ? `?${query}` : ""}`;
}
