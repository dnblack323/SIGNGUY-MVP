import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { relativeTime } from "@/lib/format";
import { Plus, LayoutPanelTop } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { DECISION_ROOM_STATUSES } from "@/lib/decisionRoom";

export default function DecisionRoomsPage() {
  const navigate = useNavigate();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("decision_room:write");
  const [status, setStatus] = useState("all");

  const { data, isLoading } = useQuery({
    queryKey: ["decision-rooms", status],
    queryFn: async () => (await api.get("/decision-rooms", { params: status === "all" ? {} : { status: [status] } })).data,
  });
  const items = data?.items || [];

  return (
    <div className="space-y-4" data-testid="decision-rooms-page">
      <PageHeader
        title="Decision Rooms" subtitle="Internal authoring for customer comparison options. Staff-only — no customer access yet."
        actions={canWrite && (
          <Button data-testid="decision-room-new-button" onClick={() => navigate("/decision-rooms/new")}>
            <Plus className="size-4 mr-1" />New Decision Room
          </Button>
        )}
      />
      <div className="flex flex-wrap items-center gap-2">
        {["all", ...DECISION_ROOM_STATUSES].map((s) => (
          <Button key={s} variant={status === s ? "default" : "outline"} size="sm" onClick={() => setStatus(s)} data-testid={`decision-room-filter-status-${s}`}>
            <span className="capitalize">{s.replace(/_/g, " ")}</span>
          </Button>
        ))}
      </div>

      {isLoading ? <TableSkeleton /> : items.length === 0 ? (
        <EmptyState icon={LayoutPanelTop} title="No Decision Rooms" description="Create your first Decision Room to present comparison options to a customer." action={canWrite && <Button onClick={() => navigate("/decision-rooms/new")}>New Decision Room</Button>} />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="decision-rooms-table">
            <TableHeader><TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Options</TableHead>
              <TableHead className="text-right">Version</TableHead>
              <TableHead>Updated</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map((r) => (
                <TableRow key={r.id} className="hover:bg-muted/40 cursor-pointer" data-testid={`decision-room-row-${r.id}`} onClick={() => navigate(`/decision-rooms/${r.id}`)}>
                  <TableCell>
                    <Link className="font-medium hover:underline" to={`/decision-rooms/${r.id}`} onClick={(e) => e.stopPropagation()}>
                      {r.title}
                    </Link>
                  </TableCell>
                  <TableCell><StatusPill kind="decision_room" value={r.status} /></TableCell>
                  <TableCell className="text-right tabular-nums">{r.options?.length || 0}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.current_version}{r.published_version ? ` (published: ${r.published_version})` : ""}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{relativeTime(r.updated_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
