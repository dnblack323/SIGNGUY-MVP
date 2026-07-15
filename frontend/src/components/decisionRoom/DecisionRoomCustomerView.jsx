import { StatusPill } from "@/components/common/StatusPill";

/**
 * EC10 Phase 10E-1 — pure, read-only Decision Room comparison view. Shared
 * by the Customer Portal detail page and the Public Token page (both fetch
 * the identical customer-safe shape from the backend — see
 * `decision_room_service.get_customer_view()`). No selection/rejection/
 * comment/question controls exist here yet — that is Phase 10E-2/10E-3.
 *
 * Known gap (documented, not solved here): `file_ids`/`rendered_preview_
 * file_id`/`thumbnail_file_id`/proof references are shown as plain
 * reference chips, not renderable images/PDFs — the existing `/files/*`
 * endpoints are staff-only (`document:read`), so no customer-safe file
 * byte-serving endpoint exists yet to actually preview them.
 */
export default function DecisionRoomCustomerView({ room }) {
  const money = (cents) => `$${(cents / 100).toFixed(2)}`;
  return (
    <div className="space-y-6" data-testid="decision-room-customer-view">
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-2xl font-semibold" data-testid="decision-room-customer-title">{room.title}</h1>
          <StatusPill kind="decision_room" value={room.status} />
        </div>
        {room.customer_safe_intro && <p className="text-slate-600 mt-1" data-testid="decision-room-customer-intro">{room.customer_safe_intro}</p>}
        {room.status === "expired" && <p className="text-sm text-orange-700 mt-2" data-testid="decision-room-expired-banner">This Decision Room has expired. It is shown here as a historical record.</p>}
        {room.status === "closed" && <p className="text-sm text-slate-500 mt-2" data-testid="decision-room-closed-banner">This Decision Room is closed. It is shown here as a historical record.</p>}
      </div>

      <div className="grid gap-4 sm:grid-cols-2" data-testid="decision-room-customer-options">
        {(room.options || []).map((o) => (
          <div key={o.id} className="rounded-lg border bg-white p-4 space-y-2" data-testid={`decision-room-customer-option-${o.id}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{o.customer_label}</span>
              {o.badge_type !== "none" && <StatusPill kind="decision_badge" value={o.badge_type} />}
            </div>
            {o.headline && <div className="text-sm font-medium text-slate-700">{o.headline}</div>}
            {o.customer_safe_description && <p className="text-sm text-slate-600">{o.customer_safe_description}</p>}
            {o.included_features?.length > 0 && (
              <ul className="text-sm list-disc pl-5 text-slate-700">{o.included_features.map((f, i) => <li key={i}>{f}</li>)}</ul>
            )}
            {o.excluded_features?.length > 0 && (
              <ul className="text-sm list-disc pl-5 text-slate-400">{o.excluded_features.map((f, i) => <li key={i}>Not included: {f}</li>)}</ul>
            )}
            {o.expected_timing && <div className="text-xs text-slate-500">Timing: {o.expected_timing}</div>}
            {(o.file_ids?.length > 0 || o.rendered_preview_file_id || o.thumbnail_file_id) && (
              <div className="text-xs text-slate-400" data-testid={`decision-room-customer-option-${o.id}-media`}>
                {(o.file_ids?.length || 0) + (o.rendered_preview_file_id ? 1 : 0)} attachment(s) referenced (preview coming soon)
              </div>
            )}
            <div className="text-lg font-semibold tabular-nums" data-testid={`decision-room-customer-option-${o.id}-price`}>
              {o.displayed_price_cents != null ? money(o.displayed_price_cents) : (o.price_display_mode === "contact_for_price" ? "Contact us for pricing" : "Price on request")}
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-400 italic">This is a read-only comparison. Selecting an option is not available yet.</p>
    </div>
  );
}
