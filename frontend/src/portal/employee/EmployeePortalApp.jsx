import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import { EmployeePortalAuthProvider, useEmployeePortalAuth } from "./EmployeePortalAuthContext";
import employeePortalApi, { employeePortalExtractError } from "./employeePortalApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Clock, Calendar, FileClock, Megaphone, User } from "lucide-react";

function Shell({ children }) {
  const { identity, logout } = useEmployeePortalAuth();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900" data-testid="employee-portal-shell">
      <header className="border-b bg-white">
        <div className="max-w-4xl mx-auto flex items-center justify-between px-4 py-3">
          <Link to="/portal/employee" className="font-semibold" data-testid="employee-portal-logo">SignGuy Employee Portal</Link>
          <nav className="flex gap-3 text-sm items-center">
            <Link to="/portal/employee/time-clock" data-testid="employee-portal-nav-time-clock">Time Clock</Link>
            <Link to="/portal/employee/schedule" data-testid="employee-portal-nav-schedule">My Schedule</Link>
            <Link to="/portal/employee/timesheet" data-testid="employee-portal-nav-timesheet">My Timesheet</Link>
            <span className="text-slate-400 cursor-not-allowed" title="Coming later" data-testid="employee-portal-nav-tasks-disabled">My Tasks</span>
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
  useEffect(() => {
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

  const onBreak = status?.breaks?.length && !status.breaks[status.breaks.length - 1].end_at;
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
            <p className="text-sm">Clocked in at <span className="font-medium">{fmtTime(status.clock_in_at)}</span>{onBreak && <Badge variant="outline" className="ml-2">On break</Badge>}</p>
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
  useEffect(() => {
    employeePortalApi.get("/portal/employee/dashboard").then((r) => setData(r.data))
      .catch((e) => setErr(employeePortalExtractError(e)));
  }, []);
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
              <p className="text-sm">{fmtHours(data.week_hours?.worked_minutes)} worked · Timesheet: <Badge variant="outline">{data.timesheet_status}</Badge></p>
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
      </div>
      <Card data-testid="employee-portal-quick-links-card">
        <CardHeader><CardTitle className="text-base">Quick Links</CardTitle></CardHeader>
        <CardContent className="flex gap-3 flex-wrap text-sm">
          <Link className="underline" to="/portal/employee/time-clock">Clock In/Out</Link>
          <Link className="underline" to="/portal/employee/schedule">My Schedule</Link>
          <Link className="underline" to="/portal/employee/timesheet">My Timesheet</Link>
          <span className="text-slate-400 cursor-not-allowed" title="Coming later">My Tasks</span>
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
            <p>Status: <Badge variant="outline" data-testid="employee-portal-timesheet-status">{data.status}</Badge></p>
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

export default function EmployeePortalApp() {
  return (
    <EmployeePortalAuthProvider>
      <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route path="verify" element={<VerifyPage />} />
        <Route path="" element={<Guard><Dashboard /></Guard>} />
        <Route path="time-clock" element={<Guard><TimeClockPage /></Guard>} />
        <Route path="schedule" element={<Guard><MySchedulePage /></Guard>} />
        <Route path="timesheet" element={<Guard><MyTimesheetPage /></Guard>} />
        <Route path="announcements" element={<Guard><AnnouncementsPage /></Guard>} />
        <Route path="profile" element={<Guard><ProfilePage /></Guard>} />
      </Routes>
    </EmployeePortalAuthProvider>
  );
}
