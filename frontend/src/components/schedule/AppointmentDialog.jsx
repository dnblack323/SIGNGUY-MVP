/**
 * Create / edit an operational appointment in the shared calendar (unchanged
 * MVP behavior: validation, availability check, conflict warning and
 * authorized override). Moved from ShopSchedulePage for F3.
 */
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { AlertCircle, MapPin, Truck, Users, Wrench, X } from "lucide-react";
import { localDateKey } from "@/components/schedule/scheduleModel";

const TODAY = () => localDateKey();

export const EVENT_TYPE_LABELS = {
  consultation: "Consultation",
  site_survey: "Site Survey",
  vehicle_dropoff: "Vehicle Drop-off",
  vehicle_pickup: "Vehicle Pickup",
  installation: "Installation",
  customer_meeting: "Customer Meeting",
  production_milestone: "Production Milestone",
  custom: "Custom",
};
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
export function clean(value) {
  return value && value !== "none" ? value : undefined;
}

export function eventId(item) {
  return item?.source_id || item?.id?.replace(/^calendar_event:/, "");
}

export function itemTitle(item) {
  return item?.display_title || item?.title || "Scheduled item";
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

export default function AppointmentDialog({ open, onOpenChange, employees, equipment, vehicles, resources, initialDate, initialContext, editingEvent, onSaved }) {
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
      <DialogContent className="max-h-[90dvh] max-w-3xl overflow-y-auto" data-testid="calendar-appointment-dialog">
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
