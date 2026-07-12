// EC7 phase 7d — Small helpers used across Inventory / Vendors / Supply / POs /
// Expenses / Finance / Tax / Reports pages. All money formatting delegates to
// lib/format.js — pages MUST NOT perform their own money math.
import { centsToDollarsString } from "./format";

export const BASIS_LABELS = {
  issued_invoices: "Invoice basis (accrual)",
  confirmed_payments_received: "Cash received basis",
  refunds: "Refunds",
  outstanding_receivables: "Outstanding A/R",
  expenses: "Expense basis",
  tax_collected: "Tax snapshot",
  estimated_cost: "Estimated cost",
  estimated_gross_profit: "Estimated gross profit",
  estimated_net_operating: "Estimated net operating",
  current_inventory: "Current inventory",
  immutable_ledger: "Immutable ledger",
  historical_snapshots: "Historical snapshots",
  purchase_orders: "Purchase orders",
  labeled_metrics: "Labeled metrics",
};

export function basisLabel(key) {
  return BASIS_LABELS[key] || key || "—";
}

// PO status → badge tone
export const PO_STATUS_TONE = {
  draft: "bg-slate-100 text-slate-700",
  submitted: "bg-blue-100 text-blue-800",
  acknowledged: "bg-indigo-100 text-indigo-800",
  partially_received: "bg-amber-100 text-amber-800",
  received: "bg-emerald-100 text-emerald-800",
  cancelled: "bg-rose-100 text-rose-800",
};

export const EXPENSE_STATE_TONE = {
  active: "bg-emerald-100 text-emerald-800",
  archived: "bg-slate-100 text-slate-700",
  voided: "bg-rose-100 text-rose-800",
};

export function money(cents) {
  return centsToDollarsString(cents);
}

// Simple debounce for search inputs
export function debounce(fn, ms = 250) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
