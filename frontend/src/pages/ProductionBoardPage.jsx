import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import StatusPill from "@/components/common/StatusPill";
import { AlertTriangle, Calendar, User as UserIcon } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";

const COLUMNS = [
  { key: "draft", label: "Draft" },
  { key: "released", label: "Released" },
  { key: "queued", label: "Queued" },
  { key: "in_progress", label: "In Progress" },
  { key: "blocked", label: "Blocked" },
  { key: "ready", label: "Ready" },
  { key: "completed", label: "Completed" },
];

const REASON_REQUIRED = new Set(["blocked", "cancelled"]);

export default function ProductionBoardPage() {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("work_order:write");

  const [priority, setPriority] = useState("all");
  const [assignee, setAssignee] = useState("all");
  const [drag, setDrag] = useState(null); // {wo, from}
  const [pending, setPending] = useState(null); // {wo, target}
  const [reason, setReason] = useState("");

  const params = {};
  if (priority !== "all") params.priority = priority;
  if (assignee !== "all") params.assigned_user_id = assignee;

  const { data, isLoading } = useQuery({
    queryKey: ["prod-board", params],
    queryFn: async () => (await api.get("/production/board", { params })).data,
  });
  const { data: users } = useQuery({
    queryKey: ["users"],
    queryFn: async () => (await api.get("/users")).data,
    enabled: canWrite,
  });

  const usersById = useMemo(() => {
    const m = {};
    (users || []).forEach((u) => { m[u.id] = u; });
    return m;
  }, [users]);

  const doTransition = useMutation({
    mutationFn: async ({ id, target, reason }) => (await api.post(`/work-orders/${id}/transition`, { target, reason })).data,
    onSuccess: () => { toast.success("Moved"); qc.invalidateQueries({ queryKey: ["prod-board"] }); },
    onError: (e) => toast.error(extractError(e)),
  });

  function onDragStart(wo, from) { setDrag({ wo, from }); }
  function onDragOver(e) { e.preventDefault(); }
  function onDrop(target) {
    if (!drag) return;
    const { wo, from } = drag;
    setDrag(null);
    if (from === target) return;
    if (REASON_REQUIRED.has(target)) {
      setPending({ wo, target });
      setReason("");
      return;
    }
    doTransition.mutate({ id: wo.id, target });
  }

  function confirmReason() {
    if (!pending) return;
    if (!reason.trim()) { toast.error("Reason is required"); return; }
    doTransition.mutate({ id: pending.wo.id, target: pending.target, reason: reason.trim() });
    setPending(null);
    setReason("");
  }

  const columns = data?.columns || {};
  const counts = data?.counts || {};

  return (
    <div className="space-y-4" data-testid="production-board-page">
      <PageHeader
        title="Production Board"
        subtitle="Drag work orders across columns to update production status."
        actions={
          <Button asChild variant="outline" size="sm" data-testid="board-list-view-link">
            <Link to="/work-orders">List view</Link>
          </Button>
        }
      />

      <div className="flex flex-wrap gap-3 items-end">
        <div className="grid gap-1">
          <Label className="text-xs">Priority</Label>
          <Select value={priority} onValueChange={setPriority}>
            <SelectTrigger className="w-40" data-testid="board-priority-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All priorities</SelectItem>
              <SelectItem value="rush">Rush</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="normal">Normal</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {canWrite && (
          <div className="grid gap-1">
            <Label className="text-xs">Assignee</Label>
            <Select value={assignee} onValueChange={setAssignee}>
              <SelectTrigger className="w-56" data-testid="board-assignee-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Anyone</SelectItem>
                {(users || []).map((u) => <SelectItem key={u.id} value={u.id}>{u.full_name || u.email}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading board…</div>
      ) : (
        <div className="grid grid-flow-col auto-cols-[minmax(240px,1fr)] gap-3 overflow-x-auto pb-2" data-testid="board-columns">
          {COLUMNS.map((col) => {
            const list = columns[col.key] || [];
            return (
              <div
                key={col.key}
                className="rounded-lg border bg-muted/30 flex flex-col min-h-[420px]"
                onDragOver={onDragOver}
                onDrop={() => onDrop(col.key)}
                data-testid={`board-col-${col.key}`}
              >
                <div className="px-3 py-2 border-b flex items-center justify-between bg-background/70 rounded-t-lg">
                  <div className="text-sm font-medium">{col.label}</div>
                  <div className="text-xs text-muted-foreground tabular-nums" data-testid={`board-col-count-${col.key}`}>{counts[col.key] ?? list.length}</div>
                </div>
                <div className="p-2 space-y-2 flex-1">
                  {list.length === 0 && <div className="text-xs text-muted-foreground italic px-1 py-4">Drop here</div>}
                  {list.map((wo) => (
                    <BoardCard
                      key={wo.id}
                      wo={wo}
                      canWrite={canWrite}
                      onDragStart={() => onDragStart(wo, col.key)}
                      usersById={usersById}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={!!pending} onOpenChange={(o) => !o && setPending(null)}>
        <DialogContent data-testid="board-reason-dialog">
          <DialogHeader>
            <DialogTitle>Reason required</DialogTitle>
            <DialogDescription>Blocked and cancelled transitions require a reason.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label>Why is this work order moving to <span className="capitalize font-medium">{pending?.target}</span>?</Label>
            <Textarea rows={4} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="board-reason-input" autoFocus />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPending(null)} data-testid="board-reason-cancel">Cancel</Button>
            <Button onClick={confirmReason} disabled={doTransition.isPending} data-testid="board-reason-confirm">Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function BoardCard({ wo, canWrite, onDragStart, usersById }) {
  const assignees = wo.assigned_user_ids || [];
  return (
    <div
      className="rounded-md border bg-card p-2.5 space-y-1.5 shadow-sm hover:shadow transition cursor-grab active:cursor-grabbing"
      draggable={canWrite}
      onDragStart={onDragStart}
      data-testid={`board-card-${wo.id}`}
    >
      <div className="flex items-center justify-between gap-2">
        <Link className="text-sm font-medium hover:underline mono" to={`/work-orders/${wo.id}`}>W-{wo.number}</Link>
        <StatusPill kind="priority" value={wo.priority || "normal"} />
      </div>
      <div className="text-xs text-muted-foreground truncate">
        Order: <Link className="link-underline" to={`/orders/${wo.order_id}`}>{wo.order_id.slice(0, 8)}…</Link>
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {wo.due_date && (
          <span className={`inline-flex items-center gap-1 ${wo.overdue ? "text-rose-700 font-medium" : ""}`}>
            <Calendar className="size-3" />{wo.due_date}
            {wo.overdue && <AlertTriangle className="size-3" />}
          </span>
        )}
        {(wo.items_snapshot || []).length > 0 && (
          <span className="ml-auto">{wo.items_snapshot.length} item{wo.items_snapshot.length === 1 ? "" : "s"}</span>
        )}
      </div>
      {assignees.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap">
          {assignees.slice(0, 3).map((uid) => (
            <span key={uid} className="inline-flex items-center gap-1 text-[10px] bg-muted rounded-full px-1.5 py-0.5">
              <UserIcon className="size-2.5" />
              {(usersById[uid]?.full_name || usersById[uid]?.email || uid).split(" ")[0]}
            </span>
          ))}
          {assignees.length > 3 && <span className="text-[10px] text-muted-foreground">+{assignees.length - 3}</span>}
        </div>
      )}
    </div>
  );
}
