import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import EmptyState from "@/components/common/EmptyState";
import { toast } from "sonner";
import { CalendarDays, ChevronLeft, ChevronRight, Clock, Plus, RefreshCw, Search } from "lucide-react";

function isoDate(d) { return d.toISOString().slice(0, 10); }
function startOfMonth(dateStr) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-01`;
}
function addDays(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return isoDate(d);
}
function addMonths(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + n);
  return isoDate(d);
}
function fmtTime(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); } catch { return ""; }
}
function toLocalDateTime(dateStr, timeStr) {
  return new Date(`${dateStr}T${timeStr}:00`).toISOString();
}

const VIEW_SPANS = {
  day: 1,
  week: 7,
  month: 35,
  agenda: 14,
};

const TYPE_LABELS = {
  consultation: "Consultation",
  site_survey: "Site Survey",
  vehicle_dropoff: "Vehicle Drop-off",
  vehicle_pickup: "Vehicle Pickup",
  installation: "Installation",
  customer_meeting: "Customer Meeting",
  internal_meeting: "Internal Meeting",
  production_milestone: "Production Milestone",
  custom: "Custom",
};

function rangeFor(view, anchor) {
  const start = view === "month" ? startOfMonth(anchor) : anchor;
  return {
    start_at: `${start}T00:00:00.000Z`,
    end_at: `${addDays(start, VIEW_SPANS[view] || 7)}T00:00:00.000Z`,
  };
}

function AppointmentDialog({ open, onOpenChange, employees, initialDate, onSaved }) {
  const [title, setTitle] = useState("");
  const [eventType, setEventType] = useState("consultation");
  const [date, setDate] = useState(initialDate);
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("10:00");
  const [employeeId, setEmployeeId] = useState("none");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [conflict, setConflict] = useState(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(force = false) {
    if (!title.trim()) return toast.error("Title is required");
    const payload = {
      title,
      event_type: eventType,
      start_at: toLocalDateTime(date, start),
      end_at: toLocalDateTime(date, end),
      employee_id: employeeId === "none" ? undefined : employeeId,
      location: location || undefined,
      description: description || undefined,
      visibility: employeeId === "none" ? "staff" : "employee",
    };
    if (force) payload.conflict_override_reason = overrideReason;
    setBusy(true);
    try {
      await api.post("/calendar/events", payload);
      toast.success("Appointment created");
      setConflict(null);
      setOverrideReason("");
      onOpenChange(false);
      onSaved();
    } catch (err) {
      const detail = err?.response?.data?.detail || "";
      if (err?.response?.status === 409) setConflict(detail || "Calendar conflict");
      else toast.error(extractError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="calendar-appointment-dialog">
        <DialogHeader><DialogTitle>Create appointment</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div className="grid gap-1.5"><Label>Title</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} data-testid="calendar-event-title" /></div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label>Type</Label>
              <Select value={eventType} onValueChange={setEventType}>
                <SelectTrigger data-testid="calendar-event-type"><SelectValue /></SelectTrigger>
                <SelectContent>{Object.entries(TYPE_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>Employee</Label>
              <Select value={employeeId} onValueChange={setEmployeeId}>
                <SelectTrigger data-testid="calendar-event-employee"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Unassigned</SelectItem>
                  {employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="grid gap-1.5"><Label>Date</Label><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></div>
            <div className="grid gap-1.5"><Label>Start</Label><Input type="time" value={start} onChange={(e) => setStart(e.target.value)} /></div>
            <div className="grid gap-1.5"><Label>End</Label><Input type="time" value={end} onChange={(e) => setEnd(e.target.value)} /></div>
          </div>
          <div className="grid gap-1.5"><Label>Location</Label><Input value={location} onChange={(e) => setLocation(e.target.value)} /></div>
          <div className="grid gap-1.5"><Label>Description</Label><Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} /></div>
          {conflict && (
            <div className="rounded border border-amber-300 bg-amber-50 p-3 space-y-2 text-sm" data-testid="calendar-conflict-warning">
              <div className="text-amber-900">{conflict}</div>
              <Label className="text-xs">Override reason</Label>
              <Input value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} data-testid="calendar-conflict-override-reason" />
              <Button size="sm" onClick={() => submit(true)} disabled={!overrideReason || busy}>Save with override</Button>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => submit(false)} disabled={busy}>Create</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EventChip({ item, onCancel }) {
  const label = item.display_title || item.title;
  const tone = item.source_type === "production_stage" ? "border-orange-300 bg-orange-50" : item.source_type === "task" ? "border-violet-300 bg-violet-50" : "border-sky-300 bg-sky-50";
  return (
    <div className={`rounded border p-2 text-xs ${tone}`} data-testid={`calendar-item-${item.source_type}-${item.source_id}`}>
      <div className="font-medium">{label}</div>
      <div className="text-muted-foreground">{fmtTime(item.start_at)}-{fmtTime(item.end_at)}</div>
      <div className="mt-1 flex items-center gap-1 flex-wrap">
        <Badge variant="outline" className="text-[10px]">{String(item.event_type || item.source_type).replace(/_/g, " ")}</Badge>
        {item.status && <Badge variant="outline" className="text-[10px]">{String(item.status).replace(/_/g, " ")}</Badge>}
      </div>
      {item.allowed_actions?.includes("cancel") && (
        <button type="button" className="mt-1 text-[11px] text-rose-700 hover:underline" onClick={() => onCancel(item)}>
          Cancel
        </button>
      )}
    </div>
  );
}

export default function ShopSchedulePage() {
  const qc = useQueryClient();
  const [view, setView] = useState("week");
  const [anchor, setAnchor] = useState(isoDate(new Date()));
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);

  const range = useMemo(() => rangeFor(view, anchor), [view, anchor]);
  const days = useMemo(() => Array.from({ length: view === "month" ? 35 : view === "day" ? 1 : 7 }, (_, i) => addDays(view === "month" ? startOfMonth(anchor) : anchor, i)), [view, anchor]);

  const { data: employeesData } = useQuery({
    queryKey: ["employees-calendar"],
    queryFn: async () => (await api.get("/employees", { params: { status: "active" } })).data,
  });
  const employees = employeesData?.items || [];

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["calendar-feed", "shop", range.start_at, range.end_at, typeFilter],
    queryFn: async () => (await api.get("/calendar/feed", {
      params: {
        ...range,
        surface: "shop",
        event_type: typeFilter === "all" ? undefined : typeFilter,
      },
    })).data,
  });

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return data?.items || [];
    return (data?.items || []).filter((item) => `${item.title || ""} ${item.display_title || ""} ${item.location || ""}`.toLowerCase().includes(q));
  }, [data, search]);

  const byDay = useMemo(() => {
    const m = {};
    filtered.forEach((item) => {
      const key = String(item.start_at || "").slice(0, 10);
      (m[key] = m[key] || []).push(item);
    });
    return m;
  }, [filtered]);

  async function cancelAppointment(item) {
    try {
      await api.post(`/calendar/events/${item.source_id}/cancel`, { reason: "Canceled from Shop Schedule" });
      toast.success("Appointment canceled");
      refetch();
    } catch (err) { toast.error(extractError(err)); }
  }

  function move(delta) {
    setAnchor((cur) => addDays(view === "month" ? addMonths(cur, delta) : cur, delta * (view === "day" ? 1 : 7)));
  }

  return (
    <div className="space-y-4" data-testid="shop-schedule-page">
      <PageHeader
        title="Shop Schedule"
        subtitle="Operational appointments, order deadlines, task due dates, and production milestones."
        actions={<Button size="sm" onClick={() => setDialogOpen(true)} data-testid="calendar-create-appointment"><Plus className="size-4 mr-1" />Appointment</Button>}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" size="icon" onClick={() => move(-1)}><ChevronLeft className="size-4" /></Button>
        <div className="text-sm font-medium flex items-center gap-1 min-w-[180px]"><CalendarDays className="size-4" />{range.start_at.slice(0, 10)} - {addDays(range.end_at.slice(0, 10), -1)}</div>
        <Button variant="ghost" size="icon" onClick={() => move(1)}><ChevronRight className="size-4" /></Button>
        <Select value={view} onValueChange={setView}>
          <SelectTrigger className="w-32" data-testid="calendar-view-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="day">Day</SelectItem>
            <SelectItem value="week">Week</SelectItem>
            <SelectItem value="month">Month</SelectItem>
            <SelectItem value="agenda">Agenda</SelectItem>
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-56" data-testid="calendar-type-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All event types</SelectItem>
            <SelectItem value="task_due">Task due dates</SelectItem>
            {Object.entries(TYPE_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
          </SelectContent>
        </Select>
        <div className="relative">
          <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
          <Input className="pl-8 w-56" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search schedule" />
        </div>
        <Button variant="outline" size="icon" onClick={() => refetch()}><RefreshCw className="size-4" /></Button>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading...</div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={Clock} title="No operational schedule items" description="Try another range or create an appointment." />
      ) : view === "agenda" ? (
        <Card>
          <CardContent className="p-0 divide-y">
            {filtered.map((item) => (
              <div key={item.id} className="p-3"><EventChip item={item} onCancel={cancelAppointment} /></div>
            ))}
          </CardContent>
        </Card>
      ) : (
        <div className={`grid gap-3 ${view === "day" ? "grid-cols-1" : "md:grid-cols-7"}`} data-testid="calendar-grid">
          {days.map((day) => (
            <Card key={day} className="min-h-[160px]">
              <CardHeader className="p-3 pb-1"><CardTitle className="text-sm">{day}</CardTitle></CardHeader>
              <CardContent className="p-3 pt-1 space-y-2">
                {(byDay[day] || []).map((item) => <EventChip key={item.id} item={item} onCancel={cancelAppointment} />)}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <AppointmentDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        employees={employees}
        initialDate={anchor}
        onSaved={() => { refetch(); qc.invalidateQueries({ queryKey: ["calendar-feed"] }); }}
      />
    </div>
  );
}
