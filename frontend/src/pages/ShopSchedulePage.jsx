import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import EmptyState from "@/components/common/EmptyState";
import { toast } from "sonner";
import {
  AlertCircle,
  CalendarCheck,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  ListChecks,
  Plus,
  Search,
} from "lucide-react";

const TODAY = () => new Date().toISOString().slice(0, 10);
const LOCAL_VIEWS = [
  { key: "calendar", label: "Calendar" },
  { key: "agenda", label: "Agenda" },
  { key: "appointments", label: "Appointments" },
];
const OPERATIONAL_SOURCE_TYPES = new Set(["calendar_event", "task", "production_stage"]);
const APPOINTMENT_SOURCE_TYPES = new Set(["calendar_event"]);
const EVENT_TYPE_LABELS = {
  consultation: "Consultation",
  site_survey: "Site Survey",
  vehicle_dropoff: "Vehicle Drop-off",
  vehicle_pickup: "Vehicle Pickup",
  installation: "Installation",
  customer_meeting: "Customer Meeting",
  production_milestone: "Production Milestone",
  custom: "Custom",
};

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

function addDays(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return isoDate(d);
}

function fmtDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  } catch {
    return String(iso).slice(0, 10);
  }
}

function fmtTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function toInputDate(iso, fallback = TODAY()) {
  if (!iso) return fallback;
  return String(iso).slice(0, 10);
}

