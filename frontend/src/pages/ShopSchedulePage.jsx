import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
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
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  MapPin,
  Plus,
  RotateCcw,
  Search,
  Truck,
  Users,
  Wrench,
  X,
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
  if (item?.wrap_project_id) return `/wrap-lab/${item.wrap_project_id}`;
  if (item?.work_order_id) return `/work-orders/${item.work_order_id}`;
  if (item?.order_id) return `/orders/${item.order_id}`;
  if (item?.quote_id) return `/quotes/${item.quote_id}`;
  if (item?.customer_id) return `/customers/${item.customer_id}`;
  if (item?.source_type === "task") return "/team/tasks";
  return null;
}

function summarizeConflict(detail) {
  if (!detail) return "Calendar conflict requires manager override reason.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((entry) => entry?.msg || String(entry)).join("; ");
  if (Array.isArray(detail.conflicts) && detail.conflicts.length > 0) {
    return detail.conflicts.map((entry) => {
      const resource = entry.resource_name || entry.resource_id || entry.resource_type || "Resource";
      return `${resource}: ${entry.title || "conflicting event"} ${fmtTime(entry.start_at)} - ${fmtTime(entry.end_at)}`;
    }).join("; ");
  }
  return detail.detail || detail.message || "Calendar conflict requires manager override reason.";
}

function resourceLabel(item) {
  return item?.name || item?.title || item?.id || "Unnamed";
}

function selectedLabel(items, ids) {
  const map = new Map(items.map((item) => [item.id, resourceLabel(item)]));
  return ids.map((id) => map.get(id) || id).join(", ");
}

function assignmentText(item) {
  const summary = item?.assignment_summary || {};
  const parts = [
    ...(summary.employees || []).map((entry) => entry.name),
    ...(summary.equipment || []).map((entry) => entry.name),
    ...(summary.vehicles || []).map((entry) => entry.name),
    ...(summary.resources || []).map((entry) => entry.name),
  ].filter(Boolean);
  if (parts.length === 0 && item?.location) parts.push(item.location);
  return parts.join(" • ");
}

function toggleId(values, id) {
  return values.includes(id) ? values.filter((value) => value !== id) : [...values, id];
}

