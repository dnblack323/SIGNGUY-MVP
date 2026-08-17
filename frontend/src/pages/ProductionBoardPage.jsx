import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Calendar, CheckCircle2, Clock3, FileText, MoreHorizontal, Pause, RefreshCw, Search, UserPlus } from "lucide-react";
import { toast } from "sonner";

import api, { extractError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useWorkspace } from "@/context/WorkspaceContext";
import PageHeader from "@/components/layout/PageHeader";
import StatusPill from "@/components/common/StatusPill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

const VIEW_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "blocked_waiting", label: "Blocked / Waiting" },
  { value: "ready", label: "Ready" },
  { value: "unassigned", label: "Unassigned" },
  { value: "overdue", label: "Overdue" },
  { value: "completed_recently", label: "Completed Recently" },
];

const GROUP_OPTIONS = [
  { value: "status", label: "By Status" },
  { value: "stage", label: "By Stage" },
  { value: "assignee", label: "By Assignee" },
  { value: "due_date", label: "By Due Date" },
];

const SORT_OPTIONS = [
  { value: "due_date", label: "Due Date" },
  { value: "priority", label: "Priority" },
  { value: "oldest_waiting", label: "Oldest Waiting" },
  { value: "oldest_started", label: "Oldest Started" },
  { value: "customer", label: "Customer" },
  { value: "work_order_number", label: "Work Order" },
  { value: "last_updated", label: "Last Updated" },
];

const STAGE_STATUS_OPTIONS = ["not_started", "in_progress", "waiting", "blocked", "completed", "skipped", "manual_no_workflow"];
const MANAGER_ACTIONS = new Set(["assign", "unassign", "skip", "reopen", "update_due_date"]);

function titleize(value) {
  return String(value || "unknown").replace(/_/g, " ");
}

function timerSessionIdFor(row, action) {
  if (["timer_correct", "timer_void"].includes(action)) {
    const completed = (row.timer_history || []).find((entry) => entry.status === "completed");
    return completed?.id || null;
  }
  return row.active_timer_session_id || row.current_timer?.id || row.active_timer?.id || null;
}

function firstName(value) {
  return String(value || "Unassigned").split(" ")[0];
}

