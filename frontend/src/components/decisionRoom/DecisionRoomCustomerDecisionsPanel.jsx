import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import StatusPill from "@/components/common/StatusPill";
import { toast } from "sonner";

/**
 * EC10 Phase 10E-2 — staff, READ-ONLY view of every `CustomerDecision`
 * recorded on this room (pending AND superseded — superseded rows stay
 * visible as history, never hidden). Staff may view + acknowledge receipt
 * only. Accepting the commercial change, applying it to a Quote/Order
 * Item, or altering pricing is explicitly NOT here — that is Phase 10F.
 */
export default function DecisionRoomCustomerDecisionsPanel({ roomId, canAcknowledge }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["decision-room-decisions", roomId],
    queryFn: async () => (await api.get(`/decision-rooms/${roomId}/decisions`)).data,
  });
  const items = useMemo(() => data?.items || [], [data]);
  const supersededIds = useMemo(
    () => new Set(items.filter((d) => d.supersedes_decision_id).map((d) => d.supersedes_decision_id)),
    [items],
  );

  const acknowledge = useMutation({
    mutationFn: async (decisionId) => (await api.post(`/decision-rooms/${roomId}/decisions/${decisionId}/acknowledge`)).data,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["decision-room-decisions", roomId] }); toast.success("Acknowledged"); },
    onError: (err) => toast.error(extractError(err)),
  });

  if (isLoading) return null;
  if (items.length === 0) return null;

  return (
    <div className="grid gap-3" data-testid="decision-room-customer-decisions-panel">
      <h3 className="font-semibold text-sm">Customer decisions ({items.length})</h3>
      <div className="rounded-xl border bg-card divide-y">
        {items.map((d) => {
          const superseded = supersededIds.has(d.id);
          return (
            <div key={d.id} className="p-3 flex items-start justify-between gap-3 text-sm" data-testid={`decision-room-customer-decision-${d.id}`}>
              <div className="grid gap-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <StatusPill kind="customer_decision_action" value={d.action_type} />
                  <StatusPill kind="decision_review_status" value={d.internal_review_status} />
                  {superseded && <StatusPill kind="production" value="superseded" />}
                  <span className="text-xs text-muted-foreground">v{d.published_version_number} · {d.source_access_mode}</span>
                </div>
                {d.option_id && <div className="text-xs text-muted-foreground">Option: {d.option_id}</div>}
                {d.comment && <div className="text-sm">"{d.comment}"</div>}
                <div className="text-xs text-muted-foreground">{new Date(d.created_at).toLocaleString()}{d.actor_display ? ` · ${d.actor_display}` : ""}</div>
              </div>
              {canAcknowledge && d.internal_review_status === "pending_review" && (
                <Button
                  size="sm" variant="outline" disabled={acknowledge.isPending}
                  onClick={() => acknowledge.mutate(d.id)}
                  data-testid={`decision-room-acknowledge-${d.id}-button`}
                >
                  Acknowledge
                </Button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
