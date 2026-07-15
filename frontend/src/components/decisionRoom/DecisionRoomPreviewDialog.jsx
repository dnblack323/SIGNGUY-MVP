import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { StatusPill } from "@/components/common/StatusPill";
import { centsToDollarsString } from "@/lib/format";

/**
 * EC10 Phase 10D — deterministic customer-safe preview, for STAFF eyes
 * only (never reachable by a customer in this phase — see `/preview`
 * router endpoint, which is behind `decision_room:read`, a staff-only
 * permission). Renders exactly what the `/preview` endpoint returns — no
 * internal_notes/cost/margin/employee-id ever reaches this component
 * because the backend already stripped them.
 */
export default function DecisionRoomPreviewDialog({ roomId, open, onOpenChange }) {
  const { data: preview } = useQuery({
    queryKey: ["decision-room-preview", roomId],
    queryFn: async () => (await api.get(`/decision-rooms/${roomId}/preview`)).data,
    enabled: open && !!roomId,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[680px] max-h-[80vh] overflow-y-auto" data-testid="decision-room-preview-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Customer-safe preview (internal, read-only)
            {preview && <StatusPill kind="decision_room" value={preview.status} />}
          </DialogTitle>
        </DialogHeader>
        {!preview ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <div className="grid gap-4">
            <div>
              <h2 className="text-lg font-semibold">{preview.title}</h2>
              {preview.customer_safe_intro && <p className="text-sm text-muted-foreground mt-1">{preview.customer_safe_intro}</p>}
            </div>
            <div className="grid gap-3">
              {(preview.options || []).map((o) => (
                <div key={o.id} className="rounded-lg border p-3 grid gap-1" data-testid={`decision-room-preview-option-${o.id}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{o.customer_label}</span>
                    {o.badge_type !== "none" && <StatusPill kind="decision_badge" value={o.badge_type} />}
                  </div>
                  {o.headline && <div className="text-sm">{o.headline}</div>}
                  {o.customer_safe_description && <p className="text-sm text-muted-foreground">{o.customer_safe_description}</p>}
                  {o.included_features?.length > 0 && (
                    <ul className="text-sm list-disc pl-5">{o.included_features.map((f, i) => <li key={i}>{f}</li>)}</ul>
                  )}
                  {o.expected_timing && <div className="text-xs text-muted-foreground">Timing: {o.expected_timing}</div>}
                  <div className="text-sm font-medium tabular-nums">
                    {o.displayed_price_cents != null ? centsToDollarsString(o.displayed_price_cents) : (o.price_display_mode === "contact_for_price" ? "Contact for price" : "Price hidden")}
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground italic">
              This is a read-only staff preview. No customer can select, reject, comment on, or otherwise act on this room yet — that experience is Phase 10E (not built).
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