function formatDuration(seconds) {
  const total = Math.max(0, Number(seconds || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.round((total % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function formatDateTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value).slice(0, 16);
  return parsed.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function ProductionBoardPage() {
  const qc = useQueryClient();
  const { user, hasPerm } = useAuth();
  const canWrite = hasPerm("work_order:write");
  const canReadPricing = hasPerm("pricing:read");
  const canWritePricing = hasPerm("pricing:write");
  const isManager = ["owner", "admin", "production_manager"].includes(user?.role);
  const [view, setView] = useState("active");
  const [groupBy, setGroupBy] = useState("status");
  const [sort, setSort] = useState("due_date");
  const [priority, setPriority] = useState("all");
  const [stageStatus, setStageStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(new Set());
  const [dialog, setDialog] = useState(null);
  const [bulkDialog, setBulkDialog] = useState(null);

  const params = useMemo(() => {
    const next = { view, group_by: groupBy, sort, limit: 100 };
    if (priority !== "all") next.priority = priority;
    if (stageStatus !== "all") next.stage_status = stageStatus;
    if (search.trim()) next.search = search.trim();
    return next;
  }, [view, groupBy, sort, priority, stageStatus, search]);

  const boardQuery = useQuery({
    queryKey: ["prod-board", params],
    queryFn: async () => (await api.get("/production/board", { params })).data,
  });

  const employeesQuery = useQuery({
    queryKey: ["employees", "active"],
    queryFn: async () => (await api.get("/employees", { params: { status: "active" } })).data,
    enabled: isManager,
  });

  const feedbackQuery = useQuery({
    queryKey: ["production-pricing-feedback"],
    queryFn: async () => (await api.get("/production/pricing-feedback")).data,
    enabled: canReadPricing,
  });

  const employees = useMemo(() => employeesQuery.data?.items || [], [employeesQuery.data]);
  const board = boardQuery.data || {};
  const rows = useMemo(() => boardQuery.data?.items || [], [boardQuery.data]);
  const columns = board.columns || {};
  const summary = board.summary_counts || {};

  const selectedRows = useMemo(() => rows.filter((row) => row.current_stage_id && selected.has(row.current_stage_id)), [rows, selected]);

  const stageAction = useMutation({
    mutationFn: async ({ row, action, payload }) => runStageAction(row, action, payload),
    onSuccess: () => {
      toast.success("Stage updated");
      setDialog(null);
      qc.invalidateQueries({ queryKey: ["prod-board"] });
      qc.invalidateQueries({ queryKey: ["production-pricing-feedback"] });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const bulkAction = useMutation({
    mutationFn: async ({ action, payload }) => runBulkAction(action, payload),
    onSuccess: (data) => {
      toast.success(`${data.success_count || 0} updated, ${data.failure_count || 0} failed`);
      setBulkDialog(null);
      setSelected(new Set());
      qc.invalidateQueries({ queryKey: ["prod-board"] });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  function toggleSelected(stageId, checked) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(stageId);
      else next.delete(stageId);
      return next;
    });
  }

  function openAction(row, action) {
    if (!row.current_stage_id) return;
    if (["start", "resume", "unassign", "timer_start", "timer_resume", "pricing_feedback"].includes(action)) {
      stageAction.mutate({ row, action, payload: {} });
      return;
    }
    setDialog({ row, action, reason: "", note: "", due_at: row.due_at || "", employee_id: row.assigned_employee_id || "" });
  }

  function submitDialog() {
    if (!dialog) return;
    const payload = {
      reason: dialog.reason,
      completion_note: dialog.note,
      note: dialog.note,
      due_at: dialog.due_at || null,
      employee_id: dialog.employee_id,
      override_reason: dialog.reason,
      session_id: timerSessionIdFor(dialog.row, dialog.action),
      corrected_elapsed_seconds: dialog.corrected_elapsed_seconds === "" ? null : Number(dialog.corrected_elapsed_seconds),
      confirm: dialog.confirm === true,
    };
    if (dialog.action === "assign" && !payload.employee_id) {
      toast.error("Select an employee");
      return;
    }
    if (["block", "skip", "reopen", "timer_pause", "timer_correct", "timer_void"].includes(dialog.action) && !payload.reason.trim()) {
      toast.error("Reason is required");
      return;
    }
    if (dialog.action === "timer_correct" && (!Number.isFinite(payload.corrected_elapsed_seconds) || payload.corrected_elapsed_seconds < 0)) {
      toast.error("Enter corrected working seconds");
      return;
    }
    if (dialog.action === "timer_void" && !payload.confirm) {
      toast.error("Confirm that this time entry should be voided");
      return;
    }
    if (dialog.action === "add_note" && !payload.note.trim()) {
      toast.error("Note is required");
      return;
    }
    stageAction.mutate({ row: dialog.row, action: dialog.action, payload });
  }

  function submitBulk() {
    if (!bulkDialog || selectedRows.length === 0) return;
    const stage_ids = selectedRows.map((row) => row.current_stage_id);
    const payload = { stage_ids, ...bulkDialog };
    if (bulkDialog.action === "assign" && !bulkDialog.employee_id) {
      toast.error("Select an employee");
      return;
    }
    if (bulkDialog.action === "note" && !bulkDialog.note?.trim()) {
      toast.error("Note is required");
      return;
    }
    bulkAction.mutate({ action: bulkDialog.action, payload });
  }

  return (
    <div className="space-y-4" data-testid="production-board-page">
      <PageHeader
        title="Production Board"
        subtitle="Live Work Order stage queue for active production."
        actions={<Button asChild variant="outline" size="sm"><Link to="/work-orders">Work Orders</Link></Button>}
      />

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-9" data-testid="board-summary-counts">
        <Summary label="Active" value={summary.active_production} icon={Clock3} />
        <Summary label="Ready" value={summary.ready_to_start} icon={CheckCircle2} />
        <Summary label="In Progress" value={summary.in_progress} icon={RefreshCw} />
        <Summary label="Blocked" value={summary.blocked} icon={AlertTriangle} tone="text-orange-700" />
        <Summary label="Waiting" value={summary.waiting} icon={Clock3} />
        <Summary label="Overdue" value={summary.overdue} icon={Calendar} tone="text-rose-700" />
        <Summary label="Unassigned" value={summary.unassigned} icon={UserPlus} />
        <Summary label="Active Timers" value={summary.active_timers} icon={Clock3} tone="text-blue-700" />
        <Summary label="Paused Timers" value={summary.paused_timers} icon={Pause} tone="text-amber-700" />
        <Summary label="Recent Done" value={summary.completed_recently} icon={CheckCircle2} />
      </div>

      <div className="flex flex-wrap items-end gap-2 rounded-md border bg-card p-3" data-testid="board-filters">
        <div className="grid gap-1">
          <Label className="text-xs">View</Label>
          <Select value={view} onValueChange={setView}>
            <SelectTrigger className="w-44" data-testid="board-view-select"><SelectValue /></SelectTrigger>
            <SelectContent>{VIEW_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid gap-1">
          <Label className="text-xs">Group</Label>
          <Select value={groupBy} onValueChange={setGroupBy}>
            <SelectTrigger className="w-40" data-testid="board-group-select"><SelectValue /></SelectTrigger>
            <SelectContent>{GROUP_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid gap-1">
          <Label className="text-xs">Sort</Label>
          <Select value={sort} onValueChange={setSort}>
            <SelectTrigger className="w-40" data-testid="board-sort-select"><SelectValue /></SelectTrigger>
            <SelectContent>{SORT_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid gap-1">
          <Label className="text-xs">Priority</Label>
          <Select value={priority} onValueChange={setPriority}>
            <SelectTrigger className="w-36" data-testid="board-priority-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="rush">Rush</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="normal">Normal</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1">
          <Label className="text-xs">Stage Status</Label>
          <Select value={stageStatus} onValueChange={setStageStatus}>
            <SelectTrigger className="w-44" data-testid="board-status-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {STAGE_STATUS_OPTIONS.map((s) => <SelectItem key={s} value={s}>{titleize(s)}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="grid min-w-[240px] flex-1 gap-1">
          <Label className="text-xs">Search</Label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2 top-2.5 size-4 text-muted-foreground" />
            <Input className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="WO, order, customer, item, employee" data-testid="board-search-input" />
          </div>
        </div>
      </div>

      {isManager && selectedRows.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2" data-testid="board-bulk-actions">
          <span className="text-sm font-medium">{selectedRows.length} selected</span>
          <Button size="sm" variant="outline" onClick={() => setBulkDialog({ action: "assign", employee_id: "", override_reason: "" })}>Assign</Button>
          <Button size="sm" variant="outline" onClick={() => setBulkDialog({ action: "due_date", due_at: "" })}>Due Date</Button>
          <Button size="sm" variant="outline" onClick={() => setBulkDialog({ action: "wait", reason: "" })}>Waiting</Button>
          <Button size="sm" variant="outline" onClick={() => setBulkDialog({ action: "note", note: "" })}>Note</Button>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>Clear</Button>
        </div>
      )}

      {boardQuery.isLoading ? (
        <div className="text-sm text-muted-foreground" data-testid="board-loading">Loading board...</div>
      ) : boardQuery.isError ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" data-testid="board-error">Could not load the production board.</div>
      ) : rows.length === 0 ? (
        <div className="rounded-md border bg-muted/30 p-6 text-sm text-muted-foreground" data-testid="board-empty">No production stages match this view.</div>
      ) : (
        <div className="space-y-4" data-testid="board-columns">
          {Object.entries(columns).map(([key, list]) => (
            <section key={key} className="space-y-2" data-testid={`board-col-${key}`}>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold capitalize">{titleize(key)}</h2>
                <Badge variant="outline" data-testid={`board-col-count-${key}`}>{list.length}</Badge>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8"></TableHead>
                    <TableHead>Work</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Assignee</TableHead>
                    <TableHead>Due</TableHead>
                    <TableHead>Progress</TableHead>
                    <TableHead className="w-12"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {list.map((row) => (
                    <BoardRow
                      key={row.id}
                      row={row}
                      canWrite={canWrite}
                      isManager={isManager}
                      selected={row.current_stage_id ? selected.has(row.current_stage_id) : false}
                      onSelect={toggleSelected}
                      onAction={openAction}
                    />
                  ))}
                </TableBody>
              </Table>
            </section>
          ))}
        </div>
      )}

      <ActionDialog
        dialog={dialog}
        employees={employees}
        busy={stageAction.isPending}
        onChange={setDialog}
        onClose={() => setDialog(null)}
        onSubmit={submitDialog}
      />
      {canReadPricing && (
        <PricingFeedbackPanel
          feedback={feedbackQuery.data?.items || []}
          loading={feedbackQuery.isLoading}
          canWrite={canWritePricing && isManager}
          onUpdated={() => {
            qc.invalidateQueries({ queryKey: ["production-pricing-feedback"] });
            qc.invalidateQueries({ queryKey: ["prod-board"] });
          }}
        />
      )}
      <BulkDialog
        dialog={bulkDialog}
        employees={employees}
        busy={bulkAction.isPending}
        count={selectedRows.length}
        onChange={setBulkDialog}
        onClose={() => setBulkDialog(null)}
        onSubmit={submitBulk}
      />
    </div>
  );
}

async function runStageAction(row, action, payload) {
  const id = row.current_stage_id;
  if (action === "assign") return (await api.post(`/production-stages/${id}/assign`, { employee_id: payload.employee_id, override_reason: payload.override_reason || null })).data;
  if (action === "unassign") return (await api.post(`/production-stages/${id}/unassign`)).data;
  if (action === "start") return (await api.post(`/production-stages/${id}/start`)).data;
  if (action === "timer_start") return (await api.post(`/production-stages/${id}/timer/start`, { notes: payload.note || null })).data;
  if (action === "timer_pause") return (await api.post(`/production-stages/${id}/timer/pause`, { session_id: payload.session_id || timerSessionIdFor(row, action), reason: payload.reason })).data;
  if (action === "timer_resume") return (await api.post(`/production-stages/${id}/timer/resume`, { session_id: payload.session_id || timerSessionIdFor(row, action) })).data;
  if (action === "timer_stop") return (await api.post(`/production-stages/${id}/timer/stop`, { session_id: payload.session_id || timerSessionIdFor(row, action), notes: payload.note || null, interruption_reason: payload.reason || null })).data;
  if (action === "timer_correct") return (await api.post(`/production-stages/${id}/timer/correct`, { session_id: payload.session_id, corrected_elapsed_seconds: payload.corrected_elapsed_seconds, reason: payload.reason })).data;
  if (action === "timer_void") return (await api.post(`/production-stages/${id}/timer/void`, { session_id: payload.session_id, reason: payload.reason, confirm: payload.confirm })).data;
  if (action === "pricing_feedback") return (await api.post(`/production-stages/${id}/pricing-feedback`)).data;
  if (action === "wait") return (await api.post(`/production-stages/${id}/wait`, { reason: payload.reason || null })).data;
  if (action === "block") return (await api.post(`/production-stages/${id}/block`, { reason: payload.reason })).data;
  if (action === "resume") return (await api.post(`/production-stages/${id}/resume`)).data;
  if (action === "complete") return (await api.post(`/production-stages/${id}/complete`, { completion_note: payload.completion_note || null })).data;
  if (action === "skip") return (await api.post(`/production-stages/${id}/skip`, { reason: payload.reason || null })).data;
  if (action === "reopen") return (await api.post(`/production-stages/${id}/reopen`, { reason: payload.reason })).data;
  if (action === "update_due_date") return (await api.patch(`/production-stages/${id}/due-date`, { due_at: payload.due_at || null })).data;
  if (action === "add_note") return (await api.post(`/production-stages/${id}/notes`, { note: payload.note })).data;
  throw new Error("Unsupported action");
}

async function runBulkAction(action, payload) {
  if (action === "assign") return (await api.post("/production/board/bulk-assign", payload)).data;
  if (action === "due_date") return (await api.post("/production/board/bulk-due-date", payload)).data;
  if (action === "wait") return (await api.post("/production/board/bulk-wait", payload)).data;
  if (action === "note") return (await api.post("/production/board/bulk-note", payload)).data;
  return (await api.post("/production/board/bulk-action", { action, stage_ids: payload.stage_ids })).data;
}

function Summary({ label, value = 0, icon: Icon, tone = "text-muted-foreground" }) {
  return (
    <Card className="rounded-md shadow-none">
      <CardContent className="flex items-center gap-2 p-3">
        <Icon className={`size-4 ${tone}`} />
        <div>
          <div className="text-lg font-semibold tabular-nums">{value || 0}</div>
          <div className="text-[11px] text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function BoardRow({ row, canWrite, isManager, selected, onSelect, onAction }) {
  const { openWorkspaceTarget } = useWorkspace();
  const canSelect = isManager && row.current_stage_id;
  const allowed = row.allowed_actions || [];
  const currentTimer = row.current_timer || row.active_timer || null;
  const timerStatus = row.timer_status || currentTimer?.status;
  const openWorkOrderWorkspace = () => {
    if (!row.work_order_id) return;
    openWorkspaceTarget({
      workspace_type: "work_order",
      record_id: row.work_order_id,
      label: row.work_order_number ? `Work Order ${row.work_order_number}` : "Work Order",
      pathname: `/work-orders/${row.work_order_id}`,
      query_params: {},
      view_state: { selected_tab: "summary" },
    });
  };
  return (
    <TableRow data-testid={`board-card-${row.work_order_id}-${row.order_item_id || "manual"}`}>
      <TableCell>
        {canSelect && <Checkbox checked={selected} onCheckedChange={(checked) => onSelect(row.current_stage_id, checked === true)} aria-label="Select stage" />}
      </TableCell>
      <TableCell>
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link className="font-medium hover:underline" to={`/work-orders/${row.work_order_id}`}>W-{row.work_order_number}</Link>
            <StatusPill kind="priority" value={row.priority || "normal"} />
            {row.overdue && <Badge variant="destructive" className="gap-1"><AlertTriangle className="size-3" />Overdue</Badge>}
          </div>
          <div className="text-xs text-muted-foreground">
            <Link className="hover:underline" to={`/orders/${row.order_id}`}>Order {row.order_number || String(row.order_id || "").slice(0, 8)}</Link>
            {row.customer_id && <> · <Link className="hover:underline" to={`/customers/${row.customer_id}`}>{row.customer_name || "Customer"}</Link></>}
          </div>
          <div className="max-w-[340px] truncate text-xs">{row.order_item_name}</div>
        </div>
      </TableCell>
      <TableCell>
        <div className="space-y-1">
          <div className="font-medium">{row.current_stage_name || "Manual / no workflow"}</div>
          <div className="flex flex-wrap gap-1">
            <StatusPill kind="production" value={row.current_stage_status} />
            {row.proof_or_approval_gate_state && <Badge variant="outline">{titleize(row.proof_or_approval_gate_state)}</Badge>}
          </div>
          {row.blocker_reason && <div className="max-w-[260px] truncate text-xs text-orange-700">{row.blocker_reason}</div>}
          {row.eligibility_warning && <div className="max-w-[260px] truncate text-xs text-amber-700">{row.eligibility_warning}</div>}
          {currentTimer && (
            <div className={`max-w-[320px] truncate text-xs ${timerStatus === "paused" ? "text-amber-700" : "text-blue-700"}`} data-testid={`board-active-timer-${row.current_stage_id}`}>
              {timerStatus === "paused" ? "Paused" : "Timing"}: {row.active_timer_employee_name || currentTimer.employee_name || "Employee"} since {formatDateTime(row.active_timer_started_at || currentTimer.started_at)}
              {currentTimer.effective_elapsed_seconds ? <> / working {formatDuration(currentTimer.effective_elapsed_seconds)}</> : null}
              {currentTimer.paused_duration_seconds ? <> / paused {formatDuration(currentTimer.paused_duration_seconds)}</> : null}
            </div>
          )}
          {row.timer_history?.length > 0 && (
            <div className="max-w-[320px] truncate text-xs text-muted-foreground">
              Last time entry: {titleize(row.timer_history[0].status)}
              {row.timer_history[0].corrected_elapsed_seconds != null ? " / corrected" : ""}
              {row.timer_history[0].status === "voided" ? " / voided" : ""}
            </div>
          )}
          {(row.actual_duration_seconds || row.planned_duration_minutes) && (
            <div className="text-xs text-muted-foreground">
              Actual {formatDuration(row.actual_duration_seconds)}
              {row.planned_duration_minutes ? <> / planned {row.planned_duration_minutes}m</> : null}
              {row.labor_variance_minutes ? <> / variance {row.labor_variance_minutes}m</> : null}
            </div>
          )}
        </div>
      </TableCell>
      <TableCell className="text-sm">
        {row.assigned_employee_name ? firstName(row.assigned_employee_name) : <span className="text-muted-foreground">Unassigned</span>}
        {row.assigned_role && <div className="text-xs text-muted-foreground">{row.assigned_role}</div>}
      </TableCell>
      <TableCell className="text-sm">
        {row.due_at ? <span className={row.overdue ? "font-medium text-rose-700" : ""}>{String(row.due_at).slice(0, 10)}</span> : <span className="text-muted-foreground">No due date</span>}
        {row.waiting_since && <div className="text-xs text-muted-foreground">Waiting since {String(row.waiting_since).slice(0, 10)}</div>}
      </TableCell>
      <TableCell>
        <div className="min-w-24">
          <div className="mb-1 flex justify-between text-xs">
            <span>{row.completed_stage_count} of {row.total_stage_count}</span>
            <span>{row.progress_percent}%</span>
          </div>
          <div className="h-1.5 rounded bg-muted">
            <div className="h-1.5 rounded bg-emerald-600" style={{ width: `${Math.min(row.progress_percent || 0, 100)}%` }} />
          </div>
        </div>
      </TableCell>
      <TableCell>
        {canWrite && row.current_stage_id && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Stage actions"><MoreHorizontal className="size-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {allowed.includes("start") && <DropdownMenuItem onClick={() => onAction(row, "start")}>Start</DropdownMenuItem>}
              {allowed.includes("timer_start") && <DropdownMenuItem onClick={() => onAction(row, "timer_start")}>Check Out & Start</DropdownMenuItem>}
              {allowed.includes("timer_pause") && <DropdownMenuItem onClick={() => onAction(row, "timer_pause")}>Pause Timer</DropdownMenuItem>}
              {allowed.includes("timer_resume") && <DropdownMenuItem onClick={() => onAction(row, "timer_resume")}>Resume Timer</DropdownMenuItem>}
              {allowed.includes("timer_stop") && <DropdownMenuItem onClick={() => onAction(row, "timer_stop")}>Check In</DropdownMenuItem>}
              {allowed.includes("wait") && <DropdownMenuItem onClick={() => onAction(row, "wait")}>Mark Waiting</DropdownMenuItem>}
              {allowed.includes("block") && <DropdownMenuItem onClick={() => onAction(row, "block")}>Block</DropdownMenuItem>}
              {allowed.includes("resume") && <DropdownMenuItem onClick={() => onAction(row, "resume")}>Resume</DropdownMenuItem>}
              {allowed.includes("complete") && <DropdownMenuItem onClick={() => onAction(row, "complete")}>Complete</DropdownMenuItem>}
              <DropdownMenuSeparator />
              {allowed.includes("add_note") && <DropdownMenuItem onClick={() => onAction(row, "add_note")}>Add Note</DropdownMenuItem>}
              {row.work_order_id && <DropdownMenuItem onClick={openWorkOrderWorkspace}>Open in New Workspace</DropdownMenuItem>}
              {isManager && allowed.filter((a) => MANAGER_ACTIONS.has(a)).map((action) => (
                <DropdownMenuItem key={action} onClick={() => onAction(row, action)}>{titleize(action)}</DropdownMenuItem>
              ))}
              {isManager && allowed.includes("timer_correct") && <DropdownMenuItem onClick={() => onAction(row, "timer_correct")}>Correct Time</DropdownMenuItem>}
              {isManager && allowed.includes("timer_void") && <DropdownMenuItem onClick={() => onAction(row, "timer_void")}>Void Time</DropdownMenuItem>}
              {isManager && allowed.includes("pricing_feedback") && <DropdownMenuItem onClick={() => onAction(row, "pricing_feedback")}>Create Pricing Feedback</DropdownMenuItem>}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </TableCell>
    </TableRow>
  );
}

function ActionDialog({ dialog, employees, busy, onChange, onClose, onSubmit }) {
  if (!dialog) return null;
  const action = dialog.action;
  return (
    <Dialog open={!!dialog} onOpenChange={(open) => !open && onClose()}>
      <DialogContent data-testid="board-action-dialog">
        <DialogHeader>
          <DialogTitle>{titleize(action)}</DialogTitle>
          <DialogDescription>{dialog.row.current_stage_name} on W-{dialog.row.work_order_number}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {action === "assign" && (
            <div className="grid gap-1.5">
              <Label>Employee</Label>
              <Select value={dialog.employee_id || ""} onValueChange={(employee_id) => onChange({ ...dialog, employee_id })}>
                <SelectTrigger><SelectValue placeholder="Select employee" /></SelectTrigger>
                <SelectContent>{employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          )}
          {action === "update_due_date" && (
            <div className="grid gap-1.5">
              <Label>Due date</Label>
              <Input type="date" value={dialog.due_at || ""} onChange={(e) => onChange({ ...dialog, due_at: e.target.value })} />
            </div>
          )}
          {action === "timer_correct" && (
            <div className="grid gap-1.5">
              <Label>Corrected working seconds</Label>
              <Input
                type="number"
                min="0"
                value={dialog.corrected_elapsed_seconds ?? ""}
                onChange={(e) => onChange({ ...dialog, corrected_elapsed_seconds: e.target.value })}
                data-testid="board-corrected-seconds-input"
              />
            </div>
          )}
          {["block", "wait", "skip", "reopen", "assign", "timer_stop", "timer_pause", "timer_correct", "timer_void"].includes(action) && (
            <div className="grid gap-1.5">
              <Label>{["timer_pause", "timer_correct", "timer_void", "block", "skip", "reopen"].includes(action) ? "Reason" : action === "timer_stop" ? "Interruption reason or note" : "Reason or override note"}</Label>
              <Textarea rows={3} value={dialog.reason || ""} onChange={(e) => onChange({ ...dialog, reason: e.target.value })} data-testid="board-reason-input" />
            </div>
          )}
          {action === "timer_void" && (
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={dialog.confirm === true} onCheckedChange={(checked) => onChange({ ...dialog, confirm: checked === true })} />
              Confirm this time entry should be excluded from totals.
            </label>
          )}
          {["complete", "add_note", "timer_stop"].includes(action) && (
            <div className="grid gap-1.5">
              <Label>{action === "complete" ? "Completion note" : action === "timer_stop" ? "Timer note" : "Production note"}</Label>
              <Textarea rows={3} value={dialog.note || ""} onChange={(e) => onChange({ ...dialog, note: e.target.value })} data-testid="board-note-input" />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={onSubmit} disabled={busy}>{busy ? "Working..." : "Apply"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PricingFeedbackPanel({ feedback, loading, canWrite, onUpdated }) {
  const decision = useMutation({
    mutationFn: async ({ item, action, payload }) => {
      return (await api.post(`/production/pricing-feedback/${item.id}/${action}`, payload)).data;
    },
    onSuccess: () => {
      toast.success("Pricing feedback updated");
      onUpdated?.();
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const items = feedback || [];
  return (
    <Card className="rounded-md shadow-none" data-testid="pricing-feedback-panel">
      <CardContent className="space-y-3 p-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-sm font-semibold">Pricing Foundation Feedback</div>
            <div className="text-xs text-muted-foreground">Manager review of production timing variance suggestions.</div>
          </div>
          <Badge variant="outline">{items.length}</Badge>
        </div>
        {loading ? (
          <div className="text-xs text-muted-foreground">Loading pricing feedback...</div>
        ) : items.length === 0 ? (
          <div className="text-xs text-muted-foreground">No active pricing feedback.</div>
        ) : (
          <div className="grid gap-2 lg:grid-cols-2">
            {items.slice(0, 6).map((item) => (
              <div key={item.id} className="rounded-md border p-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium">{item.stage_name || item.production_category || "Production stage"}</div>
                  <Badge variant={item.status === "pending" ? "default" : "outline"}>{item.status}</Badge>
                </div>
                <div className="mt-1 text-muted-foreground">
                  Planned {formatDuration(item.planned_seconds)} / Actual {formatDuration(item.effective_actual_seconds)} / Variance {formatDuration(Math.abs(item.variance_seconds))}
                </div>
                <div className="mt-1">
                  {item.mapped ? (
                    <>
                      <span className="text-muted-foreground">{item.target_path}</span>
                      <div>Existing {Number(item.existing_value ?? 0).toFixed(4)} / Suggested {Number(item.suggested_value ?? 0).toFixed(4)}</div>
                    </>
                  ) : (
                    <span className="text-amber-700">Unmapped: {item.explanation}</span>
                  )}
                </div>
                {canWrite && ["pending", "unmapped"].includes(item.status) && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {item.mapped && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={decision.isPending}
                        onClick={() => decision.mutate({ item, action: "approve", payload: { approved_value: item.suggested_value, reason: "Manager approved production variance feedback" } })}
                      >
                        Approve
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={decision.isPending}
                      onClick={() => decision.mutate({ item, action: "reject", payload: { reason: "Manager rejected production variance feedback" } })}
                    >
                      Reject
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function BulkDialog({ dialog, employees, busy, count, onChange, onClose, onSubmit }) {
  if (!dialog) return null;
  return (
    <Dialog open={!!dialog} onOpenChange={(open) => !open && onClose()}>
      <DialogContent data-testid="board-bulk-dialog">
        <DialogHeader>
          <DialogTitle>Bulk {titleize(dialog.action)}</DialogTitle>
          <DialogDescription>{count} selected stage{count === 1 ? "" : "s"}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {dialog.action === "assign" && (
            <div className="grid gap-1.5">
              <Label>Employee</Label>
              <Select value={dialog.employee_id || ""} onValueChange={(employee_id) => onChange({ ...dialog, employee_id })}>
                <SelectTrigger><SelectValue placeholder="Select employee" /></SelectTrigger>
                <SelectContent>{employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          )}
          {dialog.action === "due_date" && (
            <div className="grid gap-1.5">
              <Label>Due date</Label>
              <Input type="date" value={dialog.due_at || ""} onChange={(e) => onChange({ ...dialog, due_at: e.target.value })} />
            </div>
          )}
          {dialog.action === "wait" && (
            <div className="grid gap-1.5">
              <Label>Waiting reason</Label>
              <Textarea rows={3} value={dialog.reason || ""} onChange={(e) => onChange({ ...dialog, reason: e.target.value })} />
            </div>
          )}
          {dialog.action === "note" && (
            <div className="grid gap-1.5">
              <Label>Production note</Label>
              <Textarea rows={3} value={dialog.note || ""} onChange={(e) => onChange({ ...dialog, note: e.target.value })} />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={onSubmit} disabled={busy || count === 0}>{busy ? "Working..." : "Apply"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
