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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Archive, CheckCircle2, CirclePlay, KanbanSquare, MessageSquare, Plus, RotateCcw, Search, TimerReset } from "lucide-react";
import { toast } from "sonner";

const STATUSES = ["not_started", "in_progress", "waiting", "blocked", "completed", "canceled"];
const KANBAN_STATUSES = ["not_started", "in_progress", "waiting", "blocked", "completed"];
const PRIORITIES = ["low", "normal", "high", "rush"];
const VIEWS = [
  ["all_active", "All Active"],
  ["my_tasks", "My Tasks"],
  ["due_today", "Due Today"],
  ["overdue", "Overdue"],
  ["unassigned", "Unassigned"],
  ["blocked", "Blocked"],
  ["waiting", "Waiting"],
  ["completed_recently", "Completed Recently"],
];
const SORTS = [
  ["due_date", "Due date"],
  ["priority", "Priority"],
  ["newest", "Newest"],
  ["oldest", "Oldest"],
  ["recently_updated", "Recently updated"],
  ["assignee", "Assignee"],
  ["title", "Title"],
];
const LINK_TYPES = ["customer", "quote", "order", "order_item", "work_order", "invoice", "production_stage"];

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
    quote_id: "",
    order_id: "",
    order_item_id: "",
    work_order_id: "",
    invoice_id: "",
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
      quote_id: task?.quote_id || "",
      order_id: task?.order_id || "",
      order_item_id: task?.order_item_id || "",
      work_order_id: task?.work_order_id || "",
      invoice_id: task?.invoice_id || "",
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
            <div className="grid gap-1.5"><Label>Quote ID</Label><Input value={form.quote_id} onChange={set("quote_id")} /></div>
            <div className="grid gap-1.5"><Label>Order ID</Label><Input value={form.order_id} onChange={set("order_id")} /></div>
            <div className="grid gap-1.5"><Label>Order Item ID</Label><Input value={form.order_item_id} onChange={set("order_item_id")} /></div>
            <div className="grid gap-1.5"><Label>Work Order ID</Label><Input value={form.work_order_id} onChange={set("work_order_id")} /></div>
            <div className="grid gap-1.5"><Label>Invoice ID</Label><Input value={form.invoice_id} onChange={set("invoice_id")} /></div>
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

function actionForTarget(task, target) {
  if (task.status === target) return null;
  if (target === "in_progress") return task.status === "not_started" ? "start" : "resume";
  if (target === "waiting") return "wait";
  if (target === "blocked") return "block";
  if (target === "completed") return "complete";
  return null;
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
      {task.status === "in_progress" && <Button size="sm" variant="outline" disabled={busy} onClick={() => action("wait", { reason: "Set from task list" })}><TimerReset className="size-3.5 mr-1" />Wait</Button>}
      {["in_progress", "waiting"].includes(task.status) && <Button size="sm" variant="outline" disabled={busy} onClick={() => action("block", { reason: "Blocked from task list" })}>Block</Button>}
      {task.status === "in_progress" && <Button size="sm" disabled={busy} onClick={() => action("complete")}><CheckCircle2 className="size-3.5 mr-1" />Complete</Button>}
      {["completed", "canceled"].includes(task.status) && <Button size="sm" variant="outline" disabled={busy} onClick={() => action("reopen", { reason: "Reopened from task list" })}>Reopen</Button>}
    </div>
  );
}

