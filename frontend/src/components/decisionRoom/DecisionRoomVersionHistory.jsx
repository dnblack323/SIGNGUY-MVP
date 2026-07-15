import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { centsToDollarsString } from "@/lib/format";
import { relativeTime } from "@/lib/format";

/**
 * EC10 Phase 10D — read-only list of a Decision Room's frozen, append-only
 * published versions. Each version is byte-identical to the moment it was
 * published — never reconstructed from the room's current live state.
 */
export default function DecisionRoomVersionHistory({ roomId, open, onOpenChange }) {
  const { data } = useQuery({
    queryKey: ["decision-room-versions", roomId],
    queryFn: async () => (await api.get(`/decision-rooms/${roomId}/versions`)).data,
    enabled: open && !!roomId,
  });
  const versions = data?.items || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px] max-h-[80vh] overflow-y-auto" data-testid="decision-room-version-history-dialog">
        <DialogHeader><DialogTitle>Version history</DialogTitle></DialogHeader>
        {versions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No published versions yet.</p>
        ) : (
          <div className="grid gap-3">
            {versions.map((v) => (
              <div key={v.id} className="rounded-lg border p-3 grid gap-1" data-testid={`decision-room-version-${v.version_number}`}>
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">Version {v.version_number}</span>
                  <span className="text-xs text-muted-foreground">{relativeTime(v.created_at)}</span>
                </div>
                <div className="text-sm">{v.title}</div>
                <div className="text-xs text-muted-foreground">{(v.options_snapshot || []).length} option(s) frozen</div>
                <ul className="text-xs grid gap-0.5 mt-1">
                  {(v.options_snapshot || []).map((o) => (
                    <li key={o.id} className="flex items-center justify-between">
                      <span>{o.customer_label || o.internal_name || "Untitled option"}</span>
                      <span className="tabular-nums text-muted-foreground">
                        {o.selected_display_price_cents != null ? centsToDollarsString(o.selected_display_price_cents) : "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
