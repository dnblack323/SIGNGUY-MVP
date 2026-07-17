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
const PAYROLL = {
  open: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  review: "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200",
  approved: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  partially_paid: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  paid: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  closed: "bg-slate-200 text-slate-600 ring-1 ring-slate-300",
  voided: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
};

// EC8 phase 8e — Equipment / Training / Certification
const EQUIPMENT_STATUS = {
  active: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  inactive: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  maintenance: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  retired: "bg-slate-200 text-slate-600 ring-1 ring-slate-300",
  archived: "bg-slate-200 text-slate-500 ring-1 ring-slate-300 line-through",
};
const ACCESS_POLICY = {
  no_required: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  recommended: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  required_override_allowed: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  required_no_override: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
};
const CERTIFICATION = {
  not_started: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  in_progress: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  pending_signoff: "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200",
  certified: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  expired: "bg-orange-100 text-orange-900 ring-1 ring-orange-200",
  revoked: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  failed: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  missing: "bg-slate-100 text-slate-500 ring-1 ring-slate-200",
};
const TRAINING_ASSIGNMENT = {
  not_started: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  in_progress: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  pending_signoff: "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200",
  completed: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  failed: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  expired: "bg-orange-100 text-orange-900 ring-1 ring-orange-200",
  cancelled: "bg-slate-200 text-slate-600 ring-1 ring-slate-300",
};

// EC10 phase 10B — Intake
const INTAKE = {
  draft: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  submitted: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  under_review: "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200",
  needs_information: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  accepted: "bg-teal-100 text-teal-800 ring-1 ring-teal-200",
  converted_to_quote: "bg-violet-100 text-violet-800 ring-1 ring-violet-200",
  converted_to_order: "bg-violet-100 text-violet-800 ring-1 ring-violet-200",
  rejected: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  cancelled: "bg-slate-200 text-slate-600 ring-1 ring-slate-300",
};
const INTAKE_PRIORITY = {
  low: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  normal: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  high: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  urgent: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
};
const INTAKE_PRICING = {
  not_started: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  information_needed: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  ready_for_pricing: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  pricing_in_progress: "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200",
  priced: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  manual_price_entered: "bg-teal-100 text-teal-800 ring-1 ring-teal-200",
  pricing_review_required: "bg-orange-100 text-orange-900 ring-1 ring-orange-200",
};

// EC10 phase 10D — Customer Decision Room
const DECISION_ROOM = {
  draft: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
  ready: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  published: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  expired: "bg-orange-100 text-orange-900 ring-1 ring-orange-200",
  closed: "bg-slate-200 text-slate-600 ring-1 ring-slate-300",
  archived: "bg-slate-200 text-slate-500 ring-1 ring-slate-300 line-through",
};
const DECISION_BADGE = {
  none: "bg-slate-100 text-slate-500 ring-1 ring-slate-200",
  recommended: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  best_value: "bg-teal-100 text-teal-800 ring-1 ring-teal-200",
  premium: "bg-violet-100 text-violet-800 ring-1 ring-violet-200",
  budget: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  fastest: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  custom: "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200",
};

// EC10 phase 10E-2 — Customer Decisions (append-only, staff read-only view)
const CUSTOMER_DECISION_ACTION = {
  option_selected: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  option_rejected: "bg-slate-200 text-slate-600 ring-1 ring-slate-300",
  all_options_rejected: "bg-rose-100 text-rose-800 ring-1 ring-rose-200",
  change_requested: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
};
const DECISION_REVIEW_STATUS = {
  pending_review: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  acknowledged: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  applied: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  open: "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  answered: "bg-sky-100 text-sky-800 ring-1 ring-sky-200",
  resolved: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  reviewed: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
  withdrawn: "bg-slate-200 text-slate-600 ring-1 ring-slate-300 line-through",
  superseded: "bg-slate-200 text-slate-600 ring-1 ring-slate-300 line-through",
  informational: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
};

const MAPS = {
  quote: QUOTE, order: ORDER, production: PROD, priority: PRIORITY, invoice: INV, email: EMAIL,
  employee: EMPLOYEE, announcement: ANNOUNCEMENT, payroll: PAYROLL, equipment_status: EQUIPMENT_STATUS,
  access_policy: ACCESS_POLICY, certification: CERTIFICATION, training_assignment: TRAINING_ASSIGNMENT,
  intake: INTAKE, intake_priority: INTAKE_PRIORITY, intake_pricing: INTAKE_PRICING,
  decision_room: DECISION_ROOM, decision_badge: DECISION_BADGE,
  customer_decision_action: CUSTOMER_DECISION_ACTION, decision_review_status: DECISION_REVIEW_STATUS,
};

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
