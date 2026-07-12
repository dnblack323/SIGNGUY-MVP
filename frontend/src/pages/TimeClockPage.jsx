import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import StatusPill from "@/components/common/StatusPill";
import EmptyState from "@/components/common/EmptyState";
import { toast } from "sonner";
import { Clock, Coffee, LogIn, LogOut, Play, Square, Users } from "lucide-react";
import { formatClockTime, formatMinutes } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";

function useTicker() {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

function elapsedMinutes(startIso, nowMs) {
  if (!startIso) return 0;
  return Math.max(0, Math.floor((nowMs - new Date(startIso).getTime()) / 60000));
}

function activeBreak(entry) {
  return (entry?.breaks || []).find((b) => !b.end_at);
}

function SelfTimeClock() {
  const now = useTicker();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [workOrderId, setWorkOrderId] = useState("");
  const [notes, setNotes] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["time-clock-me"],
    queryFn: async () => (await api.get("/time-clock/me")).data,
    refetchInterval: 30000,
  });

  const entry = data?.active_entry;
  const onBreak = activeBreak(entry);

  async function act(path, body) {
    setBusy(true);
    try {
      await api.post(`/time-clock/${path}`, body || {});
      qc.invalidateQueries({ queryKey: ["time-clock-me"] });
      qc.invalidateQueries({ queryKey: ["team-dashboard"] });
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading…</div>;

  if (data && !data.employee) {
    return <EmptyState icon={Clock} title="No employee record linked" description="Ask an owner/admin to link your account to an Employee record to use self clock-in." />;
  }

  return (
    <Card data-testid="self-time-clock-card">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2"><Clock className="size-4" />{data?.employee?.name}</span>
          <span className="text-2xl font-mono tabular-nums" data-testid="current-local-time">{new Date(now).toLocaleTimeString("en-US")}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!entry ? (
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div>
              <div className="font-medium">Not clocked in</div>
              <div className="text-sm text-muted-foreground">Ready when you are.</div>
            </div>
            <Button size="lg" onClick={() => act("clock-in", { work_order_id: workOrderId || undefined, notes: notes || undefined })} disabled={busy} data-testid="clock-in-button">
              <LogIn className="size-4 mr-1" />Clock in
            </Button>
          </div>
        ) : (
          <div className="rounded-lg border p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium flex items-center gap-2">
                  {onBreak ? <StatusPill kind="employee" value="suspended" /> : <StatusPill kind="employee" value="active" />}
                  {onBreak ? "On break" : "Clocked in"}
                </div>
                <div className="text-sm text-muted-foreground">Since {formatClockTime(entry.clock_in_at)}</div>
              </div>
              <div className="text-right">
                <div className="text-3xl font-mono tabular-nums" data-testid="elapsed-time">{formatMinutes(elapsedMinutes(entry.clock_in_at, now) - (entry.total_break_minutes || 0))}</div>
                <div className="text-xs text-muted-foreground">elapsed worked time</div>
              </div>
            </div>
            {onBreak && (
              <div className="text-sm text-amber-700" data-testid="active-break-time">
                On break for {formatMinutes(elapsedMinutes(onBreak.start_at, now))}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {!onBreak ? (
                <Button variant="outline" onClick={() => act("break-start")} disabled={busy} data-testid="break-start-button">
                  <Coffee className="size-4 mr-1" />Start break
                </Button>
              ) : (
                <Button variant="outline" onClick={() => act("break-end")} disabled={busy} data-testid="break-end-button">
                  <Play className="size-4 mr-1" />End break
                </Button>
              )}
              <Button variant="destructive" onClick={() => act("clock-out")} disabled={busy || !!onBreak} data-testid="clock-out-button">
                <LogOut className="size-4 mr-1" />Clock out
              </Button>
            </div>
            {onBreak && <div className="text-xs text-muted-foreground">End your break before clocking out.</div>}
          </div>
        )}
        {!entry && (
          <div className="grid grid-cols-2 gap-3 max-w-md">
            <div className="grid gap-1.5"><Label className="text-xs">Work Order ID (optional)</Label><Input value={workOrderId} onChange={(e) => setWorkOrderId(e.target.value)} data-testid="clock-in-work-order-input" /></div>
            <div className="grid gap-1.5"><Label className="text-xs">Notes (optional)</Label><Input value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="clock-in-notes-input" /></div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AdminTimeClockPanel() {
  const qc = useQueryClient();
  const [busyId, setBusyId] = useState(null);
  const { data } = useQuery({ queryKey: ["employees", ""], queryFn: async () => (await api.get("/employees", { params: { status: "active" } })).data });
  const { data: entries } = useQuery({
    queryKey: ["time-clock-entries-all-open"],
    queryFn: async () => (await api.get("/time-clock/entries/all", { params: { status: "open" } })).data,
    refetchInterval: 30000,
  });
  const openByEmployee = useMemo(() => {
    const m = {};
    (entries?.items || []).forEach((e) => { m[e.employee_id] = e; });
    return m;
  }, [entries]);

  async function act(employeeId, action) {
    setBusyId(employeeId);
    try {
      await api.post(`/time-clock/${employeeId}/${action}`, {});
      qc.invalidateQueries({ queryKey: ["time-clock-entries-all-open"] });
      qc.invalidateQueries({ queryKey: ["team-dashboard"] });
      toast.success("Updated");
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusyId(null); }
  }

  const employees = data?.items || [];
  if (employees.length === 0) return null;

  return (
    <Card data-testid="admin-time-clock-panel">
      <CardHeader><CardTitle className="flex items-center gap-2"><Users className="size-4" />Team Time Clock</CardTitle></CardHeader>
      <CardContent className="divide-y">
        {employees.map((emp) => {
          const entry = openByEmployee[emp.id];
          const onBreak = entry && activeBreak(entry);
          return (
            <div key={emp.id} className="py-2.5 flex items-center justify-between gap-3" data-testid={`admin-clock-row-${emp.id}`}>
              <div className="min-w-0">
                <div className="font-medium text-sm">{emp.name}</div>
                <div className="text-xs text-muted-foreground">{entry ? (onBreak ? "On break" : "Clocked in") : "Not clocked in"}</div>
              </div>
              <div className="flex items-center gap-1.5">
                {!entry ? (
                  <Button size="sm" variant="outline" onClick={() => act(emp.id, "clock-in")} disabled={busyId === emp.id} data-testid={`admin-clock-in-${emp.id}`}>Clock in</Button>
                ) : (
                  <>
                    {!onBreak ? (
                      <Button size="sm" variant="ghost" onClick={() => act(emp.id, "break-start")} disabled={busyId === emp.id} data-testid={`admin-break-start-${emp.id}`}>Break</Button>
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => act(emp.id, "break-end")} disabled={busyId === emp.id} data-testid={`admin-break-end-${emp.id}`}>End break</Button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => act(emp.id, "clock-out")} disabled={busyId === emp.id || !!onBreak} data-testid={`admin-clock-out-${emp.id}`}>Clock out</Button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export default function TimeClockPage() {
  const { hasPerm } = useAuth();
  const canManage = hasPerm("timeclock:manage");
  return (
    <div className="space-y-4" data-testid="time-clock-page">
      <PageHeader title="Time Clock" subtitle="Clock in, take breaks, clock out." />
      <SelfTimeClock />
      {canManage && <AdminTimeClockPanel />}
    </div>
  );
}
