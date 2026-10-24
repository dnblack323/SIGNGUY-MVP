/**
 * F3 — Shop Schedule model (Price Lab Schedule patterns, MVP calendar data).
 *
 * All calendar dates are LOCAL dates ("YYYY-MM-DD" in the viewer's time
 * zone). Event instants from the API are ISO timestamps and are converted to
 * local dates/times only here, so a 9 PM event never lands on the next day.
 */

const pad = (value) => String(value).padStart(2, "0");

export function localDateKey(value = new Date()) {
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

export function parseLocalDateKey(key, hour = 12) {
  const match = String(key || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), hour, 0, 0, 0);
  if (date.getFullYear() !== Number(match[1]) || date.getMonth() !== Number(match[2]) - 1 || date.getDate() !== Number(match[3])) return null;
  return date;
}

export function isDateKey(key) {
  return parseLocalDateKey(key) !== null;
}

export function addLocalDays(key, amount) {
  const date = parseLocalDateKey(key);
  if (!date) return key;
  date.setDate(date.getDate() + amount);
  return localDateKey(date);
}

export function addLocalMonths(key, amount) {
  const date = parseLocalDateKey(key);
  if (!date) return key;
  const day = date.getDate();
  date.setDate(1);
  date.setMonth(date.getMonth() + amount);
  const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  date.setDate(Math.min(day, lastDay));
  return localDateKey(date);
}

/** Six weeks starting on the Sunday on or before the 1st of the month. */
export function monthGrid(key) {
  const selected = parseLocalDateKey(key) || new Date();
  const first = new Date(selected.getFullYear(), selected.getMonth(), 1, 12);
  first.setDate(first.getDate() - first.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(first);
    date.setDate(first.getDate() + index);
    return { key: localDateKey(date), day: date.getDate(), inMonth: date.getMonth() === selected.getMonth() };
  });
}

/** First and last local date keys shown by a view (the month view shows its six-week grid). */
export function visibleDateKeys(view, key) {
  if (view === "day") return { first: key, last: key };
  const grid = monthGrid(key);
  return { first: grid[0].key, last: grid[41].key };
}

/** Local-midnight boundaries as ISO instants for the API. */
export function rangeForView(view, key) {
  const { first, last } = visibleDateKeys(view, key);
  return { start_at: localMidnight(first).toISOString(), end_at: localMidnight(addLocalDays(last, 1)).toISOString() };
}

function localMidnight(key) {
  const date = parseLocalDateKey(key, 0) || new Date();
  date.setHours(0, 0, 0, 0);
  return date;
}

export function monthLabel(key) {
  return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(parseLocalDateKey(key) || new Date());
}

export function fullDateLabel(key) {
  return new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" }).format(parseLocalDateKey(key) || new Date());
}

export function formatTime(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

/* ---------------------------------------------------------------- types --- */

/**
 * Display types. Production and Installation are the primary filters; every
 * other operational item stays visible under All.
 */
export const SCHEDULE_TYPES = [
  { key: "production", label: "Production", dot: "bg-blue-600", card: "border-blue-600 bg-blue-50", text: "text-blue-900" },
  { key: "installation", label: "Installation", dot: "bg-emerald-600", card: "border-emerald-600 bg-emerald-50", text: "text-emerald-900" },
  { key: "appointment", label: "Appointments", dot: "bg-purple-600", card: "border-purple-600 bg-purple-50", text: "text-purple-900" },
  { key: "pickup_delivery", label: "Pickup / Delivery", dot: "bg-amber-500", card: "border-amber-500 bg-amber-50", text: "text-amber-900" },
  { key: "task", label: "Tasks", dot: "bg-teal-600", card: "border-teal-600 bg-teal-50", text: "text-teal-900" },
  { key: "other", label: "Other", dot: "bg-slate-500", card: "border-slate-500 bg-slate-50", text: "text-slate-800" },
];
export const TYPE_BY_KEY = Object.fromEntries(SCHEDULE_TYPES.map((type) => [type.key, type]));

export const SCHEDULE_FILTERS = [
  { key: "all", label: "All" },
  { key: "production", label: "Production" },
  { key: "installation", label: "Installation" },
];

export function scheduleType(item) {
  const eventType = item?.event_type;
  if (item?.source_type === "production_stage" || eventType === "production_milestone") return "production";
  if (eventType === "installation" || item?.installation_id) return "installation";
  if (eventType === "vehicle_dropoff" || eventType === "vehicle_pickup") return "pickup_delivery";
  if (["consultation", "site_survey", "customer_meeting"].includes(eventType)) return "appointment";
  if (item?.source_type === "task" || eventType === "task_due") return "task";
  return "other";
}

export function typesForFilter(filter) {
  return filter === "all" ? SCHEDULE_TYPES.map((type) => type.key) : [filter];
}

/* ------------------------------------------------------------ placement --- */

// Without a visible range, expansion is capped as a safety net; views always pass their range.
const UNBOUNDED_EXPANSION_DAYS = 400;

/**
 * Local date keys an item covers (multi-day items appear on every date).
 * `range` ({ first, last } date keys) clamps the expansion to the visible
 * calendar, so an event of any length shows on every visible date it overlaps.
 */
export function itemDateKeys(item, range = null) {
  const start = new Date(item?.start_at);
  const end = new Date(item?.end_at || item?.start_at);
  if (Number.isNaN(start.getTime())) return [];
  const lastInstant = Number.isNaN(end.getTime()) || end <= start ? start : new Date(end.getTime() - 1);
  let cursor = localDateKey(start);
  let last = localDateKey(lastInstant);
  if (range?.first && cursor < range.first) cursor = range.first;
  if (range?.last && last > range.last) last = range.last;
  const keys = [];
  for (let guard = 0; cursor <= last && (range || guard < UNBOUNDED_EXPANSION_DAYS); guard += 1) {
    keys.push(cursor);
    cursor = addLocalDays(cursor, 1);
  }
  return keys;
}

export function groupByDate(items, range = null) {
  const map = new Map();
  for (const item of items) {
    for (const key of itemDateKeys(item, range)) {
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    }
  }
  return map;
}

export function typeCounts(items) {
  const counts = new Map();
  for (const item of items) counts.set(scheduleType(item), (counts.get(scheduleType(item)) || 0) + 1);
  return SCHEDULE_TYPES.filter((type) => counts.has(type.key)).map((type) => ({ ...type, count: counts.get(type.key) }));
}

/**
 * Wall-clock minutes (local hour * 60 + minute) of `iso` on `dateKey`,
 * clamped to the day. Uses the displayed clock time, not elapsed time since
 * midnight, so a 9:00 AM event sits at 9:00 on daylight-saving change days.
 */
export function minutesWithinDay(iso, dateKey) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 0;
  const key = localDateKey(date);
  if (key < dateKey) return 0;
  if (key > dateKey) return 1440;
  return date.getHours() * 60 + date.getMinutes();
}

