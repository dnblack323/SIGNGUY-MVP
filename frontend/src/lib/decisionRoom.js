/**
 * EC10 Phase 10D — canonical, shared Decision Room contracts.
 *
 * Mirrors `app/services/decision_room_service.py` EXACTLY. The frontend
 * never invents a transition or a computed price — it only reflects what
 * the backend already returned, and the backend re-validates every write.
 */
export const DECISION_ROOM_STATUSES = ["draft", "ready", "published", "expired", "closed", "archived"];

// Matches `ALLOWED_TRANSITIONS` in decision_room_service.py. "published" is
// intentionally absent here — it is only reachable via the dedicated
// `/publish` action (which also freezes a version), never a plain transition.
export const ALLOWED_ROOM_TRANSITIONS = {
  draft: ["ready", "archived"],
  ready: ["draft", "archived"],
  published: ["closed", "expired", "archived"],
  expired: ["archived"],
  closed: ["archived"],
  archived: ["draft"],
};

export const ROOM_TRANSITION_LABELS = {
  ready: "Mark ready",
  draft: "Back to draft",
  published: "Publish",
  closed: "Close",
  expired: "Mark expired",
  archived: "Archive",
};

export const BADGE_TYPES = ["none", "recommended", "best_value", "premium", "budget", "fastest", "custom"];
export const BADGE_LABELS = {
  none: "No badge", recommended: "Recommended", best_value: "Best Value",
  premium: "Premium", budget: "Budget", fastest: "Fastest", custom: "Custom",
};

export const PRICE_DISPLAY_MODES = ["show_price", "hide_price", "contact_for_price"];
export const PRICE_DISPLAY_LABELS = {
  show_price: "Show price", hide_price: "Hide price", contact_for_price: "Contact for price",
};

export function blankDecisionOption() {
  return {
    customer_label: "", internal_name: "", badge_type: "none", custom_badge_text: "",
    headline: "", customer_safe_description: "", included_features: [], excluded_features: [],
    expected_timing: "", price_display_mode: "show_price", manual_price_cents: null,
    selected_price_source: "manual", pricing_snapshot_id: null,
    quote_line_item_id: null, order_item_id: null, proof_id: null,
    file_ids: [], visual_markup_id: null, rendered_preview_file_id: null, thumbnail_file_id: null,
    internal_notes: "", customer_safe_notes: "",
  };
}
