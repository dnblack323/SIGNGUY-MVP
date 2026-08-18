export const CATEGORY_CARDS = [
  ["brand_basics", "Brand Basics"],
  ["colors_fonts", "Colors & Fonts"],
  ["header", "Header"],
  ["hero", "Hero Section"],
  ["store_information", "Store Information"],
  ["store_type_content", "Store-Type Content"],
  ["catalog_introduction", "Catalog Introduction"],
  ["footer", "Footer"],
];

export const STATUS_LABELS = {
  draft: "Draft",
  waiting_owner_approval: "Waiting for Owner Approval",
  changes_requested: "Changes Requested",
  owner_approved: "Owner Approved",
  published: "Published",
};

export const TYPE_LABELS = {
  b2b: "B2B",
  fundraiser: "Fundraiser",
  event: "Event",
  promotional: "Promotional",
  employee: "Employee Store",
  general: "General Store",
};

export function getPath(data, path) {
  return path.split(".").reduce((current, part) => current?.[part], data);
}

export function setPath(data, path, value) {
  const parts = path.split(".");
  const copy = JSON.parse(JSON.stringify(data || {}));
  let cursor = copy;
  parts.slice(0, -1).forEach((part) => {
    cursor[part] = cursor[part] || {};
    cursor = cursor[part];
  });
  cursor[parts[parts.length - 1]] = value;
  return copy;
}

export function statusLabel(status) {
  return STATUS_LABELS[status] || "Draft";
}

export function buttonRadius(style) {
  if (style === "square") return "0px";
  if (style === "rounded") return "999px";
  return "8px";
}

export function safeDestination(destination) {
  if (destination === "store_information") return "#store-information";
  if (destination === "contact") return "#store-footer";
  if (destination === "none") return undefined;
  return "#catalog";
}

export function headingFontFamily(font) {
  if (font === "serif") return "Georgia, serif";
  if (font === "display") return "'Trebuchet MS', 'Arial Black', sans-serif";
  if (font === "condensed") return "'Arial Narrow', Arial, sans-serif";
  return "Inter, system-ui, sans-serif";
}

export function overlayColor(hex) {
  const value = /^#[0-9a-fA-F]{6}$/.test(hex || "") ? hex : "#000000";
  const r = parseInt(value.slice(1, 3), 16);
  const g = parseInt(value.slice(3, 5), 16);
  const b = parseInt(value.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, 0.42)`;
}
