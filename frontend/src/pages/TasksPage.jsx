import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import PageHeader from "@/components/layout/PageHeader";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Archive, CheckCircle2, CirclePlay, MessageSquare, Plus, RotateCcw, Search, TimerReset } from "lucide-react";
import { toast } from "sonner";

const STATUSES = ["not_started", "in_progress", "waiting", "blocked", "completed", "canceled"];
const PRIORITIES = ["low", "normal", "high", "rush"];

function label(value) {
  return String(value || "").replace(/_/g, " ");
}

function statusClass(status) {
  return {
    not_started: "bg-slate-100 text-slate-700",
    in_progress: "bg-sky-100 text-sky-800",
    waiting: "bg-amber-100 text-amber-800",
    blocked: "bg-rose-100 text-rose-800",
    completed: "bg-emerald-100 text-emerald-800",
    canceled: "bg-zinc-100 text-zinc-700",
  }[status] || "bg-slate-100 text-slate-700";
}

function cleanPayload(form) {
  const out = {
    ...form,
    employee_visible: form.employee_visible === "yes",
    internal_only: form.employee_visible !== "yes" && form.visibility === "internal",
  };
  for (const key of Object.keys(out)) {
    if (out[key] === "" || out[key] === "none") delete out[key];
  }
  return out;
}

