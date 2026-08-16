import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import api from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ApprovalHistoryPanel({ sourceType, sourceId }) {
  const { data, isLoading } = useQuery({
    queryKey: ["approval-history", sourceType, sourceId],
    queryFn: async () => (await api.get("/approval-center/history", {
      params: { source_type: sourceType, source_id: sourceId },
    })).data,
    enabled: Boolean(sourceType && sourceId),
  });

  const items = data?.items || [];

  return (
    <Card data-testid={`approval-history-${sourceType}`}>
      <CardHeader>
        <CardTitle className="text-base">Approval history</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="text-sm text-muted-foreground">Loading approval history...</div>
        ) : items.length === 0 ? (
          <div className="text-sm text-muted-foreground">No approval decisions recorded for this source yet.</div>
        ) : items.map((item) => (
          <div key={item.id} className="rounded-md border p-3 text-sm" data-testid={`approval-history-row-${item.id}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="font-medium">{item.label || item.parent_type}</div>
              <Badge variant="outline">{item.action}</Badge>
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {item.actor_display || item.actor_ref || item.actor_type || "Unknown actor"}
              {item.created_at ? ` · ${String(item.created_at).slice(0, 16)}` : ""}
            </div>
            {item.reason && <div className="mt-2 text-xs">Reason: {item.reason}</div>}
            {item.source_url && item.source_url !== "/approval-center" && (
              <Link className="link-underline text-xs" to={item.source_url}>Open source record</Link>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