function DetailPanel({ task, employees, comments, onDone, canArchive }) {
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
  async function archive() {
    try {
      await api.post(`/tasks/${task.id}/${task.archived_at ? "restore" : "archive"}`);
      toast.success(task.archived_at ? "Task restored" : "Task archived");
      onDone?.();
    } catch (err) {
      toast.error(extractError(err, "Archive failed"));
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
            {task.overdue && <Badge variant="destructive">overdue</Badge>}
            {task.employee_visible && <Badge variant="secondary">employee visible</Badge>}
          </div>
        </div>
        <div className="flex gap-2">
          <TaskDialog task={task} employees={employees} onDone={onDone} trigger={<Button size="sm" variant="outline">Edit</Button>} />
          {canArchive && <Button size="sm" variant="outline" onClick={archive}><Archive className="size-4" /></Button>}
        </div>
      </div>
      {task.description && <p className="text-sm text-slate-600 whitespace-pre-wrap">{task.description}</p>}
      <div className="grid gap-2 text-sm">
        <div><span className="text-slate-500">Assignee:</span> {employee?.name || task.assigned_user_id || "Unassigned"}</div>
        <div><span className="text-slate-500">Due:</span> {task.due_at || "No due date"}</div>
        <div><span className="text-slate-500">Type:</span> {task.task_type || "general"}</div>
        <div><span className="text-slate-500">Created by:</span> {task.created_by_user_id || task.created_by_employee_id || "Unknown"}</div>
        <div><span className="text-slate-500">Updated:</span> {task.updated_at || task.created_at}</div>
        <div><span className="text-slate-500">Linked:</span> {task.linked_record_label || "None"}</div>
        {(task.waiting_reason || task.block_reason) && <div><span className="text-slate-500">State reason:</span> {task.waiting_reason || task.block_reason}</div>}
      </div>
      <TaskActions task={task} onDone={onDone} />
      <div className="rounded-md border bg-slate-50 p-3 text-xs text-slate-600">
        Reminder policy: {Object.keys(task.reminder_policy || {}).length ? JSON.stringify(task.reminder_policy) : "None"}
      </div>
      <div className="border-t pt-4 space-y-3">
        <div className="font-medium text-sm flex items-center gap-2"><MessageSquare className="size-4" />Comments</div>
        <div className="space-y-2 max-h-52 overflow-auto">
          {!comments?.length ? <p className="text-sm text-slate-500 italic">No comments yet.</p> : comments.map((c) => (
            <div key={c.id} className="rounded-md bg-slate-50 p-2 text-sm">
              <div className="text-xs text-slate-500">{c.visibility} / {c.created_at}</div>
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

function FilterBar({ filters, setFilters, employees }) {
  const set = (key, value) => setFilters((f) => ({ ...f, [key]: value, skip: 0 }));
  return (
    <div className="border rounded-lg bg-white p-3 grid gap-3 md:grid-cols-[1.4fr_repeat(4,160px)] lg:grid-cols-[1.4fr_repeat(7,150px)]" data-testid="tasks-filters">
      <div className="relative">
        <Search className="size-4 absolute left-2 top-2.5 text-slate-400" />
        <Input className="pl-8" placeholder="Search tasks" value={filters.q} onChange={(e) => set("q", e.target.value)} />
      </div>
      <Select value={filters.view} onValueChange={(v) => set("view", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{VIEWS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent></Select>
      <Select value={filters.status} onValueChange={(v) => set("status", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All statuses</SelectItem>{STATUSES.map((s) => <SelectItem key={s} value={s}>{label(s)}</SelectItem>)}</SelectContent></Select>
      <Select value={filters.priority} onValueChange={(v) => set("priority", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All priorities</SelectItem>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{label(p)}</SelectItem>)}</SelectContent></Select>
      <Select value={filters.assigned_employee_id} onValueChange={(v) => set("assigned_employee_id", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All assignees</SelectItem>{employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent></Select>
      <Input value={filters.task_type} onChange={(e) => set("task_type", e.target.value)} placeholder="Task type" />
      <Select value={filters.linked_entity_type} onValueChange={(v) => set("linked_entity_type", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">Any link</SelectItem>{LINK_TYPES.map((t) => <SelectItem key={t} value={t}>{label(t)}</SelectItem>)}</SelectContent></Select>
      <Select value={filters.sort} onValueChange={(v) => set("sort", v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{SORTS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent></Select>
      <div className="flex items-center gap-2 text-sm">
        <Checkbox checked={filters.include_archived} onCheckedChange={(v) => set("include_archived", v === true)} />
        <span>Archived</span>
      </div>
    </div>
  );
}

function TaskList({ tasks, selected, onSelect, employees }) {
  return (
    <div className="border rounded-lg bg-white divide-y" data-testid="tasks-list">
      {tasks.map((task) => {
        const emp = employees.find((e) => e.id === task.assigned_employee_id);
        return (
          <button key={task.id} className={`w-full text-left p-3 hover:bg-slate-50 ${selected?.id === task.id ? "bg-slate-50" : ""}`} onClick={() => onSelect(task.id)} data-testid={`task-row-${task.id}`}>
            <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_120px_130px_120px_120px] md:items-center">
              <div className="min-w-0">
                <div className="font-medium truncate">{task.title}</div>
                <div className="text-xs text-slate-500 truncate">{task.linked_record_label || task.description || task.task_type}</div>
              </div>
              <Badge className={statusClass(task.status)}>{label(task.status)}</Badge>
              <span className="text-sm text-slate-600">{emp?.name || task.assigned_user_id || "Unassigned"}</span>
              <Badge variant="outline">{label(task.priority)}</Badge>
              <span className={`text-sm ${task.overdue ? "font-medium text-rose-700" : "text-slate-600"}`}>{task.due_at || "No due"}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function KanbanView({ data, onDropTask, movingId }) {
  const columns = data?.columns || {};
  return (
    <div className="overflow-x-auto" data-testid="tasks-kanban-board">
      <div className="grid min-w-[980px] gap-3 md:grid-cols-5">
        {KANBAN_STATUSES.map((status) => (
          <section
            key={status}
            className="rounded-lg border bg-slate-50 p-2"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              onDropTask(e.dataTransfer.getData("text/task-id"), status);
            }}
            data-testid={`task-kanban-column-${status}`}
          >
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold capitalize">{label(status)}</h2>
              <Badge variant="outline">{columns[status]?.length || 0}</Badge>
            </div>
            <div className="space-y-2">
              {(columns[status] || []).map((task) => (
                <article
                  key={task.id}
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData("text/task-id", task.id)}
                  className={`rounded-md border bg-white p-3 shadow-sm ${movingId === task.id ? "opacity-60" : ""}`}
                  data-testid={`task-kanban-card-${task.id}`}
                >
                  <div className="font-medium text-sm">{task.title}</div>
                  <div className="mt-1 text-xs text-slate-500">{task.linked_record_label || task.task_type}</div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <Badge variant="outline">{label(task.priority)}</Badge>
                    {task.overdue && <Badge variant="destructive">overdue</Badge>}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

export default function TasksPage() {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const [tab, setTab] = useState("list");
  const [filters, setFilters] = useState({ view: "all_active", status: "all", priority: "all", assigned_employee_id: "all", linked_entity_type: "all", task_type: "", q: "", sort: "due_date", include_archived: false, skip: 0, limit: 50 });
  const [selectedId, setSelectedId] = useState(null);
  const [movingId, setMovingId] = useState(null);
  const canCreate = hasPerm("task:create");
  const canArchive = hasPerm("task:archive");

  const employeesQ = useQuery({
    queryKey: ["employees-for-tasks"],
    queryFn: async () => (await api.get("/employees", { params: { status: "active" } })).data.items || [],
  });
  const employees = employeesQ.data || [];

  const params = useMemo(() => {
    const p = { include_archived: filters.include_archived, limit: filters.limit, skip: filters.skip, sort: filters.sort };
    if (filters.status !== "all") p.status = filters.status;
    if (filters.view !== "all_active") p.view = filters.view;
    else if (filters.status === "all") p.view = "all_active";
    if (filters.priority !== "all") p.priority = filters.priority;
    if (filters.assigned_employee_id !== "all") p.assigned_employee_id = filters.assigned_employee_id;
    if (filters.linked_entity_type !== "all") p.linked_entity_type = filters.linked_entity_type;
    if (filters.task_type.trim()) p.task_type = filters.task_type.trim();
    if (filters.q.trim()) p.q = filters.q.trim();
    return p;
  }, [filters]);

  const tasksQ = useQuery({ queryKey: ["tasks", params], queryFn: async () => (await api.get("/tasks", { params })).data });
  const myQ = useQuery({ queryKey: ["tasks-my"], queryFn: async () => (await api.get("/tasks/my")).data, enabled: tab === "my" });
  const kanbanParams = useMemo(() => ({ include_completed: true, include_archived: filters.include_archived, q: filters.q || undefined }), [filters.include_archived, filters.q]);
  const kanbanQ = useQuery({ queryKey: ["tasks-kanban", kanbanParams], queryFn: async () => (await api.get("/tasks/kanban", { params: kanbanParams })).data, enabled: tab === "kanban" });

  const listItems = tab === "my" ? (myQ.data?.items || []) : (tasksQ.data?.items || []);
  const selected = listItems.find((t) => t.id === selectedId) || listItems[0];
  const commentsQ = useQuery({
    queryKey: ["task-comments", selected?.id],
    enabled: !!selected?.id,
    queryFn: async () => (await api.get(`/tasks/${selected.id}/comments`)).data.items,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["tasks"] });
    qc.invalidateQueries({ queryKey: ["tasks-my"] });
    qc.invalidateQueries({ queryKey: ["tasks-kanban"] });
    if (selected?.id) qc.invalidateQueries({ queryKey: ["task-comments", selected.id] });
  };

  async function dropTask(taskId, target) {
    const task = (kanbanQ.data?.items || []).find((t) => t.id === taskId);
    if (!task) return;
    const action = actionForTarget(task, target);
    if (!action) return;
    const previous = qc.getQueryData(["tasks-kanban", kanbanParams]);
    setMovingId(taskId);
    qc.setQueryData(["tasks-kanban", kanbanParams], (current) => {
      if (!current) return current;
      const nextColumns = Object.fromEntries(Object.entries(current.columns || {}).map(([k, v]) => [k, v.filter((t) => t.id !== taskId)]));
      nextColumns[target] = [{ ...task, status: target }, ...(nextColumns[target] || [])];
      return { ...current, columns: nextColumns };
    });
    try {
      await api.post(`/tasks/${taskId}/${action}`, { reason: `Moved to ${target} from Kanban` });
      toast.success("Task moved");
      refresh();
    } catch (err) {
      qc.setQueryData(["tasks-kanban", kanbanParams], previous);
      toast.error(extractError(err, "Move rejected"));
    } finally {
      setMovingId(null);
    }
  }

  const currentQ = tab === "my" ? myQ : tasksQ;

  return (
    <div className="space-y-4" data-testid="tasks-page">
      <PageHeader
        title="Tasks"
        subtitle="Shared tenant tasks, staff work views, and linked record handoffs."
        actions={canCreate && <TaskDialog employees={employees} onDone={refresh} trigger={<Button data-testid="task-create-button"><Plus className="size-4 mr-1" />New task</Button>} />}
      />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="list">List</TabsTrigger>
          <TabsTrigger value="kanban"><KanbanSquare className="size-4 mr-1" />Kanban</TabsTrigger>
          <TabsTrigger value="my">My Tasks</TabsTrigger>
        </TabsList>
        <TabsContent value="list" className="space-y-4">
          <FilterBar filters={filters} setFilters={setFilters} employees={employees} />
          {currentQ.isLoading ? <TableSkeleton /> : currentQ.error ? <EmptyState title="Could not load tasks" description="Please try again." /> : !listItems.length ? <EmptyState title="No tasks found" description="Create or adjust filters to see shared tasks." /> : (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
              <TaskList tasks={listItems} selected={selected} onSelect={setSelectedId} employees={employees} />
              {selected && <DetailPanel task={selected} employees={employees} comments={commentsQ.data || []} onDone={refresh} canArchive={canArchive} />}
            </div>
          )}
          <Pagination data={tasksQ.data} filters={filters} setFilters={setFilters} />
        </TabsContent>
        <TabsContent value="kanban" className="space-y-4">
          <div className="border rounded-lg bg-white p-3 flex flex-wrap gap-3">
            <Input className="max-w-sm" placeholder="Search Kanban" value={filters.q} onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} />
            <div className="flex items-center gap-2 text-sm"><Checkbox checked={filters.include_archived} onCheckedChange={(v) => setFilters((f) => ({ ...f, include_archived: v === true }))} />Archived</div>
          </div>
          {kanbanQ.isLoading ? <TableSkeleton /> : kanbanQ.error ? <EmptyState title="Could not load Kanban" description="Please try again." /> : <KanbanView data={kanbanQ.data} onDropTask={dropTask} movingId={movingId} />}
        </TabsContent>
        <TabsContent value="my" className="space-y-4">
          <SummaryStrip summary={myQ.data?.summary} />
          {myQ.isLoading ? <TableSkeleton /> : myQ.error ? <EmptyState title="Could not load my tasks" description="Please try again." /> : !listItems.length ? <EmptyState title="No tasks assigned" description="Assigned and created tasks will appear here." /> : (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
              <TaskList tasks={listItems} selected={selected} onSelect={setSelectedId} employees={employees} />
              {selected && <DetailPanel task={selected} employees={employees} comments={commentsQ.data || []} onDone={refresh} canArchive={canArchive} />}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Pagination({ data, filters, setFilters }) {
  if (!data?.total) return null;
  const start = filters.skip + 1;
  const end = Math.min(filters.skip + filters.limit, data.total);
  return (
    <div className="flex items-center justify-between text-sm text-slate-600">
      <span>{start}-{end} of {data.total}</span>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" disabled={filters.skip === 0} onClick={() => setFilters((f) => ({ ...f, skip: Math.max(0, f.skip - f.limit) }))}>Previous</Button>
        <Button size="sm" variant="outline" disabled={end >= data.total} onClick={() => setFilters((f) => ({ ...f, skip: f.skip + f.limit }))}>Next</Button>
      </div>
    </div>
  );
}

function SummaryStrip({ summary = {} }) {
  const rows = [
    ["Due today", summary.due_today],
    ["Overdue", summary.overdue],
    ["Upcoming", summary.upcoming],
    ["Blocked", summary.blocked],
    ["Waiting", summary.waiting],
    ["Completed recently", summary.completed_recently],
  ];
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
      {rows.map(([labelText, value]) => (
        <div key={labelText} className="rounded-md border bg-white p-3">
          <div className="text-lg font-semibold">{value || 0}</div>
          <div className="text-xs text-slate-500">{labelText}</div>
        </div>
      ))}
    </div>
  );
}
