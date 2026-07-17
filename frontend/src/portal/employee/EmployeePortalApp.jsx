import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useCallback, useEffect, useRef, useState } from "react";
import { EmployeePortalAuthProvider, useEmployeePortalAuth } from "./EmployeePortalAuthContext";
import employeePortalApi, { employeePortalExtractError } from "./employeePortalApi";
import MyTrainingPage from "./MyTrainingPage";
import MyTrainingAssignmentDetailPage from "./MyTrainingAssignmentDetailPage";
import MyCertificationsPage from "./MyCertificationsPage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { AlertTriangle, Briefcase, Calendar, CheckCircle2, Clock, FileClock, GraduationCap, Hourglass, Megaphone, MessageSquare, Play, RotateCw, Search, ShieldCheck, User, Wallet } from "lucide-react";

function fmtCents(cents) {
  const n = Number(cents || 0) / 100;
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

function Shell({ children }) {
  const { identity, logout } = useEmployeePortalAuth();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900" data-testid="employee-portal-shell">
      <header className="border-b bg-white">
        <div className="max-w-4xl mx-auto flex items-center justify-between px-4 py-3">
          <Link to="/portal/employee" className="font-semibold" data-testid="employee-portal-logo">SignGuy Employee Portal</Link>
          <nav className="flex gap-3 text-sm items-center">
            <Link to="/portal/employee/time-clock" data-testid="employee-portal-nav-time-clock">Time Clock</Link>
            <Link to="/portal/employee/production" data-testid="employee-portal-nav-production">Production</Link>
            <Link to="/portal/employee/schedule" data-testid="employee-portal-nav-schedule">My Schedule</Link>
            <Link to="/portal/employee/timesheet" data-testid="employee-portal-nav-timesheet">My Timesheet</Link>
            <Link to="/portal/employee/pay" data-testid="employee-portal-nav-pay">My Pay</Link>
            <Link to="/portal/employee/training" data-testid="employee-portal-nav-training">My Training</Link>
            <Link to="/portal/employee/certifications" data-testid="employee-portal-nav-certifications">My Certifications</Link>
            <Link to="/portal/employee/tasks" data-testid="employee-portal-nav-tasks">My Tasks</Link>
            <Link to="/portal/employee/announcements" data-testid="employee-portal-nav-announcements">Announcements</Link>
            <Link to="/portal/employee/profile" data-testid="employee-portal-nav-profile">Profile</Link>
          </nav>
          <div className="flex items-center gap-2 text-xs">
            {identity && <span className="text-slate-600">{identity.full_name || identity.email}</span>}
            <Button size="sm" variant="outline" onClick={logout} data-testid="employee-portal-logout">Logout</Button>
          </div>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}

function Guard({ children }) {
  const { identity, loading } = useEmployeePortalAuth();
  const loc = useLocation();
  if (loading) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  if (!identity) return <Navigate to={`/portal/employee/login?next=${encodeURIComponent(loc.pathname)}`} replace />;
  return <Shell>{children}</Shell>;
}

function LoginPage() {
  const { login, requestMagicLink } = useEmployeePortalAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  async function doLogin(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await login({ email, password, tenant_slug: tenantSlug || undefined });
      toast.success("Signed in"); nav("/portal/employee");
    } catch (err) { toast.error(employeePortalExtractError(err)); }
    setBusy(false);
  }
  async function doMagic() {
    if (!email) return toast.error("Enter your email first");
    try { await requestMagicLink({ email, tenant_slug: tenantSlug || undefined }); toast.success("Check your email for a sign-in link."); }
    catch (err) { toast.error(employeePortalExtractError(err)); }
  }
  return (
    <div className="min-h-screen grid place-items-center bg-slate-50">
      <Card className="w-full max-w-sm" data-testid="employee-portal-login-card">
        <CardHeader><CardTitle>Employee Portal sign-in</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={doLogin} className="space-y-3">
            <div className="grid gap-1.5"><Label>Email</Label><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="employee-portal-login-email" required /></div>
            <div className="grid gap-1.5"><Label>Password (optional)</Label><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="employee-portal-login-password" /></div>
            <div className="grid gap-1.5"><Label className="text-xs text-slate-500">Tenant slug (if prompted)</Label><Input value={tenantSlug} onChange={(e) => setTenantSlug(e.target.value)} data-testid="employee-portal-login-tenant" /></div>
            <Button type="submit" className="w-full" disabled={busy || !password} data-testid="employee-portal-login-submit">Sign in with password</Button>
            <Button type="button" variant="outline" className="w-full" onClick={doMagic} data-testid="employee-portal-login-magic">Email me a sign-in link</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function VerifyPage() {
  const { verifyMagicLink } = useEmployeePortalAuth();
  const nav = useNavigate();
  const [status, setStatus] = useState("verifying");
  const firedRef = useRef(false);
  useEffect(() => {
    if (firedRef.current) return;
    firedRef.current = true;
    const t = new URLSearchParams(window.location.search).get("t");
    if (!t) { setStatus("invalid"); return; }
    verifyMagicLink(t).then(() => { setStatus("ok"); nav("/portal/employee"); })
      .catch(() => setStatus("failed"));
  }, [verifyMagicLink, nav]);
  return (
    <div className="min-h-screen grid place-items-center p-6 text-sm" data-testid="employee-portal-verify">
      {status === "verifying" && "Verifying your sign-in link…"}
      {status === "invalid" && "Missing token."}
      {status === "failed" && <span>That sign-in link is invalid or expired. <Link className="underline" to="/portal/employee/login">Try again</Link></span>}
    </div>
  );
}

function fmtTime(iso) {
  if (!iso) return "--:--";
  try { return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); } catch { return iso; }
}
function fmtDate(iso) {
  if (!iso) return "No due date";
  try { return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" }); } catch { return iso; }
}
function fmtHours(mins) {
  const m = mins || 0;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function TimeClockCard({ compact }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { const r = await employeePortalApi.get("/portal/employee/time-clock/me"); setStatus(r.data.active_entry); }
    catch (e) { toast.error(employeePortalExtractError(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function act(path) {
    if (busy) return;
    setBusy(true);
    try {
      const r = await employeePortalApi.post(`/portal/employee/time-clock/${path}`, {});
      setStatus(path === "clock-out" ? null : r.data);
      toast.success("Updated");
    } catch (e) { toast.error(employeePortalExtractError(e)); }
    setBusy(false);
  }

  const onBreak = !!(status?.breaks?.length && !status.breaks[status.breaks.length - 1].end_at);
  return (
    <Card data-testid="employee-portal-time-clock-card">
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Clock className="h-4 w-4" /> Time Clock</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {!status ? (
          <>
            <p className="text-sm text-slate-500">You're currently clocked out.</p>
            <Button onClick={() => act("clock-in")} disabled={busy} data-testid="employee-portal-clock-in-btn">Clock In</Button>
          </>
        ) : (
          <>
            <div className="text-sm flex items-center gap-2">Clocked in at <span className="font-medium">{fmtTime(status.clock_in_at)}</span>{onBreak && <Badge variant="outline">On break</Badge>}</div>
            <div className="flex gap-2 flex-wrap">
              {!onBreak ? (
                <Button variant="outline" onClick={() => act("break-start")} disabled={busy} data-testid="employee-portal-break-start-btn">Start Break</Button>
              ) : (
                <Button variant="outline" onClick={() => act("break-end")} disabled={busy} data-testid="employee-portal-break-end-btn">End Break</Button>
              )}
              <Button variant="destructive" onClick={() => act("clock-out")} disabled={busy} data-testid="employee-portal-clock-out-btn">Clock Out</Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Dashboard() {
  const { identity } = useEmployeePortalAuth();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [training, setTraining] = useState(null);
  const [certs, setCerts] = useState(null);
  useEffect(() => {
    employeePortalApi.get("/portal/employee/dashboard").then((r) => setData(r.data))
      .catch((e) => setErr(employeePortalExtractError(e)));
    employeePortalApi.get("/portal/employee/training/assignments").then((r) => setTraining(r.data.items)).catch(() => {});
    employeePortalApi.get("/portal/employee/certifications").then((r) => setCerts(r.data.items)).catch(() => {});
  }, []);
  const trainingDue = (training || []).filter((a) => !["completed", "cancelled", "failed"].includes(a.status) && !a.overdue).length;
  const trainingOverdue = (training || []).filter((a) => a.overdue).length;
  const pendingSignoff = (training || []).filter((a) => a.status === "pending_signoff").length;
  const certsExpiringSoon = (certs || []).filter((c) => c.expires_soon).length;
  const certsExpired = (certs || []).filter((c) => c.status === "expired").length;
  return (
    <div className="space-y-4" data-testid="employee-portal-dashboard">
      <h1 className="text-2xl font-semibold">Welcome, {identity?.full_name || identity?.email}</h1>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      <div className="grid gap-4 sm:grid-cols-2">
        <TimeClockCard />
        <Card data-testid="employee-portal-next-shift-card">
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Calendar className="h-4 w-4" /> Next Shift</CardTitle></CardHeader>
          <CardContent>
            {!data ? <p className="text-sm text-slate-500">Loading…</p> : !data.next_shift ? (
              <p className="text-sm text-slate-500 italic">No upcoming shifts scheduled.</p>
            ) : (
              <p className="text-sm">
                <span className="font-medium">{data.next_shift.shift_date}</span>{" "}
                {fmtTime(data.next_shift.start_at)}–{fmtTime(data.next_shift.end_at)}
                {data.next_shift.location && <span className="text-slate-500"> · {data.next_shift.location}</span>}
              </p>
            )}
          </CardContent>
        </Card>
        <Card data-testid="employee-portal-week-hours-card">
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><FileClock className="h-4 w-4" /> This Week</CardTitle></CardHeader>
          <CardContent>
            {!data ? <p className="text-sm text-slate-500">Loading…</p> : (
              <div className="text-sm flex items-center gap-1.5">{fmtHours(data.week_hours?.worked_minutes)} worked · Timesheet: <Badge variant="outline">{data.timesheet_status}</Badge></div>
            )}
          </CardContent>
        </Card>
        <Card data-testid="employee-portal-announcements-card">
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Megaphone className="h-4 w-4" /> Announcements</CardTitle></CardHeader>
          <CardContent className="space-y-1">
            {!data ? <p className="text-sm text-slate-500">Loading…</p> : data.announcements.length === 0 ? (
              <p className="text-sm text-slate-500 italic">No announcements.</p>
            ) : data.announcements.slice(0, 3).map((a) => (
              <p key={a.id} className="text-sm font-medium">{a.title}</p>
            ))}
          </CardContent>
        </Card>
        <Card data-testid="employee-portal-pay-card">
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Wallet className="h-4 w-4" /> My Pay</CardTitle></CardHeader>
          <CardContent>
            {!data ? <p className="text-sm text-slate-500">Loading…</p> : !data.pay ? (
              <p className="text-sm text-slate-500 italic">No pay history yet.</p>
            ) : (
              <div className="text-sm space-y-1">
                <div>Latest Pay Period: <span className="font-medium">{data.pay.period_start} – {data.pay.period_end}</span></div>
                <div className="flex items-center gap-2">
                  Gross: <span className="font-medium">{fmtCents(data.pay.gross_regular_cents + data.pay.gross_overtime_cents)}</span>
                  <Badge variant="outline">{data.pay.period_status}</Badge>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
        <Card data-testid="employee-portal-training-card">
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><GraduationCap className="h-4 w-4" /> Training</CardTitle></CardHeader>
          <CardContent>
            {!training ? <p className="text-sm text-slate-500">Loading…</p> : (
              <div className="text-sm flex items-center gap-3 flex-wrap">
                <span data-testid="employee-portal-training-due-count"><span className="font-semibold">{trainingDue}</span> due</span>
                <span className={trainingOverdue > 0 ? "text-rose-700" : ""} data-testid="employee-portal-training-overdue-count"><span className="font-semibold">{trainingOverdue}</span> overdue</span>
                <span data-testid="employee-portal-training-pending-signoff-count"><span className="font-semibold">{pendingSignoff}</span> pending signoff</span>
                <Link className="underline text-xs ml-auto" to="/portal/employee/training">View all</Link>
              </div>
            )}
          </CardContent>
        </Card>
        <Card data-testid="employee-portal-certifications-card">
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-4 w-4" /> Certifications</CardTitle></CardHeader>
          <CardContent>
            {!certs ? <p className="text-sm text-slate-500">Loading…</p> : (
              <div className="text-sm flex items-center gap-3 flex-wrap">
                <span className={certsExpiringSoon > 0 ? "text-amber-700" : ""} data-testid="employee-portal-certs-expiring-count"><span className="font-semibold">{certsExpiringSoon}</span> expiring soon</span>
                <span className={certsExpired > 0 ? "text-rose-700" : ""} data-testid="employee-portal-certs-expired-count"><span className="font-semibold">{certsExpired}</span> expired</span>
                <Link className="underline text-xs ml-auto" to="/portal/employee/certifications">View all</Link>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      <Card data-testid="employee-portal-quick-links-card">
        <CardHeader><CardTitle className="text-base">Quick Links</CardTitle></CardHeader>
        <CardContent className="flex gap-3 flex-wrap text-sm">
          <Link className="underline" to="/portal/employee/time-clock">Clock In/Out</Link>
          <Link className="underline" to="/portal/employee/production">Production</Link>
          <Link className="underline" to="/portal/employee/schedule">My Schedule</Link>
          <Link className="underline" to="/portal/employee/timesheet">My Timesheet</Link>
          <Link className="underline" to="/portal/employee/pay">My Pay</Link>
          <Link className="underline" to="/portal/employee/training">My Training</Link>
          <Link className="underline" to="/portal/employee/certifications">My Certifications</Link>
          <Link className="underline" to="/portal/employee/tasks">My Tasks</Link>
          <Link className="underline" to="/portal/employee/announcements">Announcements</Link>
          <Link className="underline" to="/portal/employee/profile">Profile</Link>
        </CardContent>
      </Card>
    </div>
  );
}

function TimeClockPage() {
  return (
    <div className="space-y-4 max-w-md" data-testid="employee-portal-time-clock-page">
      <h1 className="text-xl font-semibold flex items-center gap-2"><Clock className="h-5 w-5" /> Time Clock</h1>
      <TimeClockCard />
    </div>
  );
}

function statusBadge(status) {
  const label = String(status || "not_started").replace(/_/g, " ");
  const variant = status === "blocked" ? "destructive" : "outline";
  return <Badge variant={variant} className="capitalize">{label}</Badge>;
}

function MyTasksPage() {
  const [items, setItems] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [comment, setComment] = useState("");
  const load = useCallback(async () => {
    try {
      const r = await employeePortalApi.get("/portal/employee/tasks");
      setItems(r.data.items || []);
      setSelected((cur) => cur || r.data.items?.[0] || null);
    } catch (e) { toast.error(employeePortalExtractError(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!selected?.id) { setDetail(null); return; }
    employeePortalApi.get(`/portal/employee/tasks/${selected.id}`).then((r) => setDetail(r.data))
      .catch((e) => toast.error(employeePortalExtractError(e)));
  }, [selected?.id]);

  async function act(action) {
    if (!selected) return;
    try {
      await employeePortalApi.post(`/portal/employee/tasks/${selected.id}/${action}`, { reason: `${action} from Employee Portal` });
      toast.success("Task updated");
      setSelected(null);
      await load();
    } catch (e) { toast.error(employeePortalExtractError(e)); }
  }

  async function addComment(e) {
    e.preventDefault();
    if (!selected || !comment.trim()) return;
    try {
      await employeePortalApi.post(`/portal/employee/tasks/${selected.id}/comments`, { body: comment });
      setComment("");
      const r = await employeePortalApi.get(`/portal/employee/tasks/${selected.id}`);
      setDetail(r.data);
      toast.success("Comment added");
    } catch (err) { toast.error(employeePortalExtractError(err)); }
  }

  const actions = detail?.task?.allowed_actions || selected?.allowed_actions || [];
  return (
    <div className="space-y-4" data-testid="employee-portal-tasks-page">
      <h1 className="text-xl font-semibold flex items-center gap-2"><CheckCircle2 className="h-5 w-5" /> My Tasks</h1>
      {!items ? <p className="text-sm text-slate-500">Loading...</p> : !items.length ? (
        <Card><CardContent className="py-8 text-sm text-slate-500 italic">No assigned tasks.</CardContent></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="space-y-2">
            {items.map((task) => (
              <button key={task.id} onClick={() => setSelected(task)} className={`w-full rounded-lg border bg-white p-3 text-left ${selected?.id === task.id ? "ring-2 ring-slate-300" : ""}`} data-testid={`employee-task-row-${task.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-medium truncate">{task.title}</div>
                    <div className="text-xs text-slate-500 truncate">{task.description || task.task_type}</div>
                  </div>
                  {statusBadge(task.status)}
                </div>
                <div className="mt-2 text-xs text-slate-500">{fmtDate(task.due_at)}</div>
              </button>
            ))}
          </div>
          {selected && (
            <Card data-testid="employee-task-detail">
              <CardHeader><CardTitle className="text-base">{detail?.task?.title || selected.title}</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2 flex-wrap">{statusBadge(detail?.task?.status || selected.status)}<Badge variant="outline">{detail?.task?.priority || selected.priority}</Badge></div>
                {(detail?.task?.description || selected.description) && <p className="text-sm text-slate-600 whitespace-pre-wrap">{detail?.task?.description || selected.description}</p>}
                <div className="flex gap-2 flex-wrap">
                  {actions.includes("start") && <Button size="sm" onClick={() => act("start")}><Play className="h-4 w-4 mr-1" />Start</Button>}
                  {actions.includes("resume") && <Button size="sm" variant="outline" onClick={() => act("resume")}>Resume</Button>}
                  {actions.includes("wait") && <Button size="sm" variant="outline" onClick={() => act("wait")}>Wait</Button>}
                  {actions.includes("block") && <Button size="sm" variant="outline" onClick={() => act("block")}>Block</Button>}
                  {actions.includes("complete") && <Button size="sm" onClick={() => act("complete")}>Complete</Button>}
                </div>
                <div className="border-t pt-3 space-y-2">
                  <div className="text-sm font-medium">Comments</div>
                  {!(detail?.comments || []).length ? <p className="text-sm text-slate-500 italic">No employee-visible comments.</p> : detail.comments.map((c) => (
                    <div key={c.id} className="rounded-md bg-slate-50 p-2 text-sm">{c.body}</div>
                  ))}
                  <form onSubmit={addComment} className="space-y-2">
                    <Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Add comment" data-testid="employee-task-comment-input" />
                    <Button size="sm" type="submit" disabled={!comment.trim()}>Add comment</Button>
                  </form>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function ProductionTaskCard({ task, selected, onSelect, onAction, compact }) {
  if (!task) return null;
  const blocked = task.stage_status === "blocked";
  const waiting = task.stage_status === "waiting";
  return (
    <button
      type="button"
      onClick={() => onSelect(task)}
      className={`w-full text-left rounded border bg-white p-4 transition ${selected ? "border-slate-900 shadow-sm" : "border-slate-200 hover:border-slate-400"}`}
      data-testid={`employee-production-task-${task.stage_id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-lg font-semibold truncate">{task.stage_name || "Production task"}</div>
          <div className="text-sm text-slate-600 truncate">WO {task.work_order_number || task.work_order_id} · {task.customer_name || "Customer"} · {task.order_item_name}</div>
        </div>
        {statusBadge(task.stage_status)}
      </div>
      <div className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-3">
        <span>Due {fmtDate(task.due_at)}</span>
        <span>{task.progress_percent || 0}% complete</span>
        <span className={task.overdue ? "text-rose-700 font-medium" : ""}>{task.overdue ? "Overdue" : task.priority || "normal"}</span>
      </div>
      {(blocked || waiting || task.eligibility_warning) && (
        <div className="mt-3 flex items-center gap-2 text-sm text-amber-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span className="truncate">{task.blocker_reason || task.eligibility_warning || "Waiting"}</span>
        </div>
      )}
      {!compact && task.allowed_actions?.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {task.allowed_actions.includes("start") && <Button type="button" size="lg" onClick={(e) => { e.stopPropagation(); onAction(task, "start"); }} data-testid="employee-production-start"><Play className="h-4 w-4 mr-1" />Start</Button>}
          {task.allowed_actions.includes("resume") && <Button type="button" size="lg" onClick={(e) => { e.stopPropagation(); onAction(task, "resume"); }} data-testid="employee-production-resume"><RotateCw className="h-4 w-4 mr-1" />Resume</Button>}
          {task.allowed_actions.includes("complete") && <Button type="button" size="lg" onClick={(e) => { e.stopPropagation(); onAction(task, "complete"); }} data-testid="employee-production-complete"><CheckCircle2 className="h-4 w-4 mr-1" />Complete</Button>}
        </div>
      )}
    </button>
  );
}

function ProductionDetail({ task, onAction }) {
  if (!task) {
    return (
      <Card data-testid="employee-production-empty-detail">
        <CardContent className="pt-6 text-sm text-slate-500">Select a task to see details.</CardContent>
      </Card>
    );
  }
  return (
    <Card data-testid="employee-production-detail">
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-3 text-xl">
          <span>{task.stage_name}</span>
          {statusBadge(task.stage_status)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <div><div className="text-slate-500">Work Order</div><div className="font-medium">WO {task.work_order_number || task.work_order_id}</div></div>
          <div><div className="text-slate-500">Customer</div><div className="font-medium">{task.customer_name || "Customer"}</div></div>
          <div><div className="text-slate-500">Line Item</div><div className="font-medium">{task.order_item_name}</div></div>
          <div><div className="text-slate-500">Due</div><div className={task.overdue ? "font-medium text-rose-700" : "font-medium"}>{fmtDate(task.due_at)}</div></div>
          <div><div className="text-slate-500">Workflow</div><div className="font-medium">{task.workflow_name || "Workflow"}</div></div>
          <div><div className="text-slate-500">Progress</div><div className="font-medium">{task.completed_stage_count || 0}/{task.total_stage_count || 0} stages</div></div>
        </div>
        {task.blocker_reason && <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{task.blocker_reason}</div>}
        {task.allowed_actions?.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {task.allowed_actions.includes("start") && <Button size="lg" onClick={() => onAction(task, "start")}><Play className="h-5 w-5 mr-2" />Start Task</Button>}
            {task.allowed_actions.includes("resume") && <Button size="lg" onClick={() => onAction(task, "resume")}><RotateCw className="h-5 w-5 mr-2" />Resume</Button>}
            {task.allowed_actions.includes("complete") && <Button size="lg" onClick={() => onAction(task, "complete")}><CheckCircle2 className="h-5 w-5 mr-2" />Complete</Button>}
            {task.allowed_actions.includes("wait") && <Button size="lg" variant="outline" onClick={() => onAction(task, "wait")}><Hourglass className="h-5 w-5 mr-2" />Waiting</Button>}
            {task.allowed_actions.includes("block") && <Button size="lg" variant="outline" onClick={() => onAction(task, "block")}><AlertTriangle className="h-5 w-5 mr-2" />Block</Button>}
            {task.allowed_actions.includes("add_note") && <Button size="lg" variant="outline" onClick={() => onAction(task, "notes")}><MessageSquare className="h-5 w-5 mr-2" />Add Note</Button>}
          </div>
        ) : (
          <div className="text-sm text-slate-500">This task is visible in the shop queue. A manager must assign it before employee actions are available.</div>
        )}
      </CardContent>
    </Card>
  );
}

function ProductionPage() {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (q = search) => {
    try {
      const r = await employeePortalApi.get("/portal/employee/production", { params: q ? { search: q } : {} });
      setData(r.data);
      setErr(null);
      const nextSelected = r.data.current_task || r.data.assigned_tasks?.[0] || r.data.shop_queue?.[0] || null;
      setSelected((prev) => {
        if (prev && [...(r.data.assigned_tasks || []), ...(r.data.shop_queue || [])].some((t) => t.stage_id === prev.stage_id)) return prev;
        return nextSelected;
      });
    } catch (e) { setErr(employeePortalExtractError(e)); }
  }, [search]);

  useEffect(() => { load(""); }, [load]);

  async function act(task, action) {
    if (!task?.stage_id || busy) return;
    let payload = {};
    if (action === "wait" || action === "block") {
      const reason = window.prompt(action === "wait" ? "Why is this waiting?" : "Why is this blocked?");
      if (!reason) return;
      payload.reason = reason;
    }
    if (action === "complete") {
      const note = window.prompt("Completion note (optional)") || "";
      payload.completion_note = note;
    }
    if (action === "notes") {
      const note = window.prompt("Production note");
      if (!note) return;
      payload.note = note;
    }
    setBusy(true);
    try {
      await employeePortalApi.post(`/portal/employee/production/stages/${task.stage_id}/${action}`, payload);
      toast.success("Production task updated");
      await load(search);
    } catch (e) { toast.error(employeePortalExtractError(e)); }
    setBusy(false);
  }

  const assigned = data?.assigned_tasks || [];
  const queue = data?.shop_queue || [];
  return (
    <div className="space-y-4" data-testid="employee-production-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-semibold flex items-center gap-2"><Briefcase className="h-6 w-6" /> Production</h1>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); load(search); }}>
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search shop queue" data-testid="employee-production-search" />
          <Button type="submit" variant="outline"><Search className="h-4 w-4" /></Button>
        </form>
      </div>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      <div className="grid gap-4 lg:grid-cols-[minmax(320px,1fr)_minmax(360px,1fr)]">
        <div className="space-y-4">
          <TimeClockCard compact />
          {data?.current_task && (
            <section className="space-y-2" data-testid="employee-production-current">
              <h2 className="text-sm font-semibold uppercase text-slate-500">Current Task</h2>
              <ProductionTaskCard task={data.current_task} selected={selected?.stage_id === data.current_task.stage_id} onSelect={setSelected} onAction={act} />
            </section>
          )}
          <section className="space-y-2" data-testid="employee-production-assigned">
            <h2 className="text-sm font-semibold uppercase text-slate-500">My Assigned Tasks</h2>
            {!data ? <p className="text-sm text-slate-500">Loading...</p> : assigned.length === 0 ? (
              <Card><CardContent className="pt-6 text-sm text-slate-500">No assigned production tasks.</CardContent></Card>
            ) : assigned.map((task) => (
              <ProductionTaskCard key={task.stage_id} task={task} selected={selected?.stage_id === task.stage_id} onSelect={setSelected} onAction={act} compact />
            ))}
          </section>
        </div>
        <div className="space-y-4">
          <ProductionDetail task={selected} onAction={act} />
          <section className="space-y-2" data-testid="employee-production-shop-queue">
            <h2 className="text-sm font-semibold uppercase text-slate-500">Shop Queue</h2>
            {!data ? <p className="text-sm text-slate-500">Loading...</p> : queue.length === 0 ? (
              <Card><CardContent className="pt-6 text-sm text-slate-500">No visible shop queue tasks.</CardContent></Card>
            ) : queue.slice(0, 12).map((task) => (
              <ProductionTaskCard key={task.stage_id} task={task} selected={selected?.stage_id === task.stage_id} onSelect={setSelected} onAction={act} compact />
            ))}
          </section>
        </div>
      </div>
    </div>
  );
}

function MySchedulePage() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    employeePortalApi.get("/portal/employee/schedule/week").then((r) => setData(r.data))
      .catch((e) => setErr(employeePortalExtractError(e)));
  }, []);
  return (
    <div className="space-y-4" data-testid="employee-portal-schedule-page">
      <h1 className="text-xl font-semibold flex items-center gap-2"><Calendar className="h-5 w-5" /> My Schedule</h1>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      {!data ? <p className="text-sm text-slate-500">Loading…</p> : data.items.length === 0 ? (
        <p className="text-sm text-slate-500 italic" data-testid="employee-portal-schedule-empty">No published shifts this week yet.</p>
      ) : (
        <div className="rounded border bg-white divide-y">
          {data.items.map((s) => (
            <div key={s.id} className="p-3 text-sm flex items-center justify-between" data-testid={`employee-portal-shift-${s.id}`}>
              <div>
                <div className="font-medium">{s.shift_date} · {fmtTime(s.start_at)}–{fmtTime(s.end_at)}</div>
                <div className="text-xs text-slate-500">{s.title || ""} {s.location ? `· ${s.location}` : ""}</div>
              </div>
              <Badge variant={s.status === "cancelled" ? "destructive" : "outline"}>{s.status}</Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MyTimesheetPage() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    employeePortalApi.get(`/portal/employee/timesheet/weekly?week_start=${today}`).then((r) => setData(r.data))
      .catch((e) => setErr(employeePortalExtractError(e)));
  }, []);
  return (
    <div className="space-y-4 max-w-md" data-testid="employee-portal-timesheet-page">
      <h1 className="text-xl font-semibold flex items-center gap-2"><FileClock className="h-5 w-5" /> My Timesheet</h1>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      {!data ? <p className="text-sm text-slate-500">Loading…</p> : (
        <Card>
          <CardContent className="pt-6 space-y-2 text-sm">
            <p>Week: {data.week_start} – {data.week_end}</p>
            <p>Worked: <span className="font-medium">{fmtHours(data.worked_minutes)}</span></p>
            <p>Breaks: {fmtHours(data.break_minutes)}</p>
            <div className="flex items-center gap-1.5">Status: <Badge variant="outline" data-testid="employee-portal-timesheet-status">{data.status}</Badge></div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function AnnouncementsPage() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    employeePortalApi.get("/portal/employee/announcements").then((r) => setData(r.data))
      .catch((e) => setErr(employeePortalExtractError(e)));
  }, []);
  return (
    <div className="space-y-4" data-testid="employee-portal-announcements-page">
      <h1 className="text-xl font-semibold flex items-center gap-2"><Megaphone className="h-5 w-5" /> Announcements</h1>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      {!data ? <p className="text-sm text-slate-500">Loading…</p> : data.items.length === 0 ? (
        <p className="text-sm text-slate-500 italic">No announcements right now.</p>
      ) : (
        <div className="rounded border bg-white divide-y">
          {data.items.map((a) => (
            <div key={a.id} className="p-3 text-sm" data-testid={`employee-portal-announcement-${a.id}`}>
              <div className="font-medium">{a.title}</div>
              <div className="text-slate-600">{a.body}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ProfilePage() {
  const [data, setData] = useState(null);
  const [phone, setPhone] = useState("");
  const [err, setErr] = useState(null);
  const load = useCallback(async () => {
    try { const r = await employeePortalApi.get("/portal/employee/profile"); setData(r.data); setPhone(r.data.portal_phone || ""); }
    catch (e) { setErr(employeePortalExtractError(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);
  async function save() {
    try { await employeePortalApi.patch("/portal/employee/profile", { phone }); toast.success("Saved"); load(); }
    catch (e) { toast.error(employeePortalExtractError(e)); }
  }
  return (
    <div className="space-y-4 max-w-lg" data-testid="employee-portal-profile-page">
      <h1 className="text-xl font-semibold flex items-center gap-2"><User className="h-5 w-5" /> Profile</h1>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      {data && (
        <Card>
          <CardContent className="pt-6 space-y-3 text-sm">
            <p><span className="text-slate-500">Name:</span> {data.employee.name}</p>
            <p><span className="text-slate-500">Role:</span> {data.employee.role_label || "—"}</p>
            <p><span className="text-slate-500">Portal email:</span> {data.portal_email}</p>
            <div className="grid gap-1.5 max-w-xs">
              <Label>Preferred contact phone</Label>
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} data-testid="employee-portal-profile-phone" />
            </div>
            <Button onClick={save} data-testid="employee-portal-profile-save">Save</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function MyPayPage() {
  const [items, setItems] = useState(null);
  const [selected, setSelected] = useState(null);
  const [txns, setTxns] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    employeePortalApi.get("/portal/employee/pay/periods").then((r) => {
      setItems(r.data.items);
      if (r.data.items.length > 0) setSelected(r.data.items[0]);
    }).catch((e) => setErr(employeePortalExtractError(e)));
  }, []);
  useEffect(() => {
    if (!selected) return;
    employeePortalApi.get("/portal/employee/pay/transactions", { params: { pay_period_id: selected.pay_period_id } })
      .then((r) => setTxns(r.data.items))
      .catch((e) => setErr(employeePortalExtractError(e)));
  }, [selected]);

  return (
    <div className="space-y-4" data-testid="employee-portal-pay-page">
      <h1 className="text-xl font-semibold flex items-center gap-2"><Wallet className="h-5 w-5" /> My Pay</h1>
      <p className="text-xs text-slate-500">Internal gross-pay record — hours, advances, payments and carryover. This is not a tax document.</p>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      {!items ? <p className="text-sm text-slate-500">Loading…</p> : items.length === 0 ? (
        <p className="text-sm text-slate-500 italic" data-testid="employee-portal-pay-empty">No pay history yet.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-[220px_1fr]">
          <div className="rounded border bg-white divide-y" data-testid="employee-portal-pay-period-list">
            {items.map((p) => (
              <button
                key={p.pay_period_id}
                onClick={() => setSelected(p)}
                className={`w-full text-left p-3 text-sm ${selected?.pay_period_id === p.pay_period_id ? "bg-slate-100" : ""}`}
                data-testid={`employee-portal-pay-period-${p.pay_period_id}`}
              >
                <div className="font-medium">{p.period_start} – {p.period_end}</div>
                <Badge variant="outline" className="mt-1">{p.period_status}</Badge>
              </button>
            ))}
          </div>
          {selected && (
            <Card data-testid="employee-portal-pay-detail-card">
              <CardHeader><CardTitle className="text-base">Payday {selected.payday}</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div>Hours: <span className="font-medium">{fmtHours(selected.regular_minutes)} regular, {fmtHours(selected.overtime_minutes)} OT</span></div>
                  <div>Rate: <span className="font-medium">{fmtCents(selected.hourly_rate_cents)}/hr</span></div>
                  <div>Regular pay: <span className="font-medium">{fmtCents(selected.gross_regular_cents)}</span></div>
                  <div>Overtime pay: <span className="font-medium">{fmtCents(selected.gross_overtime_cents)}</span></div>
                  <div>Adjustments: <span className="font-medium">{fmtCents(selected.adjustment_total_cents)}</span></div>
                  <div>Advances: <span className="font-medium">{fmtCents(selected.advance_total_cents)}</span></div>
                  <div>Repayments: <span className="font-medium">{fmtCents(selected.repayment_total_cents)}</span></div>
                  <div>Payments: <span className="font-medium">{fmtCents(selected.payment_total_cents)}</span></div>
                  <div>Carryover in: <span className="font-medium">{fmtCents(selected.carryover_in_cents)}</span></div>
                  <div>Carryover out: <span className="font-medium">{fmtCents(selected.carryover_out_cents)}</span></div>
                  <div>Total paid: <span className="font-medium">{fmtCents(selected.total_paid_cents)}</span></div>
                  <div>Balance remaining: <span className="font-semibold">{fmtCents(selected.remaining_balance_cents)}</span></div>
                </div>
                <div className="pt-2 border-t">
                  <div className="text-xs text-slate-500 mb-2">Transactions</div>
                  {!txns?.length ? <p className="text-sm text-slate-500 italic">No transactions recorded for this Pay Period.</p> : (
                    <div className="divide-y" data-testid="employee-portal-pay-transactions">
                      {txns.map((t, i) => (
                        <div key={i} className="py-1.5 flex items-center justify-between text-sm">
                          <span className="capitalize">{t.type.replace(/_/g, " ")}</span>
                          <span className="text-slate-500">{t.effective_date}{t.reference ? ` · ${t.reference}` : ""}</span>
                          <span className="font-medium">{fmtCents(t.amount_cents)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
      <div className="flex gap-3 text-sm">
        <Link className="underline" to="/portal/employee">Dashboard</Link>
        <Link className="underline" to="/portal/employee/time-clock">Time Clock</Link>
        <Link className="underline" to="/portal/employee/timesheet">My Timesheet</Link>
      </div>
    </div>
  );
}

export default function EmployeePortalApp() {
  return (
    <EmployeePortalAuthProvider>
      <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route path="verify" element={<VerifyPage />} />
        <Route path="" element={<Guard><Dashboard /></Guard>} />
        <Route path="time-clock" element={<Guard><TimeClockPage /></Guard>} />
        <Route path="production" element={<Guard><ProductionPage /></Guard>} />
        <Route path="schedule" element={<Guard><MySchedulePage /></Guard>} />
        <Route path="timesheet" element={<Guard><MyTimesheetPage /></Guard>} />
        <Route path="pay" element={<Guard><MyPayPage /></Guard>} />
        <Route path="training" element={<Guard><MyTrainingPage /></Guard>} />
        <Route path="training/:assignmentId" element={<Guard><MyTrainingAssignmentDetailPage /></Guard>} />
        <Route path="certifications" element={<Guard><MyCertificationsPage /></Guard>} />
        <Route path="tasks" element={<Guard><MyTasksPage /></Guard>} />
        <Route path="announcements" element={<Guard><AnnouncementsPage /></Guard>} />
        <Route path="profile" element={<Guard><ProfilePage /></Guard>} />
      </Routes>
    </EmployeePortalAuthProvider>
  );
}