function toInputTime(iso, fallback) {
  if (!iso) return fallback;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return fallback;
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function toLocalDateTime(dateStr, timeStr) {
  return new Date(`${dateStr}T${timeStr}:00`).toISOString();
}

function rangeFor(view, anchor) {
  const span = view === "appointments" ? 30 : view === "agenda" ? 14 : 7;
  return {
    start_at: `${anchor}T00:00:00.000Z`,
    end_at: `${addDays(anchor, span)}T00:00:00.000Z`,
  };
}

function clean(value) {
  return value && value !== "none" ? value : undefined;
}

function eventId(item) {
  return item?.source_id || item?.id?.replace(/^calendar_event:/, "");
}

function itemTitle(item) {
  return item?.display_title || item?.title || "Scheduled item";
}

function buildItemDestination(item) {
  if (item?.source_type === "production_stage" && item.work_order_id) return `/work-orders/${item.work_order_id}`;
  if (item?.work_order_id) return `/work-orders/${item.work_order_id}`;
  if (item?.order_id) return `/orders/${item.order_id}`;
  if (item?.customer_id) return `/customers/${item.customer_id}`;
  if (item?.source_type === "task") return "/team/tasks";
  return null;
}

function summarizeConflict(detail) {
  if (!detail) return "Calendar conflict requires manager override reason.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((entry) => entry?.msg || String(entry)).join("; ");
  return detail.detail || detail.message || "Calendar conflict requires manager override reason.";
}

function AppointmentDialog({ open, onOpenChange, employees, initialDate, initialContext, editingEvent, onSaved }) {
  const [form, setForm] = useState({});
  const [conflict, setConflict] = useState(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [busy, setBusy] = useState(false);
  const editing = editingEvent?.source_type === "calendar_event";

  useEffect(() => {
    if (!open) return;
    setConflict(null);
    setOverrideReason("");
    setForm({
      title: editing ? itemTitle(editingEvent) : initialContext.title || "",
      event_type: editing ? editingEvent.event_type || "custom" : initialContext.eventType || "customer_meeting",
      date: editing ? toInputDate(editingEvent.start_at, initialDate) : initialContext.date || initialDate,
      start: editing ? toInputTime(editingEvent.start_at, "09:00") : "09:00",
      end: editing ? toInputTime(editingEvent.end_at, "10:00") : "10:00",
      timezone: editing ? editingEvent.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "" : Intl.DateTimeFormat().resolvedOptions().timeZone || "",
      employee_id: editing ? editingEvent.employee_id || "none" : "none",
      customer_id: editing ? editingEvent.customer_id || "" : initialContext.customerId || "",
      order_id: editing ? editingEvent.order_id || "" : initialContext.orderId || "",
      work_order_id: editing ? editingEvent.work_order_id || "" : initialContext.workOrderId || "",
      location: editing ? editingEvent.location || "" : "",
      description: editing ? editingEvent.description || "" : "",
    });
  }, [editing, editingEvent, initialContext, initialDate, open]);

  function setField(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(force = false) {
    if (!form.title?.trim()) {
      toast.error("Title is required");
      return;
    }
    const payload = {
      title: form.title.trim(),
      event_type: form.event_type,
      start_at: toLocalDateTime(form.date, form.start),
      end_at: toLocalDateTime(form.date, form.end),
      timezone: clean(form.timezone),
      employee_id: clean(form.employee_id),
      customer_id: clean(form.customer_id),
      order_id: clean(form.order_id),
      work_order_id: clean(form.work_order_id),
      location: clean(form.location),
      description: clean(form.description),
      visibility: clean(form.employee_id) ? "employee" : "staff",
    };
    if (force) payload.conflict_override_reason = overrideReason;

    setBusy(true);
    try {
      if (editing) {
        await api.patch(`/calendar/events/${eventId(editingEvent)}`, payload);
        toast.success("Appointment updated");
      } else {
        await api.post("/calendar/events", payload);
        toast.success("Appointment created");
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      if (err?.response?.status === 409) setConflict(summarizeConflict(err.response.data?.detail));
      else toast.error(extractError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="calendar-appointment-dialog">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit appointment" : "Create appointment"}</DialogTitle>
          <DialogDescription>
            Create or update an operational appointment stored in the shared calendar foundation.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid gap-1.5">
            <Label htmlFor="calendar-event-title">Title</Label>
            <Input id="calendar-event-title" value={form.title || ""} onChange={(e) => setField("title", e.target.value)} data-testid="calendar-event-title" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label>Type</Label>
              <Select value={form.event_type || "customer_meeting"} onValueChange={(value) => setField("event_type", value)}>
                <SelectTrigger data-testid="calendar-event-type"><SelectValue /></SelectTrigger>
                <SelectContent>{Object.entries(EVENT_TYPE_LABELS).map(([key, label]) => <SelectItem key={key} value={key}>{label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>Assigned employee</Label>
              <Select value={form.employee_id || "none"} onValueChange={(value) => setField("employee_id", value)}>
                <SelectTrigger data-testid="calendar-event-employee"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Unassigned</SelectItem>
                  {employees.map((employee) => <SelectItem key={employee.id} value={employee.id}>{employee.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-date">Date</Label>
              <Input id="calendar-event-date" type="date" value={form.date || initialDate} onChange={(e) => setField("date", e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-start">Start</Label>
              <Input id="calendar-event-start" type="time" value={form.start || "09:00"} onChange={(e) => setField("start", e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-end">End</Label>
              <Input id="calendar-event-end" type="time" value={form.end || "10:00"} onChange={(e) => setField("end", e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-timezone">Timezone</Label>
              <Input id="calendar-event-timezone" value={form.timezone || ""} onChange={(e) => setField("timezone", e.target.value)} />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-customer">Customer ID</Label>
              <Input id="calendar-event-customer" value={form.customer_id || ""} onChange={(e) => setField("customer_id", e.target.value)} data-testid="calendar-event-customer-id" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-order">Order ID</Label>
              <Input id="calendar-event-order" value={form.order_id || ""} onChange={(e) => setField("order_id", e.target.value)} data-testid="calendar-event-order-id" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-work-order">Work Order ID</Label>
              <Input id="calendar-event-work-order" value={form.work_order_id || ""} onChange={(e) => setField("work_order_id", e.target.value)} data-testid="calendar-event-work-order-id" />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="calendar-event-location">Location</Label>
            <Input id="calendar-event-location" value={form.location || ""} onChange={(e) => setField("location", e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="calendar-event-description">Notes</Label>
            <Textarea id="calendar-event-description" rows={2} value={form.description || ""} onChange={(e) => setField("description", e.target.value)} />
          </div>
          {conflict && (
            <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm" data-testid="calendar-conflict-warning">
              <div className="flex items-start gap-2 text-amber-900"><AlertCircle className="mt-0.5 size-4" />{conflict}</div>
              <Label htmlFor="calendar-conflict-override-reason" className="text-xs">Override reason</Label>
              <Input id="calendar-conflict-override-reason" value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} data-testid="calendar-conflict-override-reason" />
              <Button size="sm" onClick={() => submit(true)} disabled={!overrideReason || busy}>Save with override</Button>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => submit(false)} disabled={busy}>{editing ? "Save" : "Create"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EventCard({ item, canManage, onOpen, onCancel }) {
  const tone = item.source_type === "production_stage"
    ? "border-orange-200 bg-orange-50"
    : item.source_type === "task"
      ? "border-violet-200 bg-violet-50"
      : "border-sky-200 bg-sky-50";
  return (
    <div
      className={`rounded-md border p-2 text-xs ${tone}`}
      data-testid={`shop-schedule-item-${item.source_type}-${item.source_id}`}
    >
      <button
        type="button"
        className="w-full text-left transition hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        onClick={() => onOpen(item)}
      >
        <div className="font-medium text-slate-950">{itemTitle(item)}</div>
        <div className="text-slate-600">{fmtTime(item.start_at)} - {fmtTime(item.end_at)}</div>
        <div className="mt-1 flex flex-wrap items-center gap-1">
          <Badge variant="outline" className="bg-white/70 text-[10px]">{String(item.event_type || item.source_type).replace(/_/g, " ")}</Badge>
          {item.status && <Badge variant="outline" className="bg-white/70 text-[10px]">{String(item.status).replace(/_/g, " ")}</Badge>}
        </div>
      </button>
      {canManage && item.allowed_actions?.includes("cancel") && (
        <button
          type="button"
          className="mt-1 text-[11px] font-medium text-rose-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          onClick={() => onCancel(item)}
        >
          Cancel appointment
        </button>
      )}
    </div>
  );
}

function LocalViewTabs({ view, onChange }) {
  return (
    <div className="inline-flex rounded-md border bg-white p-1" role="tablist" aria-label="Shop schedule views" data-testid="shop-schedule-view-tabs">
      {LOCAL_VIEWS.map((option) => (
        <button
          key={option.key}
          type="button"
          role="tab"
          aria-selected={view === option.key ? "true" : "false"}
          data-active={view === option.key ? "true" : "false"}
          data-testid={`shop-schedule-view-${option.key}`}
          className={`h-8 rounded px-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${view === option.key ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"}`}
          onClick={() => onChange(option.key)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export default function ShopSchedulePage() {
  const qc = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  const { hasPerm } = useAuth();
  const canManageSchedule = hasPerm("schedule:manage");
  const query = useMemo(() => new URLSearchParams(location.search || ""), [location.search]);
  const urlView = LOCAL_VIEWS.some((option) => option.key === query.get("view")) ? query.get("view") : "calendar";
  const initialDate = query.get("date") === "today" || !query.get("date") ? TODAY() : query.get("date");
  const [anchor, setAnchor] = useState(initialDate);
  const [employeeFilter, setEmployeeFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);

  useEffect(() => {
    if (query.get("date") === "today") setAnchor(TODAY());
    else if (query.get("date")) setAnchor(query.get("date"));
  }, [query]);

  useEffect(() => {
    if (canManageSchedule && query.get("new") === "1") {
      setEditingEvent(null);
      setDialogOpen(true);
    }
  }, [canManageSchedule, query]);

  const initialContext = useMemo(() => ({
    customerId: query.get("customer_id") || "",
    orderId: query.get("order_id") || "",
    workOrderId: query.get("work_order_id") || "",
    eventType: EVENT_TYPE_LABELS[query.get("type")] ? query.get("type") : "customer_meeting",
    title: query.get("title") || "",
    date: query.get("date") && query.get("date") !== "today" ? query.get("date") : "",
  }), [query]);

  const range = useMemo(() => rangeFor(urlView, anchor), [urlView, anchor]);
  const days = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(anchor, index)), [anchor]);

  const { data: employeesData } = useQuery({
    queryKey: ["employees-calendar"],
    queryFn: async () => (await api.get("/employees", { params: { status: "active" } })).data,
  });
  const employees = employeesData?.items || [];

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: [
      "calendar-feed",
      range.start_at,
      range.end_at,
      employeeFilter,
      typeFilter,
      initialContext.customerId,
      initialContext.orderId,
      initialContext.workOrderId,
    ],
    queryFn: async () => (await api.get("/calendar/feed", {
      params: {
        ...range,
        employee_id: employeeFilter === "all" ? undefined : employeeFilter,
        event_type: typeFilter === "all" ? undefined : typeFilter,
        customer_id: clean(initialContext.customerId),
        order_id: clean(initialContext.orderId),
        work_order_id: clean(initialContext.workOrderId),
      },
    })).data,
  });

  const operationalItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (data?.items || [])
      .filter((item) => OPERATIONAL_SOURCE_TYPES.has(item.source_type))
      .filter((item) => item.event_type !== "internal_meeting")
      .filter((item) => (urlView === "appointments" ? APPOINTMENT_SOURCE_TYPES.has(item.source_type) : true))
      .filter((item) => {
        if (!q) return true;
        return `${item.title || ""} ${item.display_title || ""} ${item.location || ""} ${item.status || ""}`.toLowerCase().includes(q);
      });
  }, [data, search, urlView]);

  const byDay = useMemo(() => {
    const map = {};
    operationalItems.forEach((item) => {
      const key = String(item.start_at || "").slice(0, 10);
      if (!map[key]) map[key] = [];
      map[key].push(item);
    });
    return map;
  }, [operationalItems]);

  const counts = useMemo(() => ({
    appointments: operationalItems.filter((item) => item.source_type === "calendar_event").length,
    production: operationalItems.filter((item) => item.source_type === "production_stage").length,
    tasks: operationalItems.filter((item) => item.source_type === "task").length,
  }), [operationalItems]);

  function setView(nextView) {
    const next = new URLSearchParams(location.search || "");
    next.set("view", nextView);
    next.delete("new");
    navigate(`/shop-schedule?${next.toString()}`);
  }

  function setDialogState(open) {
    setDialogOpen(open);
    if (!open && query.get("new") === "1") {
      const next = new URLSearchParams(location.search || "");
      next.delete("new");
      navigate(`/shop-schedule${next.toString() ? `?${next.toString()}` : ""}`, { replace: true });
    }
    if (!open) setEditingEvent(null);
  }

  function move(delta) {
    setAnchor((current) => addDays(current, delta * 7));
  }

  function openItem(item) {
    if (item.source_type === "calendar_event") {
      if (!canManageSchedule) return;
      setEditingEvent(item);
      setDialogOpen(true);
      return;
    }
    const destination = buildItemDestination(item);
    if (destination) navigate(destination);
  }

  async function cancelAppointment(item) {
    try {
      await api.post(`/calendar/events/${eventId(item)}/cancel`, { reason: "Canceled from Shop Schedule" });
      toast.success("Appointment canceled");
      refetch();
    } catch (err) {
      toast.error(extractError(err));
    }
  }

  function invalidateSchedule() {
    refetch();
    qc.invalidateQueries({ queryKey: ["calendar-feed"] });
  }

  const activeFilters = [
    initialContext.customerId && "Customer",
    initialContext.orderId && "Order",
    initialContext.workOrderId && "Work Order",
  ].filter(Boolean);

  return (
    <div className="space-y-4" data-testid="shop-schedule-page">
      <PageHeader
        title="Shop Schedule"
        subtitle="Operational appointments, order dates, and production milestones from the shared calendar foundation."
        actions={(
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline" size="sm">
              <Link to="/team/schedule">Team Schedule</Link>
            </Button>
            {canManageSchedule && (
              <Button size="sm" onClick={() => { setEditingEvent(null); setDialogOpen(true); }} data-testid="calendar-create-appointment">
                <Plus className="mr-1 size-4" />Appointment
              </Button>
            )}
          </div>
        )}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <LocalViewTabs view={urlView} onChange={setView} />
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => move(-1)} aria-label="Previous schedule range"><ChevronLeft className="size-4" /></Button>
          <div className="flex min-w-[210px] items-center gap-1 text-sm font-medium">
            <CalendarDays className="size-4" />{range.start_at.slice(0, 10)} - {addDays(range.end_at.slice(0, 10), -1)}
          </div>
          <Button variant="ghost" size="icon" onClick={() => move(1)} aria-label="Next schedule range"><ChevronRight className="size-4" /></Button>
          <Button variant="outline" size="sm" onClick={() => setAnchor(TODAY())} data-testid="shop-schedule-today">Today</Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3" data-testid="shop-schedule-summary">
        <Card><CardContent className="flex items-center gap-3 p-4"><CalendarCheck className="size-5 text-blue-700" /><div><div className="text-xs text-muted-foreground">Appointments</div><div className="text-xl font-semibold">{counts.appointments}</div></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-3 p-4"><Clock className="size-5 text-orange-700" /><div><div className="text-xs text-muted-foreground">Production milestones</div><div className="text-xl font-semibold">{counts.production}</div></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-3 p-4"><ListChecks className="size-5 text-violet-700" /><div><div className="text-xs text-muted-foreground">Task due dates</div><div className="text-xl font-semibold">{counts.tasks}</div></div></CardContent></Card>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-2 p-3">
          <div className="relative">
            <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
            <Input className="w-64 pl-8" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search operational schedule" data-testid="shop-schedule-search" />
          </div>
          <Select value={employeeFilter} onValueChange={setEmployeeFilter}>
            <SelectTrigger className="w-52" data-testid="calendar-employee-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All assigned employees</SelectItem>
              {employees.map((employee) => <SelectItem key={employee.id} value={employee.id}>{employee.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-56" data-testid="calendar-type-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All operational types</SelectItem>
              <SelectItem value="task_due">Task due dates</SelectItem>
              {Object.entries(EVENT_TYPE_LABELS).map(([key, label]) => <SelectItem key={key} value={key}>{label}</SelectItem>)}
            </SelectContent>
          </Select>
          {activeFilters.length > 0 && (
            <div className="flex flex-wrap gap-1 text-xs" data-testid="shop-schedule-linked-filter">
              {activeFilters.map((label) => <Badge key={label} variant="outline">{label} context</Badge>)}
            </div>
          )}
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="rounded-md border bg-white p-6 text-sm text-muted-foreground" data-testid="shop-schedule-loading">Loading schedule...</div>
      ) : isError ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" data-testid="shop-schedule-error">{extractError(error)}</div>
      ) : operationalItems.length === 0 ? (
        <EmptyState icon={Clock} title="No operational schedule items" description="Try a different range or create a customer, order, or production appointment." />
      ) : urlView === "calendar" ? (
        <div className="grid gap-3 md:grid-cols-7" data-testid="shop-schedule-calendar-grid">
          {days.map((day) => (
            <Card key={day} className="min-h-[170px]">
              <CardHeader className="p-3 pb-1"><CardTitle className="text-sm">{fmtDate(`${day}T00:00:00`)}</CardTitle></CardHeader>
              <CardContent className="space-y-2 p-3 pt-1">
                {(byDay[day] || []).map((item) => <EventCard key={item.id} item={item} canManage={canManageSchedule} onOpen={openItem} onCancel={cancelAppointment} />)}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card data-testid={urlView === "appointments" ? "shop-schedule-appointments-list" : "shop-schedule-agenda-list"}>
          <CardContent className="divide-y p-0">
            {operationalItems.map((item) => {
              const destination = buildItemDestination(item);
              return (
                <div key={item.id} className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="font-medium text-slate-950">{itemTitle(item)}</div>
                    <div className="text-sm text-muted-foreground">{fmtDate(item.start_at)} at {fmtTime(item.start_at)} - {fmtTime(item.end_at)}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      <Badge variant="outline">{String(item.event_type || item.source_type).replace(/_/g, " ")}</Badge>
                      {item.status && <Badge variant="outline">{String(item.status).replace(/_/g, " ")}</Badge>}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    {canManageSchedule && item.source_type === "calendar_event" ? (
                      <Button variant="outline" size="sm" onClick={() => openItem(item)} data-testid={`shop-schedule-edit-${item.source_id}`}>Edit</Button>
                    ) : destination ? (
                      <Button asChild variant="outline" size="sm"><Link to={destination}>Open record</Link></Button>
                    ) : null}
                    {canManageSchedule && item.allowed_actions?.includes("cancel") && (
                      <Button variant="ghost" size="sm" onClick={() => cancelAppointment(item)}>Cancel</Button>
                    )}
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      <AppointmentDialog
        open={dialogOpen}
        onOpenChange={setDialogState}
        employees={employees}
        initialDate={anchor}
        initialContext={initialContext}
        editingEvent={editingEvent}
        onSaved={invalidateSchedule}
      />
    </div>
  );
}
