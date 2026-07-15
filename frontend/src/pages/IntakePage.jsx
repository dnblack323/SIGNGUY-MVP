import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { relativeTime } from "@/lib/format";
import { Plus, Inbox, Search, AlertTriangle } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { INTAKE_STATUSES, INTAKE_PRIORITIES } from "@/lib/intake";

export default function IntakePage() {
  const navigate = useNavigate();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("intake:write");
  const [status, setStatus] = useState("all");
  const [priority, setPriority] = useState("all");
  const [q, setQ] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["intake", status, priority, q],
    queryFn: async () => (await api.get("/intake", {
      params: {
        status: status === "all" ? undefined : status,
        priority: priority === "all" ? undefined : priority,
        q: q || undefined,
        limit: 100,
      },
    })).data,
  });
  const items = data?.items || [];

  return (
    <div className="space-y-4" data-testid="intake-page">
      <PageHeader
        title="Intake" subtitle="Requests captured before they become a Quote or Order."
        actions={canWrite && (
          <Button data-testid="intake-new-button" onClick={() => navigate("/intake/new")}>
            <Plus className="size-4 mr-1" />New Intake
          </Button>
        )}
      />
      <div className="flex flex-wrap items-center gap-2">
        {["all", ...INTAKE_STATUSES].map((s) => (
          <Button key={s} variant={status === s ? "default" : "outline"} size="sm" onClick={() => setStatus(s)} data-testid={`intake-filter-status-${s}`}>
            <span className="capitalize">{s.replace(/_/g, " ")}</span>
          </Button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-sm">
          <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search # / project / contact / customer" className="pl-9" data-testid="intake-search-input" />
        </div>
        <Select value={priority} onValueChange={setPriority}>
          <SelectTrigger className="w-[160px]" data-testid="intake-filter-priority-select"><SelectValue placeholder="Priority" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All priorities</SelectItem>
            {INTAKE_PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? <TableSkeleton /> : items.length === 0 ? (
        <EmptyState icon={Inbox} title="No intake submissions" description="Create your first intake to get started." action={canWrite && <Button onClick={() => navigate("/intake/new")}>New Intake</Button>} />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="intake-table">
            <TableHeader><TableRow>
              <TableHead>#</TableHead>
              <TableHead>Project</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Due</TableHead>
              <TableHead className="text-right">Items</TableHead>
              <TableHead>Created</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map((i) => (
                <TableRow key={i.id} className="hover:bg-muted/40 cursor-pointer" data-testid={`intake-row-${i.id}`} onClick={() => navigate(`/intake/${i.id}`)}>
                  <TableCell className="mono text-xs">IN-{i.intake_number}</TableCell>
                  <TableCell>
                    <Link className="font-medium hover:underline" to={`/intake/${i.id}`} onClick={(e) => e.stopPropagation()}>
                      {i.project_name || i.contact_name || "Untitled intake"}
                    </Link>
                    {i.missing_information?.length > 0 && (
                      <span className="inline-flex items-center gap-1 ml-2 text-[10px] text-amber-700" data-testid={`intake-missing-info-badge-${i.id}`}>
                        <AlertTriangle className="size-3" /> {i.missing_information.length} missing
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground capitalize">{(i.source_type || "").replace(/_/g, " ")}</TableCell>
                  <TableCell><StatusPill kind="intake" value={i.status} /></TableCell>
                  <TableCell><StatusPill kind="intake_priority" value={i.priority} /></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{i.requested_due_date || "—"}</TableCell>
                  <TableCell className="text-right tabular-nums">{i.items?.length || 0}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{relativeTime(i.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
