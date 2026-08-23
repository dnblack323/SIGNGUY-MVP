export const CUSTOMER_IMAGE_SLOTS = ["primary", "secondary"];

export function productImagesForSave(draft = {}) {
  const bySlot = {};
  const responseImages = Array.isArray(draft.images) ? draft.images : [];
  CUSTOMER_IMAGE_SLOTS.forEach((slot) => {
    const explicit = draft.customer_images?.[slot];
    const responseImage = responseImages.find((image) => image?.slot === slot);
    const source = explicit || responseImage;
    if (!source) return;
    const fileId = source.file_id || source.fileId;
    const url = source.preview_url || source.url;
    const altText = source.alt_text || source.altText || "";
    if (!fileId && !url && !altText) return;
    bySlot[slot] = {
      slot,
      role: source.role || slot,
      ...(fileId ? { file_id: fileId } : {}),
      ...(source.file_name ? { file_name: source.file_name } : {}),
      ...(source.content_type ? { content_type: source.content_type } : {}),
      ...(!fileId && url ? { url } : {}),
      ...(altText ? { alt_text: altText } : {}),
    };
  });
  return bySlot;
}

export function productImageForSlot(product = {}, slot = "primary") {
  const explicit = product.customer_images?.[slot];
  const responseImage = Array.isArray(product.images)
    ? product.images.find((image) => image?.slot === slot)
    : null;
  return { explicit, responseImage };
}

export function staffProductImageUrl(product = {}, slot = "primary") {
  const { explicit, responseImage } = productImageForSlot(product, slot);
  return (
    explicit?.preview_url ||
    explicit?.url ||
    responseImage?.preview_url ||
    responseImage?.url ||
    ""
  );
}

export function productImageAltText(product = {}, slot = "primary") {
  const { explicit, responseImage } = productImageForSlot(product, slot);
  return explicit?.alt_text || responseImage?.alt_text || "";
}

export function toIntCents(value) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

export function productCatalogStatus(product = {}) {
  return (
    product.catalog_status ||
    product.setup_status ||
    (product.status === "draft" ? "planned" : product.status || "planned")
  );
}

export function editableAnswerValue(value) {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return value ?? "";
}

export function formatLabel(value) {
  return String(value || "").replace(/_/g, " ");
}

export function formatDateTime(value) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not recorded";
  return date.toLocaleString();
}

export function formatActivityLabel(value) {
  return formatLabel(String(value || "activity").replace(/^webstore\./, ""));
}

export function getProductSetupItems(product) {
  return [
    {
      label: "Basic information",
      done: Boolean(product?.name && product?.product_type),
    },
    {
      label: "Image or mockup",
      done: Boolean(staffProductImageUrl(product, "primary")),
    },
    {
      label: "Category",
      done: Boolean(
        product?.category_id || product?.category_name || product?.category,
      ),
    },
    { label: "Pricing", done: Number(product?.selling_price_cents || 0) > 0 },
    {
      label: "SKU or options",
      done: Boolean(product?.sku || (product?.variants || []).length),
    },
    {
      label: "Production setup",
      done: Boolean(product?.production_method || product?.production_notes),
    },
    {
      label: "Packet eligible",
      done: Boolean(
        product?.launch_packet_eligible ||
          productCatalogStatus(product) === "ready" ||
          productCatalogStatus(product) === "active",
      ),
    },
  ];
}
