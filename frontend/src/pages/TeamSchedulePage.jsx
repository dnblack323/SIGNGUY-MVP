import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import EmptyState from "@/components/common/EmptyState";
import { toast } from "sonner";
import { CalendarDays, ChevronLeft, ChevronRight, Copy, Plus, Send, X } from "lucide-react";

function isoDate(d) { return d.toISOString().slice(0, 10); }
function addDays(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return isoDate(d);
}
function fmtTime(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); } catch { return ""; }
}
// 24-hour "HH:MM" — required by <input type="time"> value/prefill (fmtTime's
// 12-hour "09:00 AM" format is invalid for that input and silently renders blank).
function to24hTime(iso) {
  if (!iso) return "";
  try { return new Date(iso).toISOString().slice(11, 16); } catch { return ""; }
}
function combineDateTime(dateStr, timeStr) {
  return new Date(`${dateStr}T${timeStr}:00Z`).toISOString();
}
function currentSaturday() {
  const now = new Date();
  const dow = now.getUTCDay(); // 0=Sun..6=Sat
  const diff = (dow + 1) % 7; // days since last Saturday
  const sat = new Date(now);
  sat.setUTCDate(now.getUTCDate() - diff);
  return isoDate(sat);
}

const DAY_LABELS = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"];

function ShiftForm({ employees, initial, onSubmit, onCancel, busy }) {
  const [employeeId, setEmployeeId] = useState(initial?.employee_id || "");
  const [shiftDate, setShiftDate] = useState(initial?.shift_date || "");
  const [startTime, setStartTime] = useState(initial?.start_at ? to24hTime(initial.start_at) : "09:00");
  const [endTime, setEndTime] = useState(initial?.end_at ? to24hTime(initial.end_at) : "17:00");
  const [title, setTitle] = useState(initial?.title || "");
  const [location, setLocation] = useState(initial?.location || "");
  const [notes, setNotes] = useState(initial?.notes || "");
  const [conflict, setConflict] = useState(null);
  const [overrideReason, setOverrideReason] = useState("");

  function toStartEnd() {
    return { start_at: combineDateTime(shiftDate, startTime), end_at: combineDateTime(shiftDate, endTime) };
  }

  async function submit(force) {
    if (!employeeId || !shiftDate) return toast.error("Employee and date are required");
    if (!startTime || !endTime) return toast.error("Start and end time are required");
    const { start_at, end_at } = toStartEnd();
    const payload = { employee_id: employeeId, shift_date: shiftDate, start_at, end_at, title, location, notes };
    if (force && overrideReason) payload.override_reason = overrideReason;
    try {
      await onSubmit(payload);
      setConflict(null);
    } catch (err) {
      const detail = err?.response?.data?.detail || "";
      if (detail.startsWith("availability_conflict:")) {
        setConflict(detail.replace("availability_conflict:", "").trim());
      } else {
        toast.error(extractError(err));
      }
    }
  }

  return (
    <div className="space-y-3" data-testid="shift-form">
      <div className="grid gap-1.5">
        <Label>Employee</Label>
        <Select value={employeeId} onValueChange={setEmployeeId} disabled={!!initial?.id}>
          <SelectTrigger data-testid="shift-form-employee"><SelectValue placeholder="Select employee" /></SelectTrigger>
          <SelectContent>
            {employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="grid gap-1.5"><Label className="text-xs">Date</Label><Input type="date" value={shiftDate} onChange={(e) => setShiftDate(e.target.value)} data-testid="shift-form-date" /></div>
        <div className="grid gap-1.5"><Label className="text-xs">Start</Label><Input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} data-testid="shift-form-start" /></div>
        <div className="grid gap-1.5"><Label className="text-xs">End</Label><Input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} data-testid="shift-form-end" /></div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5"><Label className="text-xs">Title</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} data-testid="shift-form-title" /></div>
        <div className="grid gap-1.5"><Label className="text-xs">Location</Label><Input value={location} onChange={(e) => setLocation(e.target.value)} data-testid="shift-form-location" /></div>
      </div>
      <div className="grid gap-1.5"><Label className="text-xs">Notes</Label><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="shift-form-notes" rows={2} /></div>
      {conflict && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 space-y-2" data-testid="shift-conflict-warning">
          <div className="text-sm text-amber-800">Availability conflict: {conflict}</div>
          <Label className="text-xs">Override reason (required to proceed)</Label>
          <Input value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} data-testid="shift-form-override-reason" />
          <Button size="sm" onClick={() => submit(true)} disabled={busy || !overrideReason} data-testid="shift-form-override-submit">
            Save anyway
          </Button>
        </div>
      )}
      <DialogFooter>
        <Button variant="outline" onClick={onCancel} data-testid="shift-form-cancel">Cancel</Button>
        <Button onClick={() => submit(false)} disabled={busy} data-testid="shift-form-submit">Save</Button>
      </DialogFooter>
    </div>
  );
}

