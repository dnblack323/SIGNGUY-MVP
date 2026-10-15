/**
 * F3 — Shop Schedule (approved Price Lab Schedule layout on MVP's calendar).
 *
 * Month and Single Day views, All / Production / Installation filters,
 * previous / Today / next navigation, Quick Add, right rail, and the existing
 * MVP appointment dialog (resources, availability, conflicts, overrides).
 * The shared calendar service stays the only scheduling store.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, Filter, Plus, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import AppointmentDialog, { EVENT_TYPE_LABELS, clean, eventId } from "@/components/schedule/AppointmentDialog";
import { DayView, EventDetailsDialog, MonthView, ScheduleRail, TypeDot } from "@/components/schedule/ScheduleViews";
import {
  SCHEDULE_FILTERS,
  SCHEDULE_TYPES,
  addLocalDays,
  addLocalMonths,
  fullDateLabel,
  groupByDate,
  isDateKey,
  localDateKey,
  monthLabel,
  rangeForView,
  scheduleType,
  typesForFilter,
} from "@/components/schedule/scheduleModel";

// Team shifts and absences belong to Team Schedule, not the operational Shop Schedule.
const OPERATIONAL_SOURCE_TYPES = new Set(["calendar_event", "task", "production_stage"]);
// Older links (ribbon, other pages) used calendar / agenda / appointments.
const LEGACY_VIEWS = { calendar: "month", agenda: "day", appointments: "day" };
const LANE_EVENT_TYPE = { production: "production_milestone", installation: "installation", appointment: "customer_meeting", pickup_delivery: "vehicle_pickup" };

export default function ShopSchedulePage() {
  const qc = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  const { hasPerm } = useAuth();
  const canManageSchedule = hasPerm("schedule:manage");
  const query = useMemo(() => new URLSearchParams(location.search || ""), [location.search]);

  const rawView = query.get("view");
  const view = rawView === "day" || rawView === "month" ? rawView : LEGACY_VIEWS[rawView] || "month";
  const rawDate = query.get("date");
  const selectedDate = isDateKey(rawDate) ? rawDate : localDateKey();
  const typeFilter = SCHEDULE_FILTERS.some((f) => f.key === query.get("type")) ? query.get("type") : "all";

  const [enabledTypes, setEnabledTypes] = useState(SCHEDULE_TYPES.map((type) => type.key));
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [employeeFilter, setEmployeeFilter] = useState("all");
  const [equipmentFilter, setEquipmentFilter] = useState("all");
  const [vehicleFilter, setVehicleFilter] = useState("all");
  const [resourceFilter, setResourceFilter] = useState("all");
  const [attentionFilter, setAttentionFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [quickAddType, setQuickAddType] = useState(null);
  const [detailsItem, setDetailsItem] = useState(null);

  function setQuery(patch, { replace = false } = {}) {
    const next = new URLSearchParams(location.search || "");
    Object.entries(patch).forEach(([key, value]) => {
      if (value === null || value === undefined || value === "") next.delete(key);
      else next.set(key, value);
    });
    next.delete("new");
    navigate(`/shop-schedule${next.toString() ? `?${next.toString()}` : ""}`, { replace });
  }

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
    eventType: EVENT_TYPE_LABELS[quickAddType] ? quickAddType : EVENT_TYPE_LABELS[query.get("type")] ? query.get("type") : "customer_meeting",
    title: query.get("title") || "",
    date: isDateKey(rawDate) ? rawDate : selectedDate,
  }), [query, quickAddType, rawDate, selectedDate]);

  const range = useMemo(() => rangeForView(view, selectedDate), [view, selectedDate]);

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

  const feedParams = {
    ...range,
    limit: 500,
    window_first: true,
    employee_id: employeeFilter === "all" ? undefined : employeeFilter,
    equipment_id: equipmentFilter === "all" ? undefined : equipmentFilter,
    vehicle_id: vehicleFilter === "all" ? undefined : vehicleFilter,
    resource_id: resourceFilter === "all" ? undefined : resourceFilter,
    attention: attentionFilter === "all" ? undefined : attentionFilter,
    customer_id: clean(initialContext.customerId),
    quote_id: clean(initialContext.quoteId),
    order_id: clean(initialContext.orderId),
    order_item_id: clean(initialContext.orderItemId),
    work_order_id: clean(initialContext.workOrderId),
    production_stage_id: clean(initialContext.productionStageId),
    wrap_project_id: clean(initialContext.wrapProjectId),
  };
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["calendar-feed", feedParams],
    queryFn: async () => (await api.get("/calendar/feed", { params: feedParams })).data,
  });

  const filterTypes = typesForFilter(typeFilter);
  const shownTypes = filterTypes.filter((type) => enabledTypes.includes(type));
  const items = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (data?.items || [])
      .filter((item) => OPERATIONAL_SOURCE_TYPES.has(item.source_type))
      .filter((item) => item.event_type !== "internal_meeting")
      .filter((item) => shownTypes.includes(scheduleType(item)))
      .filter((item) => !q || `${item.title || ""} ${item.display_title || ""} ${item.location || ""} ${item.status || ""}`.toLowerCase().includes(q));
  }, [data, search, shownTypes]);
  const byDate = useMemo(() => groupByDate(items), [items]);
  const dayItems = byDate.get(selectedDate) || [];

  function movePeriod(amount) {
    setQuery({ date: view === "month" ? addLocalMonths(selectedDate, amount) : addLocalDays(selectedDate, amount) });
  }

  function openQuickAdd(laneType = null) {
    setEditingEvent(null);
    setQuickAddType(laneType ? LANE_EVENT_TYPE[laneType] || null : null);
    setDialogOpen(true);
  }

  function setDialogState(open) {
    setDialogOpen(open);
    if (!open) {
      setEditingEvent(null);
      setQuickAddType(null);
      if (query.get("new") === "1") setQuery({}, { replace: true });
    }
  }

  function openItem(item) {
    setDetailsItem(item);
  }

  async function lifecycle(item, action, body, message) {
    try {
      await api.post(`/calendar/events/${eventId(item)}/${action}`, body);
      toast.success(message);
      setDetailsItem(null);
      refetch();
    } catch (err) {
      toast.error(extractError(err));
    }
  }

  function invalidateSchedule() {
    refetch();
    qc.invalidateQueries({ queryKey: ["calendar-feed"] });
  }

  const linkedContext = [
    initialContext.customerId && "Customer",
    initialContext.quoteId && "Quote",
    initialContext.orderId && "Order",
    initialContext.orderItemId && "Order Item",
    initialContext.workOrderId && "Work Order",
    initialContext.productionStageId && "Production Stage",
    initialContext.wrapProjectId && "Wrap Project",
  ].filter(Boolean);
  const resourceFiltersActive = [employeeFilter, equipmentFilter, vehicleFilter, resourceFilter, attentionFilter].some((v) => v !== "all") || search;
  const isToday = selectedDate === localDateKey();

  return (
    <div className="space-y-3" data-testid="shop-schedule-page">
      <header className="flex flex-wrap items-center gap-3 rounded-lg border bg-card px-4 py-3" data-testid="schedule-toolbar">
        <div className="mr-auto">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Shop Operations</div>
          <h1 className="text-xl font-semibold leading-tight">Shop Schedule</h1>
        </div>
        <div className="flex items-center gap-1.5" aria-label="Schedule date controls">
          <Button variant="outline" size="icon" className="size-8" onClick={() => movePeriod(-1)} aria-label={view === "month" ? "Previous month" : "Previous day"}><ChevronLeft className="size-4" /></Button>
          <Button variant="outline" size="sm" onClick={() => setQuery({ date: localDateKey() })} data-testid="shop-schedule-today">Today</Button>
          <Button variant="outline" size="icon" className="size-8" onClick={() => movePeriod(1)} aria-label={view === "month" ? "Next month" : "Next day"}><ChevronRight className="size-4" /></Button>
          <strong className="ml-2 min-w-[11rem] text-sm" data-testid="schedule-date-label">{view === "month" ? monthLabel(selectedDate) : fullDateLabel(selectedDate)}</strong>
          {rawDate && !isToday && (
            <Button variant="ghost" size="sm" className="h-8 px-2 text-xs" onClick={() => setQuery({ date: null })} data-testid="schedule-clear-date">
              <X className="mr-1 size-3.5" />Clear date
            </Button>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant={filtersOpen || resourceFiltersActive ? "secondary" : "outline"} size="sm" onClick={() => setFiltersOpen((v) => !v)} aria-expanded={filtersOpen} data-testid="schedule-filters-toggle">
            <Filter className="mr-1 size-4" />Filters{resourceFiltersActive ? " •" : ""}
          </Button>
          <div className="inline-flex rounded-md border p-0.5" role="tablist" aria-label="Schedule view" data-testid="shop-schedule-view-tabs">
            {["day", "month"].map((key) => (
              <button key={key} type="button" role="tab" aria-selected={view === key}
                className={cn("h-7 rounded px-3 text-sm font-medium", view === key ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-muted")}
                onClick={() => setQuery({ view: key })} data-testid={`shop-schedule-view-${key}`}>
                {key === "day" ? "Day" : "Month"}
              </button>
            ))}
          </div>
          <Button asChild variant="ghost" size="sm"><Link to="/team/schedule">Team Schedule</Link></Button>
          {canManageSchedule && (
            <Button size="sm" onClick={() => openQuickAdd()} data-testid="calendar-create-appointment"><Plus className="mr-1 size-4" />Add to Schedule</Button>
          )}
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="Schedule filter" data-testid="schedule-type-filter">
        {SCHEDULE_FILTERS.map((filter) => (
          <button key={filter.key} type="button" role="tab" aria-selected={typeFilter === filter.key}
            className={cn("inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-sm font-medium", typeFilter === filter.key ? "border-slate-950 bg-slate-950 text-white" : "bg-card hover:bg-muted")}
            onClick={() => setQuery({ type: filter.key === "all" ? null : filter.key })} data-testid={`schedule-filter-${filter.key}`}>
            {filter.key !== "all" && <TypeDot type={filter.key} />}{filter.label}
          </button>
        ))}
        {linkedContext.length > 0 && (
          <div className="ml-2 flex flex-wrap gap-1 text-xs" data-testid="shop-schedule-linked-filter">
            {linkedContext.map((label) => <Badge key={label} variant="outline">{label} context</Badge>)}
          </div>
        )}
      </div>

      {filtersOpen && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-card p-3" data-testid="schedule-filters-panel">
          <div className="relative">
            <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
            <Input className="h-9 w-56 pl-8" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search schedule" data-testid="shop-schedule-search" />
          </div>
          <Select value={employeeFilter} onValueChange={setEmployeeFilter}>
            <SelectTrigger className="h-9 w-48" data-testid="calendar-employee-filter"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All employees</SelectItem>{employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={equipmentFilter} onValueChange={setEquipmentFilter}>
            <SelectTrigger className="h-9 w-44" data-testid="calendar-equipment-filter"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All equipment</SelectItem>{equipment.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={vehicleFilter} onValueChange={setVehicleFilter}>
            <SelectTrigger className="h-9 w-40" data-testid="calendar-vehicle-filter"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All vehicles</SelectItem>{vehicles.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={resourceFilter} onValueChange={setResourceFilter}>
            <SelectTrigger className="h-9 w-44" data-testid="calendar-resource-filter"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All bays / areas</SelectItem>{resources.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={attentionFilter} onValueChange={setAttentionFilter}>
            <SelectTrigger className="h-9 w-40" data-testid="calendar-attention-filter"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All attention</SelectItem><SelectItem value="conflicts">Conflicts only</SelectItem></SelectContent>
          </Select>
        </div>
      )}

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_260px]">
        <main className="min-w-0">
          {isLoading ? (
            <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground" data-testid="shop-schedule-loading">Loading schedule…</div>
          ) : isError ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" data-testid="shop-schedule-error">{extractError(error)}</div>
          ) : view === "month" ? (
            <MonthView dateKey={selectedDate} byDate={byDate} onOpenDay={(date, type) => setQuery({ view: "day", date, ...(type && SCHEDULE_FILTERS.some((f) => f.key === type) ? { type } : {}) })} />
          ) : (
            <DayView dateKey={selectedDate} items={dayItems} lanes={shownTypes} onOpen={openItem} onCreateAt={canManageSchedule ? openQuickAdd : undefined} />
          )}
        </main>
        <ScheduleRail
          dateKey={selectedDate}
          byDate={byDate}
          enabledTypes={enabledTypes}
          onToggleType={(type) => setEnabledTypes((current) => (current.includes(type) ? current.filter((t) => t !== type) : [...current, type]))}
          onSelectDate={(date) => setQuery({ date })}
          onOpenDay={(date) => setQuery({ view: "day", date })}
        />
      </div>

      <EventDetailsDialog
        item={detailsItem}
        open={Boolean(detailsItem)}
        onOpenChange={(open) => !open && setDetailsItem(null)}
        canManage={canManageSchedule}
        onEdit={(item) => { setDetailsItem(null); setEditingEvent(item); setDialogOpen(true); }}
        onComplete={(item) => lifecycle(item, "complete", { outcome_note: "Completed from Shop Schedule" }, "Appointment completed")}
        onCancel={(item) => lifecycle(item, "cancel", { reason: "Canceled from Shop Schedule" }, "Appointment canceled")}
        onReopen={(item) => lifecycle(item, "reopen", { reason: "Reopened from Shop Schedule" }, "Appointment reopened")}
      />
      <AppointmentDialog
        open={dialogOpen}
        onOpenChange={setDialogState}
        employees={employees}
        initialDate={selectedDate}
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
