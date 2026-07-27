const DETAIL_ROUTE_PATTERNS = [
  { type: "customer", prefix: "/customers/" },
  { type: "quote", prefix: "/quotes/" },
  { type: "order", prefix: "/orders/" },
  { type: "work_order", prefix: "/work-orders/" },
  { type: "invoice", prefix: "/invoices/" },
  { type: "decision_room", prefix: "/decision-rooms/" },
  { type: "webstore", prefix: "/webstores/" },
  { type: "wrap_lab", prefix: "/wrap-lab/" },
  { type: "material", prefix: "/materials/" },
  { type: "purchase_order", prefix: "/purchase-orders/" },
  { type: "vendor", prefix: "/vendors/" },
  { type: "employee", prefix: "/team/employees/" },
  { type: "equipment", prefix: "/team/equipment/" },
];

const EXCLUDED_RECORD_IDS = new Set(["new", "board"]);

function queryParamsFromSearch(search = "") {
  const params = new URLSearchParams(search);
  const out = {};
  for (const [key, value] of params.entries()) {
    out[key] = value;
  }
  return out;
}

export function pathFromWorkspace(workspace) {
  const params = new URLSearchParams(workspace?.query_params || {});
  const query = params.toString();
  return `${workspace?.pathname || "/"}${query ? `?${query}` : ""}`;
}

export function detectWorkspaceTarget(location) {
  const pathname = location?.pathname || "/";
  if (pathname === "/pricing-calculator") {
    return {
      workspace_type: "pricing_calculator",
      record_id: null,
      label: "Pricing Calculator",
      pathname,
      query_params: queryParamsFromSearch(location.search),
      view_state: {},
    };
  }

  for (const pattern of DETAIL_ROUTE_PATTERNS) {
    if (!pathname.startsWith(pattern.prefix)) continue;
    const recordId = pathname.slice(pattern.prefix.length).split("/")[0];
    if (!recordId || EXCLUDED_RECORD_IDS.has(recordId)) return null;
    return {
      workspace_type: pattern.type,
      record_id: decodeURIComponent(recordId),
      pathname,
      query_params: queryParamsFromSearch(location.search),
      view_state: {},
    };
  }

  return null;
}