/**
 * Side-by-side columns so simultaneous items in one lane are all visible.
 * Returns items with { top, height, column, columns } in minutes.
 */
export function layoutDayItems(items, dateKey) {
  const placed = items
    .map((item) => {
      const top = minutesWithinDay(item.start_at, dateKey);
      const bottom = Math.max(top + 20, minutesWithinDay(item.end_at || item.start_at, dateKey));
      return { item, top, bottom };
    })
    .sort((a, b) => a.top - b.top || b.bottom - a.bottom);
  const result = [];
  let cluster = [];
  let clusterEnd = -1;
  const flush = () => {
    const columns = [];
    for (const entry of cluster) {
      let column = columns.findIndex((end) => end <= entry.top);
      if (column === -1) {
        column = columns.length;
        columns.push(entry.bottom);
      } else {
        columns[column] = entry.bottom;
      }
      entry.column = column;
    }
    for (const entry of cluster) result.push({ ...entry, columns: columns.length, height: entry.bottom - entry.top });
    cluster = [];
    clusterEnd = -1;
  };
  for (const entry of placed) {
    if (cluster.length && entry.top >= clusterEnd) flush();
    cluster.push(entry);
    clusterEnd = Math.max(clusterEnd, entry.bottom);
  }
  if (cluster.length) flush();
  return result;
}

/** Hours shown in the day grid: 7 AM to 7 PM, widened to fit the day's items. */
export function visibleHours(laidOut) {
  let first = 7;
  let last = 19;
  for (const entry of laidOut) {
    first = Math.min(first, Math.floor(entry.top / 60));
    last = Math.max(last, Math.ceil(entry.bottom / 60));
  }
  return { first: Math.max(0, first), last: Math.min(24, Math.max(last, first + 1)) };
}

/* -------------------------------------------------------------- records --- */

export function linkedRecords(item) {
  const links = [];
  if (item?.order_id) links.push({ label: "Order", to: `/orders/${item.order_id}` });
  if (item?.work_order_id) links.push({ label: "Work Order", to: `/work-orders/${item.work_order_id}` });
  if (item?.quote_id) links.push({ label: "Quote", to: `/quotes/${item.quote_id}` });
  if (item?.customer_id) links.push({ label: "Customer", to: `/customers/${item.customer_id}` });
  if (item?.wrap_project_id) links.push({ label: "Wrap project", to: `/wrap-lab/${item.wrap_project_id}` });
  if (item?.source_type === "task") links.push({ label: "Task", to: "/team/tasks" });
  return links;
}

export function assignedPeople(item) {
  return (item?.assignment_summary?.employees || []).map((entry) => entry.name).filter(Boolean);
}

export function reservedResources(item) {
  const summary = item?.assignment_summary || {};
  return [...(summary.equipment || []), ...(summary.vehicles || []), ...(summary.resources || [])].map((entry) => entry.name).filter(Boolean);
}

/* ------------------------------------------------------------ authority --- */

// Mirrors CALENDAR_OVERRIDE_ROLES in the backend, which still enforces it.
const CONFLICT_OVERRIDE_ROLES = new Set(["owner", "admin", "manager"]);

export function canOverrideConflicts(user) {
  return CONFLICT_OVERRIDE_ROLES.has(String(user?.role || "").toLowerCase());
}
