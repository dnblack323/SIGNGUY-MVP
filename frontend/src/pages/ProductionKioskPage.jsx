import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { AlertTriangle, CheckCircle2, Clock3, Lock, LogOut, Play, RefreshCw, Search, ShieldCheck, UserRound } from "lucide-react";
import { toast } from "sonner";

import { API, extractError } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const DEVICE_KEY = "sg.production_kiosk.device_token";
const EMPLOYEE_KEY = "sg.production_kiosk.employee_token";

const kioskApi = axios.create({ baseURL: API, timeout: 30000 });

function headers() {
  const h = {};
  const device = localStorage.getItem(DEVICE_KEY);
  const employee = localStorage.getItem(EMPLOYEE_KEY);
  if (device) h["X-Kiosk-Device-Token"] = device;
  if (employee) h["X-Kiosk-Employee-Token"] = employee;
  return h;
}

function staffHeaders() {
  const token = localStorage.getItem("signguy.token");
  return token ? { Authorization: `Bearer ${token}`, ...headers() } : headers();
}

function titleize(value) {
  return String(value || "").replace(/_/g, " ");
}

function TaskCard({ task, onAction, offline, allowSupervisorStart = false }) {
  if (!task) return null;
  const actions = task.allowed_actions || [];
  return (
    <Card className="rounded-md border-slate-200">
      <CardContent className="p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-slate-950">WO {task.work_order_number || "Draft"}</span>
              <Badge variant="outline">{titleize(task.stage_status)}</Badge>
              {task.overdue ? <Badge variant="destructive">Overdue</Badge> : null}
            </div>
            <div className="mt-1 text-sm text-slate-700">{task.order_item_name}</div>
            <div className="mt-1 text-xs text-slate-500">
              {task.customer_name ? `${task.customer_name} · ` : ""}{task.stage_name || "Production task"} · {task.progress_percent || 0}%
            </div>
            {task.blocker_reason ? <div className="mt-2 text-sm text-red-700">{task.blocker_reason}</div> : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {actions.map((action) => (
              <Button key={action} size="sm" variant={action === "complete" ? "default" : "outline"} disabled={offline} onClick={() => onAction(task, action)}>
                {action === "start" || action === "resume" ? <Play className="mr-1 h-4 w-4" /> : null}
                {action === "complete" ? <CheckCircle2 className="mr-1 h-4 w-4" /> : null}
                {action === "add_note" ? "Note" : titleize(action)}
              </Button>
            ))}
            {allowSupervisorStart ? (
              <Button size="sm" variant="outline" disabled={offline} onClick={() => onAction(task, "supervisor_start")}>
                <ShieldCheck className="mr-1 h-4 w-4" /> Supervisor Start
              </Button>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function TaskList({ title, items, onAction, offline, empty = "No tasks", allowSupervisorStart = false }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
        <Badge variant="secondary">{items.length}</Badge>
      </div>
      {items.length ? items.map((task) => <TaskCard key={task.stage_id} task={task} onAction={onAction} offline={offline} allowSupervisorStart={allowSupervisorStart} />) : (
        <div className="rounded-md border border-dashed border-slate-300 p-4 text-sm text-slate-500">{empty}</div>
      )}
    </section>
  );
}

export default function ProductionKioskPage() {
  const [deviceReady, setDeviceReady] = useState(false);
  const [employee, setEmployee] = useState(null);
  const [config, setConfig] = useState(null);
  const [work, setWork] = useState(null);
  const [timeClock, setTimeClock] = useState(null);
  const [label, setLabel] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [pin, setPin] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [offline, setOffline] = useState(!navigator.onLine);
  const [overrideTask, setOverrideTask] = useState(null);
  const [overrideReason, setOverrideReason] = useState("");

  useEffect(() => {
    const online = () => setOffline(false);
    const offlineHandler = () => setOffline(true);
    window.addEventListener("online", online);
    window.addEventListener("offline", offlineHandler);
    return () => {
      window.removeEventListener("online", online);
      window.removeEventListener("offline", offlineHandler);
    };
  }, []);

  const loadWork = useCallback(async () => {
    if (offline || !localStorage.getItem(EMPLOYEE_KEY)) return;
    const params = search.trim() ? { search: search.trim() } : {};
    const [{ data: workData }, { data: clockData }] = await Promise.all([
      kioskApi.get("/production-kiosk/work", { headers: headers(), params }),
      kioskApi.get("/production-kiosk/time-clock", { headers: headers() }).catch(() => ({ data: null })),
    ]);
    setWork(workData);
    setEmployee(workData.employee);
    setConfig(workData.config);
    setTimeClock(clockData);
  }, [offline, search]);

  const inspect = useCallback(async () => {
    const device = localStorage.getItem(DEVICE_KEY);
    if (!device) return;
    try {
      const { data } = await kioskApi.get("/production-kiosk/session", { headers: headers() });
      setDeviceReady(true);
      setConfig(data.config);
      if (localStorage.getItem(EMPLOYEE_KEY)) await loadWork();
    } catch {
      localStorage.removeItem(DEVICE_KEY);
      localStorage.removeItem(EMPLOYEE_KEY);
      setDeviceReady(false);
      setEmployee(null);
      setWork(null);
    }
  }, [loadWork]);

  useEffect(() => { inspect(); }, [inspect]);

  const activate = async () => {
    if (offline) return;
    setLoading(true);
    try {
      const { data } = await kioskApi.post("/production-kiosk/sessions/activate", { device_label: label }, { headers: staffHeaders() });
      localStorage.setItem(DEVICE_KEY, data.device_token);
      setDeviceReady(true);
      setConfig(data.config);
      toast.success("Kiosk activated");
    } catch (e) {
      toast.error(extractError(e, "Could not activate kiosk"));
    } finally {
      setLoading(false);
    }
  };

  const identify = async () => {
    if (offline) return;
    setLoading(true);
    try {
      const { data } = await kioskApi.post("/production-kiosk/identify", { employee_id: employeeId, pin }, { headers: headers() });
      localStorage.setItem(EMPLOYEE_KEY, data.employee_token);
      setEmployee(data.employee);
      setConfig(data.config);
      setPin("");
      await loadWork();
    } catch (e) {
      toast.error(extractError(e, "Invalid employee credentials"));
    } finally {
      setLoading(false);
    }
  };

  const endEmployee = async () => {
    try { await kioskApi.post("/production-kiosk/employee/end", {}, { headers: headers() }); } catch { /* ignore */ }
    localStorage.removeItem(EMPLOYEE_KEY);
    setEmployee(null);
    setWork(null);
    setTimeClock(null);
  };

  const runAction = async (task, action, extra = {}) => {
    if (offline) return;
    const payload = { ...extra };
    if (action === "block" || action === "wait") {
      const reason = window.prompt(`${titleize(action)} reason`);
      if (!reason) return;
      payload.reason = reason;
    }
    if (action === "complete") {
      payload.completion_note = window.prompt("Completion note") || undefined;
    }
    if (action === "add_note") {
      const note = window.prompt("Production note");
      if (!note) return;
      action = "notes";
      payload.note = note;
    }
    try {
      await kioskApi.post(`/production-kiosk/stages/${task.stage_id}/${action}`, payload, { headers: headers() });
      toast.success("Task updated");
      await loadWork();
    } catch (e) {
      toast.error(extractError(e, "Task update failed"));
    }
  };

  const createOverrideAndStart = async () => {
    if (!overrideTask || offline) return;
    try {
      const { data } = await kioskApi.post("/production-kiosk/supervisor-overrides", {
        employee_id: employee.id,
        stage_id: overrideTask.stage_id,
        action: "start",
        reason: overrideReason,
      }, { headers: staffHeaders() });
      await runAction(overrideTask, "start", { supervisor_override_token: data.override_token });
      setOverrideTask(null);
      setOverrideReason("");
    } catch (e) {
      toast.error(extractError(e, "Supervisor override failed"));
    }
  };

  const clock = async (path) => {
    if (offline) return;
    try {
      await kioskApi.post(`/production-kiosk/time-clock/${path}`, {}, { headers: headers() });
      const { data } = await kioskApi.get("/production-kiosk/time-clock", { headers: headers() });
      setTimeClock(data);
    } catch (e) {
      toast.error(extractError(e, "Time Clock update failed"));
    }
  };

  const counts = work?.counts || {};
  const readyActions = useMemo(() => work?.ready_for_me || [], [work]);

  if (!deviceReady) {
    return (
      <main className="min-h-screen bg-slate-950 p-6 text-white">
        <div className="mx-auto max-w-lg space-y-6 pt-20">
          <div>
            <div className="flex items-center gap-2 text-sm text-slate-300"><Lock className="h-4 w-4" /> Production Kiosk</div>
            <h1 className="mt-2 text-3xl font-semibold">Activate Device</h1>
          </div>
          {offline ? <div className="rounded-md bg-red-900/40 p-3 text-sm">Disconnected. Kiosk activation is unavailable.</div> : null}
          <Card className="rounded-md border-slate-700 bg-slate-900 text-white">
            <CardContent className="space-y-4 p-5">
              <div className="space-y-2">
                <Label htmlFor="device-label">Device label</Label>
                <Input id="device-label" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Shop tablet 1" />
              </div>
              <Button className="w-full" onClick={activate} disabled={loading || offline}>Activate</Button>
            </CardContent>
          </Card>
        </div>
      </main>
    );
  }

  if (!employee) {
    return (
      <main className="min-h-screen bg-slate-100 p-6">
        <div className="mx-auto max-w-md space-y-5 pt-20">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-500">Production Kiosk</div>
              <h1 className="text-2xl font-semibold text-slate-950">Employee Sign In</h1>
            </div>
            <ShieldCheck className="h-8 w-8 text-slate-700" />
          </div>
          {offline ? <div className="rounded-md bg-red-100 p-3 text-sm text-red-800">Disconnected. Employee sign-in is disabled.</div> : null}
          <Card className="rounded-md">
            <CardContent className="space-y-4 p-5">
              <div className="space-y-2">
                <Label htmlFor="employee-id">Employee ID</Label>
                <Input id="employee-id" value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} autoComplete="off" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pin">PIN</Label>
                <Input id="pin" type="password" value={pin} onChange={(e) => setPin(e.target.value)} autoComplete="off" />
              </div>
              <Button className="w-full" onClick={identify} disabled={loading || offline || !employeeId || !pin}>
                <UserRound className="mr-2 h-4 w-4" /> Start Kiosk Session
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="sticky top-0 z-10 border-b bg-white/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500">Production Kiosk</div>
            <div className="flex items-center gap-2 text-xl font-semibold text-slate-950">
              {employee.name} {offline ? <Badge variant="destructive">Offline</Badge> : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-slate-400" />
              <Input className="w-64 pl-8" value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") loadWork(); }} />
            </div>
            <Button variant="outline" onClick={loadWork} disabled={offline}><RefreshCw className="mr-2 h-4 w-4" />Refresh</Button>
            <Button variant="outline" onClick={endEmployee}><LogOut className="mr-2 h-4 w-4" />Switch</Button>
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-7xl gap-4 p-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-5">
          <div className="grid gap-3 md:grid-cols-5">
            {["current", "assigned", "ready_for_me", "blocked_waiting", "recently_completed_by_me"].map((key) => (
              <Card key={key} className="rounded-md"><CardContent className="p-3"><div className="text-xs text-slate-500">{titleize(key)}</div><div className="text-2xl font-semibold">{counts[key] || 0}</div></CardContent></Card>
            ))}
          </div>
          <TaskList title="Current Task" items={work?.current_task ? [work.current_task] : []} onAction={runAction} offline={offline} empty="No active task" />
          <TaskList title="Assigned Tasks" items={work?.assigned_tasks || []} onAction={runAction} offline={offline} />
          <TaskList title="Ready For Me" items={readyActions} onAction={(task) => setOverrideTask(task)} offline={offline} empty="No ready tasks" allowSupervisorStart />
          <TaskList title="Shop Queue" items={work?.shop_queue || []} onAction={() => {}} offline={offline} empty="Queue hidden or empty" />
          <TaskList title="Blocked / Waiting" items={work?.blocked_waiting || []} onAction={runAction} offline={offline} />
          <TaskList title="Recently Completed By Me" items={work?.recently_completed_by_me || []} onAction={runAction} offline={offline} />
        </div>
        <aside className="space-y-4">
          <Card className="rounded-md">
            <CardContent className="space-y-4 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500">Work Shift Time</div>
                  <div className="font-semibold">{timeClock?.active_entry ? "Clocked in" : "Clocked out"}</div>
                </div>
                <Clock3 className="h-6 w-6 text-slate-600" />
              </div>
              {config?.time_clock_panel_enabled === false ? (
                <div className="text-sm text-slate-500">Time Clock panel disabled.</div>
              ) : (
                <Button className="w-full" onClick={() => clock(timeClock?.active_entry ? "clock-out" : "clock-in")} disabled={offline}>
                  {timeClock?.active_entry ? "Clock Out" : "Clock In"}
                </Button>
              )}
            </CardContent>
          </Card>
          {overrideTask ? (
            <Card className="rounded-md border-amber-300">
              <CardContent className="space-y-3 p-4">
                <div className="flex items-center gap-2 font-semibold text-amber-900"><AlertTriangle className="h-4 w-4" /> Supervisor Override</div>
                <div className="text-sm text-slate-600">Start WO {overrideTask.work_order_number} for {employee.name}</div>
                <Textarea value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} placeholder="Reason" />
                <div className="flex gap-2">
                  <Button size="sm" onClick={createOverrideAndStart} disabled={!overrideReason.trim() || offline}>Approve Start</Button>
                  <Button size="sm" variant="outline" onClick={() => setOverrideTask(null)}>Cancel</Button>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </aside>
      </div>
    </main>
  );
}
