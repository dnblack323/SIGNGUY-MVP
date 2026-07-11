import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { Wrench, LayoutGrid } from "lucide-react";
import { relativeTime } from "@/lib/format";
import { useState } from "react";

const STATUSES = ["all", "draft", "released", "queued", "in_progress", "blocked", "ready", "completed", "cancelled"];

export default function WorkOrdersPage() {
  const [status, setStatus] = useState("all");
  const [currentOnly, setCurrentOnly] = useState(true);

  const { data, isLoading } = useQuery({
    queryKey: ["work-orders", status, currentOnly],
    queryFn: async () => (await api.get("/work-orders", {
      params: {
        production_status: status === "all" ? undefined : status,
        current_only: currentOnly || undefined,
        limit: 100,
      },
    })).data,
  });
  const items = data?.items || [];

  return (
    <div className="space-y-4" data-testid="work-orders-page">
      <PageHeader
        title="Work Orders"
        subtitle="Production floor list."
        actions={
          <Button asChild variant="outline" size="sm" data-testid="wo-open-board-button">
            <Link to="/work-orders/board"><LayoutGrid className="size-4 mr-1" />Production Board</Link>
          </Button>
        }
      />
      <div className="flex flex-wrap gap-2 items-center">
        {STATUSES.map((s) => (
          <Button key={s} variant={status === s ? "default" : "outline"} size="sm" onClick={() => setStatus(s)} data-testid={`wo-filter-${s}`}>
            <span className="capitalize">{s.replace(/_/g, " ")}</span>
          </Button>
        ))}
        <label className="ml-2 inline-flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
          <Checkbox checked={currentOnly} onCheckedChange={(v) => setCurrentOnly(!!v)} data-testid="wo-current-only-toggle" />
          Current version only
        </label>
      </div>

      {isLoading ? <TableSkeleton /> : items.length === 0 ? (
        <EmptyState icon={Wrench} title="No work orders yet" description="Generate a work order from an Order." />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="work-orders-table">
            <TableHeader><TableRow>
              <TableHead>#</TableHead>
              <TableHead>Order</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Due</TableHead>
              <TableHead>Items</TableHead>
              <TableHead>Created</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map((w) => (
                <TableRow key={w.id} className="hover:bg-muted/40" data-testid={`work-order-row-${w.id}`}>
                  <TableCell className="mono text-xs">
                    <Link className="hover:underline" to={`/work-orders/${w.id}`}>W-{w.number}</Link>
                    {w.version > 1 && <span className="ml-1 text-[10px] rounded bg-muted px-1">v{w.version}</span>}
                    {w.current_version === false && <span className="ml-1 text-[10px] text-rose-700">superseded</span>}
                  </TableCell>
                  <TableCell><Link className="font-medium hover:underline" to={`/orders/${w.order_id}`}>O-{String(w.order_id).slice(0, 8)}…</Link></TableCell>
                  <TableCell><StatusPill kind="production" value={w.production_status} /></TableCell>
                  <TableCell><StatusPill kind="priority" value={w.priority || "normal"} /></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{w.due_date || "—"}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{(w.items_snapshot || []).length}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{relativeTime(w.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
