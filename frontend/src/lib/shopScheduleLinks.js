export function buildShopScheduleUrl({
  view = "appointments",
  create = false,
  customerId,
  orderId,
  workOrderId,
  eventType,
  title,
} = {}) {
  const params = new URLSearchParams();
  if (view) params.set("view", view);
  if (create) params.set("new", "1");
  if (customerId) params.set("customer_id", customerId);
  if (orderId) params.set("order_id", orderId);
  if (workOrderId) params.set("work_order_id", workOrderId);
  if (eventType) params.set("type", eventType);
  if (title) params.set("title", title);
  const query = params.toString();
  return `/shop-schedule${query ? `?${query}` : ""}`;
}