function TaskDialog({ task, employees, onDone, trigger }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: "",
    description: "",
    priority: "normal",
    task_type: "general",
    due_at: "",
    assigned_employee_id: "none",
    customer_id: "",
    order_id: "",
    order_item_id: "",
    work_order_id: "",
    production_stage_id: "",
    visibility: "staff",
    employee_visible: "no",
  });

  useEffect(() => {
    if (!open) return;
    setForm({
      title: task?.title || "",
      description: task?.description || "",
      priority: task?.priority || "normal",
      task_type: task?.task_type || "general",
      due_at: task?.due_at || "",
      assigned_employee_id: task?.assigned_employee_id || "none",
      customer_id: task?.customer_id || "",
      order_id: task?.order_id || "",
      order_item_id: task?.order_item_id || "",
      work_order_id: task?.work_order_id || "",
      production_stage_id: task?.production_stage_id || "",
      visibility: task?.visibility || "staff",
      employee_visible: task?.employee_visible ? "yes" : "no",
    });
  }, [open, task]);

  const set = (key) => (valueOrEvent) => {
    const value = valueOrEvent?.target ? valueOrEvent.target.value : valueOrEvent;
    setForm((f) => ({ ...f, [key]: value }));
  };

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = cleanPayload(form);
      if (task) await api.patch(`/tasks/${task.id}`, payload);
      else await api.post("/tasks", payload);
      toast.success(task ? "Task updated" : "Task created");
      setOpen(false);
      onDone?.();
    } catch (err) {
      toast.error(extractError(err, "Task save failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-[760px] max-h-[90vh] overflow-y-auto" data-testid="task-dialog">
        <DialogHeader><DialogTitle>{task ? "Edit task" : "New task"}</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="grid gap-4">
          <div className="grid gap-2 md:grid-cols-2">
            <div className="grid gap-1.5 md:col-span-2"><Label>Title</Label><Input required value={form.title} onChange={set("title")} data-testid="task-title-input" /></div>
            <div className="grid gap-1.5 md:col-span-2"><Label>Description</Label><Textarea rows={3} value={form.description} onChange={set("description")} data-testid="task-description-input" /></div>
            <div className="grid gap-1.5"><Label>Priority</Label><Select value={form.priority} onValueChange={set("priority")}><SelectTrigger data-testid="task-priority-select"><SelectValue /></SelectTrigger><SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{label(p)}</SelectItem>)}</SelectContent></Select></div>
            <div className="grid gap-1.5"><Label>Type</Label><Input value={form.task_type} onChange={set("task_type")} data-testid="task-type-input" /></div>
            <div className="grid gap-1.5"><Label>Due</Label><Input value={form.due_at} onChange={set("due_at")} placeholder="YYYY-MM-DD or ISO time" data-testid="task-due-input" /></div>
            <div className="grid gap-1.5"><Label>Assigned employee</Label><Select value={form.assigned_employee_id} onValueChange={set("assigned_employee_id")}><SelectTrigger data-testid="task-employee-select"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="none">Unassigned</SelectItem>{employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent></Select></div>
            <div className="grid gap-1.5"><Label>Customer ID</Label><Input value={form.customer_id} onChange={set("customer_id")} /></div>
            <div className="grid gap-1.5"><Label>Order ID</Label><Input value={form.order_id} onChange={set("order_id")} /></div>
            <div className="grid gap-1.5"><Label>Order Item ID</Label><Input value={form.order_item_id} onChange={set("order_item_id")} /></div>
            <div className="grid gap-1.5"><Label>Work Order ID</Label><Input value={form.work_order_id} onChange={set("work_order_id")} /></div>
            <div className="grid gap-1.5"><Label>Production Stage ID</Label><Input value={form.production_stage_id} onChange={set("production_stage_id")} /></div>
            <div className="grid gap-1.5"><Label>Employee visible</Label><Select value={form.employee_visible} onValueChange={set("employee_visible")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="no">No</SelectItem><SelectItem value="yes">Yes</SelectItem></SelectContent></Select></div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy}>{busy ? "Saving..." : "Save task"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TaskActions({ task, onDone }) {
  const [busy, setBusy] = useState(false);
  const action = async (name, body = {}) => {
    setBusy(true);
    try {
      await api.post(`/tasks/${task.id}/${name}`, body);
      toast.success("Task updated");
      onDone?.();
    } catch (err) {
      toast.error(extractError(err, "Task action failed"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-wrap gap-2">
      {task.status === "not_started" && <Button size="sm" variant="outline" disabled={busy} onClick={() => action("start")}><CirclePlay className="size-3.5 mr-1" />Start</Button>}
      {["waiting", "blocked"].includes(task.status) && <Button size="sm" variant="outline" disabled={busy} onClick={() => action("resume")}><RotateCcw className="size-3.5 mr-1" />Resume</Button>}
      {task.status === "in_progress" && <Button size="sm" variant="outline" disabled={busy} onClick={() => action("wait", { reason: "Set from task shell" })}><TimerReset className="size-3.5 mr-1" />Wait</Button>}
      {["in_progress", "waiting"].includes(task.status) && <Button size="sm" variant="outline" disabled={busy} onClick={() => action("block", { reason: "Blocked from task shell" })}>Block</Button>}
      {task.status === "in_progress" && <Button size="sm" disabled={busy} onClick={() => action("complete")}><CheckCircle2 className="size-3.5 mr-1" />Complete</Button>}
      {["completed", "canceled"].includes(task.status) && <Button size="sm" variant="outline" disabled={busy} onClick={() => action("reopen", { reason: "Reopened from task shell" })}>Reopen</Button>}
    </div>
  );
}

function DetailPanel({ task, employees, comments, onDone }) {
  const [comment, setComment] = useState("");
  async function addComment(e) {
    e.preventDefault();
    try {
      await api.post(`/tasks/${task.id}/comments`, { body: comment, visibility: task.employee_visible ? "employee" : "internal" });
      setComment("");
      onDone?.();
    } catch (err) {
      toast.error(extractError(err, "Comment failed"));
    }
  }
  const employee = employees.find((e) => e.id === task.assigned_employee_id);
  return (
    <aside className="border rounded-lg bg-white p-4 space-y-4" data-testid="task-detail-panel">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold leading-tight">{task.title}</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge className={statusClass(task.status)}>{label(task.status)}</Badge>
            <Badge variant="outline">{label(task.priority)}</Badge>
            {task.employee_visible && <Badge variant="secondary">employee visible</Badge>}
          </div>
        </div>
        <TaskDialog task={task} employees={employees} onDone={onDone} trigger={<Button size="sm" variant="outline">Edit</Button>} />
      </div>
      {task.description && <p className="text-sm text-slate-600 whitespace-pre-wrap">{task.description}</p>}
      <div className="grid gap-2 text-sm">
        <div><span className="text-slate-500">Assignee:</span> {employee?.name || task.assigned_user_id || "Unassigned"}</div>
        <div><span className="text-slate-500">Due:</span> {task.due_at || "No due date"}</div>
        <div><span className="text-slate-500">Links:</span> {[task.customer_id && `customer ${task.customer_id}`, task.order_id && `order ${task.order_id}`, task.order_item_id && `item ${task.order_item_id}`, task.work_order_id && `WO ${task.work_order_id}`, task.production_stage_id && `stage ${task.production_stage_id}`].filter(Boolean).join(" / ") || "None"}</div>
      </div>
      <TaskActions task={task} onDone={onDone} />
      <div className="border-t pt-4 space-y-3">
        <div className="font-medium text-sm flex items-center gap-2"><MessageSquare className="size-4" />Comments</div>
        <div className="space-y-2 max-h-52 overflow-auto">
          {!comments?.length ? <p className="text-sm text-slate-500 italic">No comments yet.</p> : comments.map((c) => (
            <div key={c.id} className="rounded-md bg-slate-50 p-2 text-sm">
              <div className="text-xs text-slate-500">{c.visibility} · {c.created_at}</div>
              <div className="whitespace-pre-wrap">{c.body}</div>
            </div>
          ))}
        </div>
        <form onSubmit={addComment} className="space-y-2">
          <Textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Add a comment" data-testid="task-comment-input" />
          <Button size="sm" type="submit" disabled={!comment.trim()}>Add comment</Button>
        </form>
      </div>
    </aside>
  );
}

export default function TasksPage() {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const [filters, setFilters] = useState({ status: "all", priority: "all", assigned_employee_id: "all", q: "", include_archived: false });
  const [selectedId, setSelectedId] = useState(null);
  const canCreate = hasPerm("task:create");
  const canArchive = hasPerm("task:archive");

  const employeesQ = useQuery({
    queryKey: ["employees-for-tasks"],
    queryFn: async () => (await api.get("/employees", { params: { status: "active" } })).data.items || [],
  });
  const params = useMemo(() => {
    const p = { include_archived: filters.include_archived };
    if (filters.status !== "all") p.status = filters.status;
    if (filters.priority !== "all") p.priority = filters.priority;
    if (filters.assigned_employee_id !== "all") p.assigned_employee_id = filters.assigned_employee_id;
    if (filters.q.trim()) p.q = filters.q.trim();
    return p;
  }, [filters]);
  const tasksQ = useQuery({
    queryKey: ["tasks", params],
    queryFn: async () => (await api.get("/tasks", { params })).data,
  });
  const selected = (tasksQ.data?.items || []).find((t) => t.id === selectedId) || tasksQ.data?.items?.[0];
  const commentsQ = useQuery({
    queryKey: ["task-comments", selected?.id],
    enabled: !!selected?.id,
    queryFn: async () => (await api.get(`/tasks/${selected.id}/comments`)).data.items,
  });
  const employees = employeesQ.data || [];
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["tasks"] });
    if (selected?.id) qc.invalidateQueries({ queryKey: ["task-comments", selected.id] });
  };

  async function archive(task) {
    try {
      await api.post(`/tasks/${task.id}/${task.archived_at ? "restore" : "archive"}`);
      toast.success(task.archived_at ? "Task restored" : "Task archived");
      refresh();
    } catch (err) {
      toast.error(extractError(err, "Archive failed"));
    }
  }

  return (
    <div className="space-y-4" data-testid="tasks-page">
      <PageHeader
        title="Tasks"
        subtitle="Shared tenant tasks for linked work across the shop."
        actions={canCreate && <TaskDialog employees={employees} onDone={refresh} trigger={<Button data-testid="task-create-button"><Plus className="size-4 mr-1" />New task</Button>} />}
      />
      <div className="border rounded-lg bg-white p-3 grid gap-3 md:grid-cols-[1.4fr_160px_160px_180px_auto]" data-testid="tasks-filters">
        <div className="relative">
          <Search className="size-4 absolute left-2 top-2.5 text-slate-400" />
          <Input className="pl-8" placeholder="Search tasks" value={filters.q} onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} />
        </div>
        <Select value={filters.status} onValueChange={(v) => setFilters((f) => ({ ...f, status: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All statuses</SelectItem>{STATUSES.map((s) => <SelectItem key={s} value={s}>{label(s)}</SelectItem>)}</SelectContent></Select>
        <Select value={filters.priority} onValueChange={(v) => setFilters((f) => ({ ...f, priority: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All priorities</SelectItem>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{label(p)}</SelectItem>)}</SelectContent></Select>
        <Select value={filters.assigned_employee_id} onValueChange={(v) => setFilters((f) => ({ ...f, assigned_employee_id: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All assignees</SelectItem>{employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent></Select>
        <Button variant={filters.include_archived ? "default" : "outline"} onClick={() => setFilters((f) => ({ ...f, include_archived: !f.include_archived }))}><Archive className="size-4" /></Button>
      </div>
      {tasksQ.isLoading ? <TableSkeleton /> : tasksQ.error ? (
        <EmptyState title="Could not load tasks" description="Please try again." />
      ) : !tasksQ.data?.items?.length ? (
        <EmptyState title="No tasks found" description="Create or adjust filters to see shared tasks." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="border rounded-lg bg-white divide-y" data-testid="tasks-list">
            {tasksQ.data.items.map((task) => (
              <button key={task.id} className={`w-full text-left p-3 hover:bg-slate-50 ${selected?.id === task.id ? "bg-slate-50" : ""}`} onClick={() => setSelectedId(task.id)} data-testid={`task-row-${task.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium truncate">{task.title}</div>
                    <div className="text-xs text-slate-500 truncate">{task.description || task.task_type}</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge className={statusClass(task.status)}>{label(task.status)}</Badge>
                      <Badge variant="outline">{label(task.priority)}</Badge>
                      {task.due_at && <Badge variant="secondary">due {task.due_at}</Badge>}
                    </div>
                  </div>
                  {canArchive && <Button type="button" size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); archive(task); }}>{task.archived_at ? "Restore" : "Archive"}</Button>}
                </div>
              </button>
            ))}
          </div>
          {selected && <DetailPanel task={selected} employees={employees} comments={commentsQ.data || []} onDone={refresh} />}
        </div>
      )}
    </div>
  );
}