export default function TeamSchedulePage() {
  const qc = useQueryClient();
  const [weekStart, setWeekStart] = useState(currentSaturday());
  const [employeeFilter, setEmployeeFilter] = useState("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingShift, setEditingShift] = useState(null);
  const [busy, setBusy] = useState(false);

  const { data: employeesData } = useQuery({
    queryKey: ["employees-active-schedule"],
    queryFn: async () => (await api.get("/employees", { params: { status: "active" } })).data,
  });
  const employees = employeesData?.items || [];

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["team-schedule", weekStart],
    queryFn: async () => (await api.get("/schedules", { params: { period_start: weekStart } })).data,
  });
  const schedule = data?.schedule;
  const shifts = data?.shifts || [];

  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);

  const visibleEmployees = employeeFilter === "all" ? employees : employees.filter((e) => e.id === employeeFilter);

  const shiftsByEmpDay = useMemo(() => {
    const m = {};
    shifts.forEach((s) => {
      const key = `${s.employee_id}|${s.shift_date}`;
      (m[key] = m[key] || []).push(s);
    });
    return m;
  }, [shifts]);

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["team-schedule", weekStart] });
    qc.invalidateQueries({ queryKey: ["team-dashboard"] });
  }

  async function createShift(payload) {
    setBusy(true);
    try {
      await api.post(`/schedules/${schedule.id}/shifts`, payload);
      toast.success("Shift added");
      setDialogOpen(false); setEditingShift(null);
      invalidate();
    } finally { setBusy(false); }
  }

  async function updateShift(payload) {
    setBusy(true);
    try {
      await api.patch(`/schedule-shifts/${editingShift.id}`, payload);
      toast.success("Shift updated");
      setDialogOpen(false); setEditingShift(null);
      invalidate();
    } finally { setBusy(false); }
  }

  async function cancelShift(shift) {
    try {
      await api.post(`/schedule-shifts/${shift.id}/cancel`, {});
      toast.success("Shift cancelled");
      invalidate();
    } catch (err) { toast.error(extractError(err)); }
  }

  async function copyWeek() {
    const target = addDays(weekStart, 7);
    try {
      await api.post(`/schedules/${schedule.id}/copy-week`, { target_period_start: target });
      toast.success(`Copied to week of ${target}`);
      invalidate();
    } catch (err) { toast.error(extractError(err)); }
  }

  async function publish() {
    try {
      await api.post(`/schedules/${schedule.id}/publish`);
      toast.success("Schedule published — employees notified");
      refetch();
    } catch (err) { toast.error(extractError(err)); }
  }

  async function republish() {
    try {
      await api.post(`/schedules/${schedule.id}/republish`);
      toast.success("Schedule republished — affected employees notified");
      refetch();
    } catch (err) { toast.error(extractError(err)); }
  }

  return (
    <div className="space-y-4" data-testid="team-schedule-page">
      <PageHeader
        title="Team Schedule"
        subtitle="Build and publish this week's shifts."
        actions={
          <div className="flex items-center gap-2">
            {schedule && (
              <Badge variant={schedule.status === "published" ? "default" : "outline"} data-testid="schedule-status-badge">
                {schedule.status}{schedule.status === "published" ? ` v${schedule.version}` : ""}
              </Badge>
            )}
            <Button variant="outline" size="sm" onClick={copyWeek} disabled={!schedule} data-testid="copy-week-button">
              <Copy className="size-4 mr-1" />Copy to next week
            </Button>
            {schedule?.status === "draft" ? (
              <Button size="sm" onClick={publish} disabled={!schedule} data-testid="publish-schedule-button">
                <Send className="size-4 mr-1" />Publish
              </Button>
            ) : (
              <Button size="sm" variant="outline" onClick={republish} disabled={!schedule} data-testid="republish-schedule-button">
                <Send className="size-4 mr-1" />Republish
              </Button>
            )}
            <Button size="sm" onClick={() => { setEditingShift(null); setDialogOpen(true); }} data-testid="add-shift-button">
              <Plus className="size-4 mr-1" />Add Shift
            </Button>
          </div>
        }
      />

      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => setWeekStart(addDays(weekStart, -7))} data-testid="prev-week-button">
          <ChevronLeft className="size-4" />
        </Button>
        <div className="text-sm font-medium flex items-center gap-1" data-testid="week-range-label">
          <CalendarDays className="size-4" />{weekStart} – {addDays(weekStart, 6)}
        </div>
        <Button variant="ghost" size="icon" onClick={() => setWeekStart(addDays(weekStart, 7))} data-testid="next-week-button">
          <ChevronRight className="size-4" />
        </Button>
        <Select value={employeeFilter} onValueChange={setEmployeeFilter}>
          <SelectTrigger className="w-56" data-testid="schedule-employee-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All employees</SelectItem>
            {employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : visibleEmployees.length === 0 ? (
        <EmptyState icon={CalendarDays} title="No employees to schedule" description="Add active employees under Team & Workflow → Employees first." />
      ) : (
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm" data-testid="schedule-grid">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2 font-medium min-w-[140px]">Employee</th>
                  {days.map((d, i) => (
                    <th key={d} className="text-left p-2 font-medium min-w-[130px]">{DAY_LABELS[i]}<div className="text-xs text-muted-foreground">{d.slice(5)}</div></th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleEmployees.map((emp) => (
                  <tr key={emp.id} className="border-b last:border-0" data-testid={`schedule-row-${emp.id}`}>
                    <td className="p-2 font-medium align-top">{emp.name}</td>
                    {days.map((d) => {
                      const cellShifts = shiftsByEmpDay[`${emp.id}|${d}`] || [];
                      return (
                        <td key={d} className="p-2 align-top space-y-1">
                          {cellShifts.filter((s) => s.status !== "cancelled").map((s) => (
                            <div key={s.id} className="rounded-md border bg-muted/40 p-1.5 group" data-testid={`shift-chip-${s.id}`}>
                              <button
                                type="button"
                                className="text-left w-full"
                                onClick={() => { setEditingShift(s); setDialogOpen(true); }}
                                data-testid={`shift-chip-edit-${s.id}`}
                              >
                                <div className="text-xs font-medium">{fmtTime(s.start_at)}–{fmtTime(s.end_at)}</div>
                                {s.location && <div className="text-xs text-muted-foreground">{s.location}</div>}
                                {s.conflict_override_reason && <Badge variant="outline" className="mt-1 text-[10px]">override</Badge>}
                              </button>
                              <button
                                type="button"
                                className="text-[10px] text-rose-600 hover:underline"
                                onClick={() => cancelShift(s)}
                                data-testid={`shift-chip-cancel-${s.id}`}
                              >
                                <X className="inline size-3" /> cancel
                              </button>
                            </div>
                          ))}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) setEditingShift(null); }}>
        <DialogContent data-testid="shift-dialog">
          <DialogHeader><DialogTitle>{editingShift ? "Edit Shift" : "Add Shift"}</DialogTitle></DialogHeader>
          <ShiftForm
            employees={employees}
            initial={editingShift}
            busy={busy}
            onSubmit={editingShift ? updateShift : createShift}
            onCancel={() => { setDialogOpen(false); setEditingShift(null); }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
