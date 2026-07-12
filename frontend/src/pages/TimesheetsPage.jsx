import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import StatusPill from "@/components/common/StatusPill";
import EmptyState from "@/components/common/EmptyState";
import { toast } from "sonner";
import { AlertTriangle, ChevronLeft, ChevronRight, Download, FileText, Pencil } from "lucide-react";
import { centsToDollarsString, formatClockTime, formatMinutes } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";

function isoDate(d) { return d.toISOString().slice(0, 10); }
function addDays(dateStr, n) { const d = new Date(dateStr + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return isoDate(d); }

function CorrectionDialog({ entry, onDone }) {
  const [open, setOpen] = useState(false);
  const [clockIn, setClockIn] = useState(entry.clock_in_at?.slice(0, 16) || "");
  const [clockOut, setClockOut] = useState(entry.clock_out_at?.slice(0, 16) || "");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = { reason };
      if (clockIn) payload.clock_in_at = new Date(clockIn).toISOString();
      if (clockOut) payload.clock_out_at = new Date(clockOut).toISOString();
      await api.post(`/time-clock/entries/${entry.id}/correct`, payload);
      toast.success("Time entry corrected");
      setOpen(false);
      onDone?.();
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="ghost" data-testid={`correct-entry-${entry.id}`}><Pencil className="size-3.5 mr-1" />Correct</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>Correct time entry</DialogTitle>
          <DialogDescription>Original values are preserved in the correction history.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5"><Label>Clock in</Label><Input type="datetime-local" value={clockIn} onChange={(e) => setClockIn(e.target.value)} data-testid="correction-clock-in-input" /></div>
          <div className="grid gap-1.5"><Label>Clock out</Label><Input type="datetime-local" value={clockOut} onChange={(e) => setClockOut(e.target.value)} data-testid="correction-clock-out-input" /></div>
          <div className="grid gap-1.5"><Label>Reason*</Label><Textarea required rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="correction-reason-input" /></div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy} data-testid="correction-submit-button">{busy ? "Saving…" : "Confirm correction"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RejectDialog({ onConfirm }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button size="sm" variant="outline" data-testid="timesheet-reject-button">Reject</Button></DialogTrigger>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader><DialogTitle>Reject timesheet</DialogTitle></DialogHeader>
        <div className="grid gap-3">
          <Textarea required rows={2} placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="timesheet-reject-reason-input" />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={() => { onConfirm(reason); setOpen(false); setReason(""); }} disabled={!reason} data-testid="timesheet-reject-confirm-button">Confirm reject</Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function WeeklyTimesheetView({ employeeId, canManage }) {
  const qc = useQueryClient();
  const [weekStart, setWeekStart] = useState(isoDate(new Date()));

  const { data: weekly, isLoading } = useQuery({
    queryKey: ["timesheet-weekly", employeeId, weekStart],
    queryFn: async () => (await api.get("/timesheets/weekly", { params: { week_start: weekStart, employee_id: employeeId || undefined } })).data,
  });
  const { data: entriesData } = useQuery({
    queryKey: ["time-entries-week", employeeId, weekly?.week_start, weekly?.week_end],
    queryFn: async () => (await api.get(employeeId ? "/time-clock/entries/all" : "/time-clock/entries", {
      params: { employee_id: employeeId || undefined, date_from: weekly?.week_start, date_to: weekly?.week_end },
    })).data,
    enabled: !!weekly,
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["timesheet-weekly"] });
    qc.invalidateQueries({ queryKey: ["time-entries-week"] });
  }

  async function approve() {
    try { await api.post(`/timesheets/${weekly.id}/approve`); toast.success("Timesheet approved"); refresh(); }
    catch (err) { toast.error(extractError(err)); }
  }
  async function reject(reason) {
    try { await api.post(`/timesheets/${weekly.id}/reject`, { reason }); toast.success("Timesheet rejected"); refresh(); }
    catch (err) { toast.error(extractError(err)); }
  }
  async function reopen() {
    try { await api.post(`/timesheets/${weekly.id}/reopen`, { reason: "Reopened for correction" }); toast.success("Timesheet reopened"); refresh(); }
    catch (err) { toast.error(extractError(err)); }
  }

  const entries = entriesData?.items || [];

  return (
    <div className="space-y-3" data-testid="weekly-timesheet-view">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <Button size="icon" variant="ghost" onClick={() => setWeekStart(addDays(weekStart, -7))} data-testid="timesheet-prev-week"><ChevronLeft className="size-4" /></Button>
          <div className="text-sm font-medium w-48 text-center" data-testid="timesheet-week-range">
            {weekly ? `${weekly.week_start} – ${weekly.week_end}` : "…"}
          </div>
          <Button size="icon" variant="ghost" onClick={() => setWeekStart(addDays(weekStart, 7))} data-testid="timesheet-next-week"><ChevronRight className="size-4" /></Button>
        </div>
        {weekly && <StatusPill kind="announcement" value={weekly.status === "pending" ? "draft" : weekly.status === "approved" ? "published" : "expired"} />}
      </div>

      {isLoading || !weekly ? <div className="text-sm text-muted-foreground">Loading…</div> : (
        <>
          <Card>
            <CardContent className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div><div className="text-xl font-semibold tabular-nums" data-testid="weekly-worked-minutes">{formatMinutes(weekly.worked_minutes)}</div><div className="text-xs text-muted-foreground">Worked</div></div>
              <div><div className="text-xl font-semibold tabular-nums">{formatMinutes(weekly.break_minutes)}</div><div className="text-xs text-muted-foreground">Break</div></div>
              <div><div className="text-xl font-semibold tabular-nums">{formatMinutes(weekly.regular_minutes)} <span className="text-xs text-muted-foreground">(+{formatMinutes(weekly.overtime_minutes)} OT)</span></div><div className="text-xs text-muted-foreground">Regular / OT</div></div>
              <div><div className="text-xl font-semibold tabular-nums" data-testid="weekly-estimated-pay">{centsToDollarsString(weekly.estimated_gross_cents)}</div><div className="text-xs text-muted-foreground">Estimated pay (live rate)</div></div>
            </CardContent>
            {weekly.incomplete_entry_count > 0 && (
              <CardContent className="pt-0 pb-4">
                <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 rounded-md px-3 py-2" data-testid="incomplete-entries-warning">
                  <AlertTriangle className="size-4" />{weekly.incomplete_entry_count} incomplete entr{weekly.incomplete_entry_count === 1 ? "y" : "ies"} (missing clock-out)
                  {weekly.missed_clock_count > 0 && ` · ${weekly.missed_clock_count} likely missed clock-out`}
                </div>
              </CardContent>
            )}
            {canManage && (
              <CardContent className="pt-0 pb-4 flex items-center gap-2">
                {weekly.status === "pending" && (
                  <>
                    <Button size="sm" onClick={approve} data-testid="timesheet-approve-button">Approve</Button>
                    <RejectDialog onConfirm={reject} />
                  </>
                )}
                {(weekly.status === "approved" || weekly.status === "rejected") && (
                  <Button size="sm" variant="outline" onClick={reopen} data-testid="timesheet-reopen-button">Reopen</Button>
                )}
                <Button size="sm" variant="ghost" disabled title="Export becomes available once Payroll (Phase 8d) lands" data-testid="timesheet-export-button">
                  <Download className="size-3.5 mr-1" />Export
                </Button>
              </CardContent>
            )}
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-sm">Entries</CardTitle></CardHeader>
            <CardContent className="divide-y">
              {entries.length === 0 ? (
                <EmptyState icon={FileText} title="No time entries this week" description="Nothing clocked yet for this range." />
              ) : entries.map((e) => (
                <div key={e.id} className="py-2.5 flex items-center justify-between gap-3" data-testid={`time-entry-row-${e.id}`}>
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{e.work_date} · {formatClockTime(e.clock_in_at)} – {e.clock_out_at ? formatClockTime(e.clock_out_at) : "—"}</div>
                    <div className="text-xs text-muted-foreground">{formatMinutes(e.worked_minutes)} worked · {formatMinutes(e.total_break_minutes)} break {e.corrections?.length > 0 && `· corrected ${e.corrections.length}x`}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusPill kind="employee" value={e.status === "open" ? "suspended" : e.status === "approved" ? "active" : e.status === "voided" ? "terminated" : "inactive"} />
                    {canManage && e.status !== "approved" && e.status !== "voided" && <CorrectionDialog entry={e} onDone={refresh} />}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function TeamReviewTab() {
  const [employeeId, setEmployeeId] = useState("");
  const { data: employees } = useQuery({ queryKey: ["employees", ""], queryFn: async () => (await api.get("/employees")).data });
  const { data: pending } = useQuery({ queryKey: ["timesheets-pending"], queryFn: async () => (await api.get("/timesheets/pending-review")).data });

  const items = employees?.items || [];

  return (
    <div className="space-y-4">
      {pending?.items?.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Awaiting review</CardTitle></CardHeader>
          <CardContent className="divide-y" data-testid="timesheets-pending-list">
            {pending.items.map((t) => {
              const emp = items.find((e) => e.id === t.employee_id);
              return (
                <button key={t.id} className="w-full text-left py-2 flex items-center justify-between hover:bg-muted/40 rounded px-2 -mx-2" onClick={() => setEmployeeId(t.employee_id)} data-testid={`pending-review-row-${t.id}`}>
                  <span className="text-sm">{emp?.name || t.employee_id} — {t.week_start} to {t.week_end}</span>
                  <span className="text-sm text-muted-foreground">{formatMinutes(t.worked_minutes)}</span>
                </button>
              );
            })}
          </CardContent>
        </Card>
      )}
      <div className="max-w-xs">
        <Select value={employeeId} onValueChange={setEmployeeId}>
          <SelectTrigger data-testid="timesheet-employee-select"><SelectValue placeholder="Choose an employee" /></SelectTrigger>
          <SelectContent>
            {items.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      {employeeId ? <WeeklyTimesheetView employeeId={employeeId} canManage /> : (
        <EmptyState icon={FileText} title="Select an employee" description="Choose an employee above to view and manage their timesheet." />
      )}
    </div>
  );
}

export default function TimesheetsPage() {
  const { hasPerm } = useAuth();
  const canReviewOthers = hasPerm("timesheet:read") || hasPerm("timesheet:manage");
  return (
    <div className="space-y-4" data-testid="timesheets-page">
      <PageHeader title="Timesheets" subtitle="Daily, weekly, and monthly time totals." />
      {canReviewOthers ? (
        <Tabs defaultValue="team" data-testid="timesheets-tabs">
          <TabsList>
            <TabsTrigger value="mine" data-testid="timesheets-tab-mine">My Timesheet</TabsTrigger>
            <TabsTrigger value="team" data-testid="timesheets-tab-team">Team Review</TabsTrigger>
          </TabsList>
          <TabsContent value="mine"><WeeklyTimesheetView employeeId={null} canManage={false} /></TabsContent>
          <TabsContent value="team"><TeamReviewTab /></TabsContent>
        </Tabs>
      ) : (
        <WeeklyTimesheetView employeeId={null} canManage={false} />
      )}
    </div>
  );
}