function ResourceChecklist({ title, icon: Icon, items, selectedIds, onChange, testId, detail }) {
  const [q, setQ] = useState("");
  const visible = items.filter((item) => `${resourceLabel(item)} ${item.role_label || ""} ${item.category || ""} ${item.resource_type || ""}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="rounded-md border p-3" data-testid={testId}>
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900">
        <Icon className="size-4 text-slate-500" />{title}
      </div>
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search ${title.toLowerCase()}`} className="mb-2 h-8" aria-label={`Search ${title}`} />
      <div className="max-h-28 space-y-1 overflow-auto">
        {visible.length === 0 ? (
          <div className="text-xs text-muted-foreground">No active records</div>
        ) : visible.map((item) => (
          <label key={item.id} className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 text-xs hover:bg-slate-50">
            <Checkbox checked={selectedIds.includes(item.id)} onCheckedChange={() => onChange(toggleId(selectedIds, item.id))} aria-label={resourceLabel(item)} />
            <span className="min-w-0">
              <span className="block truncate font-medium">{resourceLabel(item)}</span>
              {detail?.(item) && <span className="block truncate text-muted-foreground">{detail(item)}</span>}
            </span>
          </label>
        ))}
      </div>
      {selectedIds.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {selectedIds.map((id) => (
            <Badge key={id} variant="outline" className="gap-1 text-[10px]">
              {resourceLabel(items.find((item) => item.id === id) || { id })}
              <button type="button" aria-label={`Remove ${id}`} onClick={() => onChange(selectedIds.filter((value) => value !== id))}>
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function AvailabilityPanel({ availability, isLoading }) {
  if (isLoading) return <div className="rounded-md border bg-slate-50 p-3 text-sm text-muted-foreground">Checking availability...</div>;
  if (!availability) return null;
  const conflicts = availability.conflicts || [];
  const warnings = availability.warnings || [];
  return (
    <div className={`rounded-md border p-3 text-sm ${conflicts.length ? "border-amber-300 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`} data-testid="calendar-resource-availability">
      <div className="font-medium">{conflicts.length ? "Availability needs attention" : "Selected resources are available"}</div>
      <div className="mt-1 text-xs text-muted-foreground">
        {availability.summary?.assigned_employees || 0} assigned people • {availability.summary?.reserved_equipment || 0} equipment • {availability.summary?.reserved_vehicles || 0} vehicles • {availability.summary?.available_resources || 0} available spaces
      </div>
      {conflicts.length > 0 && (
        <div className="mt-2 space-y-1" data-testid="calendar-resource-conflicts">
          {conflicts.map((entry, index) => (
            <div key={`${entry.resource_type}-${entry.resource_id}-${entry.source_id}-${index}`} className="text-xs text-amber-950">
              <strong>{entry.resource_name || entry.resource_id}</strong> conflicts with {entry.title || "scheduled event"} at {fmtTime(entry.start_at)} - {fmtTime(entry.end_at)}
            </div>
          ))}
        </div>
      )}
      {warnings.length > 0 && <div className="mt-2 text-xs text-amber-900">{warnings.length} availability warning{warnings.length === 1 ? "" : "s"} to review.</div>}
    </div>
  );
}

function AppointmentDialog({ open, onOpenChange, employees, equipment, vehicles, resources, initialDate, initialContext, editingEvent, onSaved }) {
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
      assigned_employee_ids: editing ? editingEvent.assigned_employee_ids || (editingEvent.employee_id ? [editingEvent.employee_id] : []) : [],
      reserved_equipment_ids: editing ? editingEvent.reserved_equipment_ids || [] : [],
      reserved_vehicle_ids: editing ? editingEvent.reserved_vehicle_ids || [] : [],
      reserved_resource_ids: editing ? editingEvent.reserved_resource_ids || [] : [],
      customer_id: editing ? editingEvent.customer_id || "" : initialContext.customerId || "",
      contact_id: editing ? editingEvent.contact_id || "" : initialContext.contactId || "",
      quote_id: editing ? editingEvent.quote_id || "" : initialContext.quoteId || "",
      order_id: editing ? editingEvent.order_id || "" : initialContext.orderId || "",
      order_item_id: editing ? editingEvent.order_item_id || "" : initialContext.orderItemId || "",
      work_order_id: editing ? editingEvent.work_order_id || "" : initialContext.workOrderId || "",
      production_stage_id: editing ? editingEvent.production_stage_id || "" : initialContext.productionStageId || "",
      wrap_project_id: editing ? editingEvent.wrap_project_id || "" : initialContext.wrapProjectId || "",
      vehicle_inspection_id: editing ? editingEvent.vehicle_inspection_id || "" : initialContext.vehicleInspectionId || "",
      installation_id: editing ? editingEvent.installation_id || "" : initialContext.installationId || "",
      task_id: editing ? editingEvent.task_id || "" : initialContext.taskId || "",
      source_type: editing ? editingEvent.linked_source_type || editingEvent.source_type || "" : initialContext.sourceType || "",
      source_id: editing ? editingEvent.linked_source_id || "" : initialContext.sourceId || "",
      location: editing ? editingEvent.location || "" : "",
      description: editing ? editingEvent.description || "" : "",
    });
  }, [editing, editingEvent, initialContext, initialDate, open]);

  function setField(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  const proposedRange = useMemo(() => {
    if (!open || !form.date || !form.start || !form.end) return null;
    return {
      start_at: toLocalDateTime(form.date, form.start),
      end_at: toLocalDateTime(form.date, form.end),
    };
  }, [form.date, form.end, form.start, open]);

  const availabilityPayload = useMemo(() => proposedRange ? {
    ...proposedRange,
    event_id: editing ? eventId(editingEvent) : undefined,
    employee_id: clean(form.employee_id),
    assigned_employee_ids: form.assigned_employee_ids || [],
    reserved_equipment_ids: form.reserved_equipment_ids || [],
    reserved_vehicle_ids: form.reserved_vehicle_ids || [],
    reserved_resource_ids: form.reserved_resource_ids || [],
      location: clean(form.location),
      customer_id: clean(form.customer_id),
    } : null, [editing, editingEvent, form, proposedRange]);

  const { data: availability, isFetching: availabilityLoading } = useQuery({
    queryKey: ["calendar-availability", availabilityPayload],
    queryFn: async () => (await api.post("/calendar/availability", availabilityPayload)).data,
    enabled: Boolean(open && availabilityPayload),
  });

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
      assigned_employee_ids: form.assigned_employee_ids || [],
      reserved_equipment_ids: form.reserved_equipment_ids || [],
      reserved_vehicle_ids: form.reserved_vehicle_ids || [],
      reserved_resource_ids: form.reserved_resource_ids || [],
      customer_id: clean(form.customer_id),
      contact_id: clean(form.contact_id),
      quote_id: clean(form.quote_id),
      order_id: clean(form.order_id),
      order_item_id: clean(form.order_item_id),
      work_order_id: clean(form.work_order_id),
      production_stage_id: clean(form.production_stage_id),
      wrap_project_id: clean(form.wrap_project_id),
      vehicle_inspection_id: clean(form.vehicle_inspection_id),
      installation_id: clean(form.installation_id),
      task_id: clean(form.task_id),
      source_type: clean(form.source_type),
      source_id: clean(form.source_id),
      location: clean(form.location),
      description: clean(form.description),
      visibility: clean(form.employee_id) ? "employee" : "staff",
    };
    if (force) payload.conflict_override_reason = overrideReason;
    if (!force && availability?.conflicts?.length > 0) {
      setConflict(summarizeConflict({ conflicts: availability.conflicts }));
      return;
    }

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
          <div className="space-y-3 rounded-md border bg-slate-50 p-3" data-testid="calendar-people-resources-section">
            <div>
              <div className="text-sm font-semibold text-slate-950">People & Resources</div>
              <div className="text-xs text-muted-foreground">Assign crew members and reserve equipment, vehicles, or shop work areas.</div>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              <ResourceChecklist
                title="Crew"
                icon={Users}
                items={employees}
                selectedIds={form.assigned_employee_ids || []}
                onChange={(ids) => setField("assigned_employee_ids", ids)}
                testId="calendar-employee-selector"
                detail={(item) => item.role_label}
              />
              <ResourceChecklist
                title="Equipment"
                icon={Wrench}
                items={equipment}
                selectedIds={form.reserved_equipment_ids || []}
                onChange={(ids) => setField("reserved_equipment_ids", ids)}
                testId="calendar-equipment-selector"
                detail={(item) => item.category}
              />
              <ResourceChecklist
                title="Vehicles"
                icon={Truck}
                items={vehicles}
                selectedIds={form.reserved_vehicle_ids || []}
                onChange={(ids) => setField("reserved_vehicle_ids", ids)}
                testId="calendar-vehicle-selector"
                detail={(item) => item.location}
              />
              <ResourceChecklist
                title="Bays & Work Areas"
                icon={MapPin}
                items={resources}
                selectedIds={form.reserved_resource_ids || []}
                onChange={(ids) => setField("reserved_resource_ids", ids)}
                testId="calendar-resource-selector"
                detail={(item) => [item.resource_type, item.location].filter(Boolean).join(" • ")}
              />
            </div>
            {(form.assigned_employee_ids?.length || form.reserved_equipment_ids?.length || form.reserved_vehicle_ids?.length || form.reserved_resource_ids?.length) ? (
              <div className="rounded-md bg-white p-2 text-xs text-slate-700" data-testid="calendar-selected-resource-summary">
                {[
                  selectedLabel(employees, form.assigned_employee_ids || []),
                  selectedLabel(equipment, form.reserved_equipment_ids || []),
                  selectedLabel(vehicles, form.reserved_vehicle_ids || []),
                  selectedLabel(resources, form.reserved_resource_ids || []),
                ].filter(Boolean).join(" • ")}
              </div>
            ) : null}
            <AvailabilityPanel availability={availability} isLoading={availabilityLoading} />
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
          <div className="grid gap-3 sm:grid-cols-3" data-testid="calendar-linked-records-section">
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-customer">Linked customer</Label>
              <Input id="calendar-event-customer" value={form.customer_id || ""} onChange={(e) => setField("customer_id", e.target.value)} data-testid="calendar-event-customer-id" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-contact">Contact</Label>
              <Input id="calendar-event-contact" value={form.contact_id || ""} onChange={(e) => setField("contact_id", e.target.value)} data-testid="calendar-event-contact-id" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-quote">Quote</Label>
              <Input id="calendar-event-quote" value={form.quote_id || ""} onChange={(e) => setField("quote_id", e.target.value)} data-testid="calendar-event-quote-id" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-order">Order</Label>
              <Input id="calendar-event-order" value={form.order_id || ""} onChange={(e) => setField("order_id", e.target.value)} data-testid="calendar-event-order-id" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-order-item">Order item</Label>
              <Input id="calendar-event-order-item" value={form.order_item_id || ""} onChange={(e) => setField("order_item_id", e.target.value)} data-testid="calendar-event-order-item-id" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-work-order">Work Order</Label>
              <Input id="calendar-event-work-order" value={form.work_order_id || ""} onChange={(e) => setField("work_order_id", e.target.value)} data-testid="calendar-event-work-order-id" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-production-stage">Production stage</Label>
              <Input id="calendar-event-production-stage" value={form.production_stage_id || ""} onChange={(e) => setField("production_stage_id", e.target.value)} data-testid="calendar-event-production-stage-id" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-wrap-project">Wrap Project</Label>
              <Input id="calendar-event-wrap-project" value={form.wrap_project_id || ""} onChange={(e) => setField("wrap_project_id", e.target.value)} data-testid="calendar-event-wrap-project-id" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="calendar-event-source">Source record</Label>
              <Input id="calendar-event-source" value={form.source_id || ""} onChange={(e) => setField("source_id", e.target.value)} data-testid="calendar-event-source-id" />
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

function EventCard({ item, canManage, onOpen, onCancel, onComplete, onReopen }) {
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
        {assignmentText(item) && <div className="mt-1 truncate text-slate-700" data-testid={`shop-schedule-assignment-${item.source_id}`}>{assignmentText(item)}</div>}
        <div className="mt-1 flex flex-wrap items-center gap-1">
          <Badge variant="outline" className="bg-white/70 text-[10px]">{String(item.event_type || item.source_type).replace(/_/g, " ")}</Badge>
          {item.status && <Badge variant="outline" className="bg-white/70 text-[10px]">{String(item.status).replace(/_/g, " ")}</Badge>}
          {item.conflicts?.length > 0 && <Badge variant="outline" className="border-amber-300 bg-amber-100 text-[10px] text-amber-900">Conflict</Badge>}
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
      {canManage && item.allowed_actions?.includes("complete") && (
        <button
          type="button"
          className="ml-2 mt-1 text-[11px] font-medium text-emerald-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          onClick={() => onComplete(item)}
          data-testid={`shop-schedule-card-complete-${item.source_id}`}
        >
          <CheckCircle2 className="mr-1 inline size-3" />Complete
        </button>
      )}
      {canManage && item.allowed_actions?.includes("reopen") && (
        <button
          type="button"
          className="ml-2 mt-1 text-[11px] font-medium text-blue-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          onClick={() => onReopen(item)}
          data-testid={`shop-schedule-card-reopen-${item.source_id}`}
        >
          <RotateCcw className="mr-1 inline size-3" />Reopen
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
  const [equipmentFilter, setEquipmentFilter] = useState("all");
  const [vehicleFilter, setVehicleFilter] = useState("all");
  const [resourceFilter, setResourceFilter] = useState("all");
  const [attentionFilter, setAttentionFilter] = useState("all");
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
    contactId: query.get("contact_id") || "",
    quoteId: query.get("quote_id") || "",
    orderId: query.get("order_id") || "",
    orderItemId: query.get("order_item_id") || "",
    workOrderId: query.get("work_order_id") || "",
    productionStageId: query.get("production_stage_id") || "",
    wrapProjectId: query.get("wrap_project_id") || "",
    vehicleInspectionId: query.get("vehicle_inspection_id") || "",
    installationId: query.get("installation_id") || "",
    taskId: query.get("task_id") || "",
    sourceType: query.get("source_type") || "",
    sourceId: query.get("source_id") || "",
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

  const { data: equipmentData } = useQuery({
    queryKey: ["equipment-calendar"],
    queryFn: async () => (await api.get("/equipment", { params: { status: "active" } })).data,
  });
  const allEquipment = equipmentData?.items || [];
  const equipment = allEquipment.filter((item) => item.category !== "vehicle");
  const vehicles = allEquipment.filter((item) => item.category === "vehicle");

  const { data: resourceData } = useQuery({
    queryKey: ["calendar-resources"],
    queryFn: async () => (await api.get("/calendar/resources", { params: { status: "active" } })).data,
  });
  const resources = resourceData?.items || [];

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: [
      "calendar-feed",
      range.start_at,
      range.end_at,
      employeeFilter,
      equipmentFilter,
      vehicleFilter,
      resourceFilter,
      attentionFilter,
      typeFilter,
      initialContext.customerId,
      initialContext.quoteId,
      initialContext.orderId,
      initialContext.orderItemId,
      initialContext.workOrderId,
      initialContext.productionStageId,
      initialContext.wrapProjectId,
    ],
    queryFn: async () => (await api.get("/calendar/feed", {
      params: {
        ...range,
        employee_id: employeeFilter === "all" ? undefined : employeeFilter,
        equipment_id: equipmentFilter === "all" ? undefined : equipmentFilter,
        vehicle_id: vehicleFilter === "all" ? undefined : vehicleFilter,
        resource_id: resourceFilter === "all" ? undefined : resourceFilter,
        attention: attentionFilter === "all" ? undefined : attentionFilter,
        event_type: typeFilter === "all" ? undefined : typeFilter,
        customer_id: clean(initialContext.customerId),
        quote_id: clean(initialContext.quoteId),
        order_id: clean(initialContext.orderId),
        order_item_id: clean(initialContext.orderItemId),
        work_order_id: clean(initialContext.workOrderId),
        production_stage_id: clean(initialContext.productionStageId),
        wrap_project_id: clean(initialContext.wrapProjectId),
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
    assignedEmployees: new Set(operationalItems.flatMap((item) => item.assigned_employee_ids || (item.employee_id ? [item.employee_id] : []))).size,
    reservedEquipment: operationalItems.reduce((count, item) => count + (item.reserved_equipment_ids?.length || 0) + (item.reserved_vehicle_ids?.length || 0), 0),
    reservedResources: operationalItems.reduce((count, item) => count + (item.reserved_resource_ids?.length || 0), 0),
    conflicts: operationalItems.filter((item) => item.conflicts?.length).length,
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

  async function completeAppointment(item) {
    try {
      await api.post(`/calendar/events/${eventId(item)}/complete`, { outcome_note: "Completed from Shop Schedule" });
      toast.success("Appointment completed");
      refetch();
    } catch (err) {
      toast.error(extractError(err));
    }
  }

  async function reopenAppointment(item) {
    const reason = "Reopened from Shop Schedule";
    try {
      await api.post(`/calendar/events/${eventId(item)}/reopen`, { reason });
      toast.success("Appointment reopened");
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
    initialContext.quoteId && "Quote",
    initialContext.orderId && "Order",
    initialContext.orderItemId && "Order Item",
    initialContext.workOrderId && "Work Order",
    initialContext.productionStageId && "Production Stage",
    initialContext.wrapProjectId && "Wrap Project",
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
        <Card><CardContent className="flex items-center gap-3 p-4"><Users className="size-5 text-emerald-700" /><div><div className="text-xs text-muted-foreground">Assigned employees</div><div className="text-xl font-semibold">{counts.assignedEmployees}</div></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-3 p-4"><Wrench className="size-5 text-slate-700" /><div><div className="text-xs text-muted-foreground">Reserved resources</div><div className="text-xl font-semibold">{counts.reservedEquipment + counts.reservedResources}</div></div></CardContent></Card>
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
          <Select value={equipmentFilter} onValueChange={setEquipmentFilter}>
            <SelectTrigger className="w-48" data-testid="calendar-equipment-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All equipment</SelectItem>
              {equipment.map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={vehicleFilter} onValueChange={setVehicleFilter}>
            <SelectTrigger className="w-44" data-testid="calendar-vehicle-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All vehicles</SelectItem>
              {vehicles.map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={resourceFilter} onValueChange={setResourceFilter}>
            <SelectTrigger className="w-48" data-testid="calendar-resource-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All bays/areas</SelectItem>
              {resources.map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={attentionFilter} onValueChange={setAttentionFilter}>
            <SelectTrigger className="w-44" data-testid="calendar-attention-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All attention</SelectItem>
              <SelectItem value="conflicts">Conflicts only</SelectItem>
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
                {(byDay[day] || []).map((item) => (
                  <EventCard
                    key={item.id}
                    item={item}
                    canManage={canManageSchedule}
                    onOpen={openItem}
                    onCancel={cancelAppointment}
                    onComplete={completeAppointment}
                    onReopen={reopenAppointment}
                  />
                ))}
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
                    {assignmentText(item) && <div className="text-sm text-slate-700" data-testid={`shop-schedule-row-assignment-${item.source_id}`}>{assignmentText(item)}</div>}
                    <div className="mt-1 flex flex-wrap gap-1">
                      <Badge variant="outline">{String(item.event_type || item.source_type).replace(/_/g, " ")}</Badge>
                      {item.status && <Badge variant="outline">{String(item.status).replace(/_/g, " ")}</Badge>}
                      {item.conflicts?.length > 0 && <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-900">Conflict</Badge>}
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
                    {canManageSchedule && item.allowed_actions?.includes("complete") && (
                      <Button variant="ghost" size="sm" onClick={() => completeAppointment(item)} data-testid={`shop-schedule-complete-${item.source_id}`}>Complete</Button>
                    )}
                    {canManageSchedule && item.allowed_actions?.includes("reopen") && (
                      <Button variant="ghost" size="sm" onClick={() => reopenAppointment(item)} data-testid={`shop-schedule-reopen-${item.source_id}`}>Reopen</Button>
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
        equipment={equipment}
        vehicles={vehicles}
        resources={resources}
        onSaved={invalidateSchedule}
      />
    </div>
  );
}
