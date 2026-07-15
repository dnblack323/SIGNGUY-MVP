/**
 * EC10 Phase 10B — canonical, shared intake contracts.
 *
 * `ALLOWED_TRANSITIONS` mirrors `app/services/intake_service.py` EXACTLY —
 * the frontend never invents a transition; it only offers what the backend
 * would accept, and the backend re-validates on every call regardless.
 */
export const INTAKE_STATUSES = [
  "draft", "submitted", "under_review", "needs_information",
  "accepted", "converted_to_quote", "converted_to_order", "rejected", "cancelled",
];

export const ALLOWED_TRANSITIONS = {
  draft: ["submitted", "cancelled"],
  submitted: ["under_review", "needs_information", "cancelled"],
  under_review: ["needs_information", "accepted", "rejected", "cancelled"],
  needs_information: ["submitted", "cancelled"],
  accepted: ["converted_to_quote", "converted_to_order", "cancelled"],
  converted_to_quote: [],
  converted_to_order: [],
  rejected: [],
  cancelled: [],
};

export const TRANSITION_LABELS = {
  submitted: "Submit for review",
  under_review: "Start review",
  needs_information: "Request more information",
  accepted: "Accept",
  converted_to_quote: "Mark converted to quote",
  converted_to_order: "Mark converted to order",
  rejected: "Reject",
  cancelled: "Cancel",
};

export const INTAKE_CATEGORIES = [
  "banners", "rigid_signs", "digital_print", "cut_vinyl",
  "apparel", "promotional", "vehicle_graphics", "services", "custom",
];

export const INTAKE_SOURCE_TYPES = [
  "internal_user", "customer_portal", "public_intake_link", "questionnaire",
  "email_import", "quote", "order", "saved_template", "api", "other",
];

export const INTAKE_PRIORITIES = ["low", "normal", "high", "urgent"];

export const INTAKE_PRICING_STATUSES = [
  "not_started", "information_needed", "ready_for_pricing",
  "pricing_in_progress", "priced", "manual_price_entered", "pricing_review_required",
];

export function blankIntakeItem() {
  return {
    _localId: `local-${Math.random().toString(36).slice(2)}`,
    category: "", item_name: "", description: "", quantity: 1,
    saved_item_id: null, material_profile_id: null, pricing_component_ids: [],
    file_ids: [], customer_notes: "", internal_notes: "",
    proof_required: false, approval_required: false,
    requested_due_date: "", installation_required: false,
  };
}
