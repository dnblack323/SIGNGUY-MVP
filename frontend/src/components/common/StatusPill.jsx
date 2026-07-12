import { cn } from "@/lib/utils";

const QUOTE = {
  draft: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  sent: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  approved: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  declined: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  converted: "bg-violet-100 text-violet-800 ring-1 ring-violet-200",
};
const ORDER = {
  draft: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  confirmed: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  in_production: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  completed: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  cancelled: "bg-slate-200 text-slate-800 ring-1 ring-slate-300",
};
const PROD = {
  draft: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  released: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  queued: "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200",
  not_started: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  in_progress: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  blocked: "bg-orange-100 text-orange-900 ring-1 ring-orange-200",
  on_hold: "bg-orange-100 text-orange-900 ring-1 ring-orange-200",
  ready: "bg-teal-100 text-teal-800 ring-1 ring-teal-200",
  completed: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  cancelled: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  superseded: "bg-slate-200 text-slate-600 ring-1 ring-slate-300 line-through",
};
const PRIORITY = {
  low: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  normal: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  high: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  rush: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
};
const INV = {
  draft: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  sent: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  viewed: "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200",
  partially_paid: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  paid: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  overdue: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  void: "bg-slate-200 text-slate-800 ring-1 ring-slate-300",
};
const EMAIL = {
  queued: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  sent: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  delivered: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  failed: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  skipped: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
};

const EMPLOYEE = {
  active: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  suspended: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  inactive: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  terminated: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  archived: "bg-slate-200 text-slate-600 ring-1 ring-slate-300",
};
const ANNOUNCEMENT = {
  draft: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  published: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  expired: "bg-slate-200 text-slate-600 ring-1 ring-slate-300",
};

const MAPS = { quote: QUOTE, order: ORDER, production: PROD, priority: PRIORITY, invoice: INV, email: EMAIL, employee: EMPLOYEE, announcement: ANNOUNCEMENT };

export function StatusPill({ kind, value, className }) {
  const map = MAPS[kind] || QUOTE;
  const cls = map[value] || "bg-slate-100 text-slate-700 ring-1 ring-slate-200";
  const label = String(value || "unknown").replace(/_/g, " ");
  return (
    <span
      data-testid="status-pill"
      className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium capitalize", cls, className)}
    >
      {label}
    </span>
  );
}

export default StatusPill;
