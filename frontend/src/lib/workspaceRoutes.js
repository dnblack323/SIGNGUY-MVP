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

export function workspaceKeyFromTarget(target) {
  if (!target) return "";
  if (target.record_id) return `${target.workspace_type}:${target.record_id}`;
  if (target.workspace_type === "pricing_calculator") return "pricing_calculator:default";
  return `${target.workspace_type}:${target.pathname}:${target.query_params?.id || ""}`;
}

function viewStateFromQuery(queryParams = {}) {
  return {
    ...(queryParams.tab ? { selected_tab: queryParams.tab, active_tab: queryParams.tab } : {}),
    ...(queryParams.view ? { view: queryParams.view } : {}),
    ...(queryParams.filter ? { filter: queryParams.filter } : {}),
    ...(queryParams.sort ? { sort: queryParams.sort } : {}),
    ...(queryParams.category ? { category: queryParams.category } : {}),
  };
}

export function detectWorkspaceTarget(location) {
  const pathname = location?.pathname || "/";
  const queryParams = queryParamsFromSearch(location.search);
  if (pathname === "/pricing-calculator") {
    return {
      workspace_type: "pricing_calculator",
      record_id: null,
      label: "Pricing Calculator",
      pathname,
      query_params: queryParams,
      view_state: viewStateFromQuery(queryParams),
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
      query_params: queryParams,
      view_state: viewStateFromQuery(queryParams),
    };
  }

  return null;
}
