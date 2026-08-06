import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/auth/AuthContext";
import api, { extractError } from "@/lib/api";
import { isPlatformUser } from "@/lib/navigation";
import { platformAdminApi } from "@/lib/platformAdmin";
import {
  Ban,
  BarChart3,
  CheckCircle2,
  Mail,
  Megaphone,
  RefreshCcw,
  Search,
  Settings,
  ShieldCheck,
  UserRound,
  Wrench,
} from "lucide-react";
import { toast } from "sonner";

function dt(value) {
  if (!value) return "-";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString();
}

function datetimeLocalValue(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 16);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function statusVariant(status) {
  if (["active", "current", true].includes(status)) return "secondary";
  if (["suspended", "failed", false].includes(status)) return "destructive";
  return "outline";
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function PlatformGate({ children }) {
  const { user, permissions } = useAuth();
  if (!isPlatformUser(user, permissions)) {
    return (
      <div className="space-y-4" data-testid="platform-admin-access-denied">
        <PageHeader title="Platform Admin" subtitle="Operator access is required." />
        <Alert>
          <ShieldCheck className="size-4" />
          <AlertTitle>Platform access required</AlertTitle>
          <AlertDescription>This area is available only to platform administrators.</AlertDescription>
        </Alert>
      </div>
    );
  }
  return children;
}

function StatCard({ title, value, icon: Icon }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent><div className="text-2xl font-semibold">{value ?? 0}</div></CardContent>
    </Card>
  );
}

function MiniRows({ title, rows, columns, empty = "No rows found." }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader><TableRow>{columns.map((column) => <TableHead key={column.key}>{column.label}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {(rows || []).map((row, idx) => <TableRow key={row.id || row.route || row.referrer || row.event_type || row.feature_key || row.status || row.entry_type || idx}>{columns.map((column) => <TableCell key={column.key}>{column.render ? column.render(row) : row[column.key]}</TableCell>)}</TableRow>)}
            {(rows || []).length === 0 && <TableRow><TableCell colSpan={columns.length} className="text-sm text-muted-foreground">{empty}</TableCell></TableRow>}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export default function PlatformAdminPage() {
  const [search, setSearch] = useState("");
  const [data, setData] = useState({ items: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await platformAdminApi.tenants(search));
    } catch (err) {
      setError(extractError(err, "Unable to load tenants"));
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { load(); }, [load]);

  const stats = useMemo(() => {
    const items = data.items || [];
    return {
      tenants: items.length,
      users: items.reduce((sum, t) => sum + (t.user_count || 0), 0),
      suspended: items.filter((t) => t.is_active === false || t.status === "suspended").length,
      founders: items.filter((t) => t.is_founder).length,
    };
  }, [data.items]);

  return (
    <PlatformGate>
      <div className="space-y-4" data-testid="platform-admin-page">
        <PageHeader
          title="Platform Admin"
          subtitle="Tenant oversight, support controls, communications, analytics, and governance."
          actions={<Button size="sm" variant="outline" onClick={load} disabled={loading}><RefreshCcw className="size-4 mr-2" />Refresh</Button>}
        />
        {error && <Alert variant="destructive"><AlertTitle>Unable to load</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/analytics"><BarChart3 className="size-4 mr-2" />Analytics</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/broadcast-email"><Megaphone className="size-4 mr-2" />Broadcast Email</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/site-settings"><Settings className="size-4 mr-2" />Site Settings</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/email-logs"><Mail className="size-4 mr-2" />Email Deliverability</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/audit-log"><ShieldCheck className="size-4 mr-2" />Audit Log</Link></Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard title="Tenants" value={stats.tenants} icon={UserRound} />
          <StatCard title="Users" value={stats.users} icon={UserRound} />
          <StatCard title="Suspended" value={stats.suspended} icon={Ban} />
          <StatCard title="Founders" value={stats.founders} icon={ShieldCheck} />
        </div>
        <Card>
          <CardHeader>
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <CardTitle>Tenant List</CardTitle>
              <label className="relative w-full md:w-80">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, slug, owner email" data-testid="platform-admin-tenant-search" />
              </label>
            </div>
          </CardHeader>
          <CardContent>
            <Table data-testid="platform-admin-tenant-table">
              <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Owner</TableHead><TableHead>Plan</TableHead><TableHead>Users</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
              <TableBody>
                {(data.items || []).map((tenant) => (
                  <TableRow key={tenant.id} className="cursor-pointer" onClick={() => navigate(`/platform-admin/tenants/${tenant.id}`)} data-testid={`platform-admin-tenant-row-${tenant.id}`}>
                    <TableCell className="font-medium">{tenant.name}<div className="text-xs text-muted-foreground">{tenant.slug || tenant.id}</div></TableCell>
                    <TableCell>{tenant.owner_email || "-"}</TableCell>
                    <TableCell>{tenant.plan}</TableCell>
                    <TableCell>{tenant.user_count}</TableCell>
                    <TableCell><Badge variant={statusVariant(tenant.status)}>{tenant.status}</Badge></TableCell>
                  </TableRow>
                ))}
                {(data.items || []).length === 0 && <TableRow><TableCell colSpan={5} className="text-sm text-muted-foreground">No tenants found.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </PlatformGate>
  );
}

export function PlatformAdminTenantDetailPage() {
  const { tenantId } = useParams();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [threshold, setThreshold] = useState("");
  const navigate = useNavigate();

  const load = useCallback(async () => {
    if (!tenantId) return;
    setData(await platformAdminApi.tenant(tenantId));
  }, [tenantId]);

  useEffect(() => { load().catch((err) => toast.error(extractError(err, "Unable to load tenant"))); }, [load]);

  const act = async (fn, success) => {
    setBusy(true);
    try {
      const next = await fn();
      setData(next);
      toast.success(success);
    } catch (err) {
      toast.error(extractError(err, "Action failed"));
    } finally {
      setBusy(false);
    }
  };

  const tenant = data?.tenant;
  const owner = (data?.users || []).find((u) => u.role === "owner") || data?.users?.[0];
  const subscription = data?.billing?.subscription || {};
  const account = data?.billing?.account || {};
  const checklist = data?.onboarding?.items || [];
  const progress = data?.onboarding?.progress || {};

  const startImpersonation = async (userId) => {
    if (!window.confirm("Start support mode as this user? Do not change tenant data without consent.")) return;
    try {
      const result = await platformAdminApi.impersonate(userId);
      localStorage.setItem("signguy.platformToken", localStorage.getItem("signguy.token") || "");
      localStorage.setItem("signguy.token", result.access_token);
      window.location.href = "/";
    } catch (err) {
      toast.error(extractError(err, "Unable to start impersonation"));
    }
  };

  if (!data) {
    return <PlatformGate><div className="text-sm text-muted-foreground">Loading tenant...</div></PlatformGate>;
  }

  return (
    <PlatformGate>
      <div className="space-y-4" data-testid="platform-admin-tenant-detail-page">
        <PageHeader
          title={tenant?.name || "Tenant"}
          subtitle={`${tenant?.owner_email || "No owner email"} - ${tenant?.plan || "unassigned"}`}
          actions={
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => navigate("/platform-admin")}>Back</Button>
              {tenant?.is_active === false ? (
                <Button size="sm" onClick={() => act(() => platformAdminApi.reactivate(tenantId, { note: "", notify_owner: true }), "Tenant reactivated")} disabled={busy}><CheckCircle2 className="size-4 mr-2" />Reactivate</Button>
              ) : (
                <Button size="sm" variant="destructive" onClick={() => {
                  const reason = window.prompt("Reason for suspension");
                  if (reason) act(() => platformAdminApi.suspend(tenantId, reason), "Tenant suspended");
                }} disabled={busy}><Ban className="size-4 mr-2" />Suspend</Button>
              )}
            </div>
          }
        />
        {tenant?.is_active === false && (
          <Alert variant="destructive" data-testid="tenant-suspended-banner">
            <Ban className="size-4" />
            <AlertTitle>Tenant suspended</AlertTitle>
            <AlertDescription>{tenant.suspension_reason || "No reason recorded"} - {dt(tenant.suspended_at)}</AlertDescription>
          </Alert>
        )}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Profile</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Joined</span><span>{dt(tenant.created_at)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Founder</span><Badge variant={tenant.is_founder ? "secondary" : "outline"}>{tenant.is_founder ? "Yes" : "No"}</Badge></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Billing</span><Badge variant={statusVariant(account.status)}>{account.status || "not configured"}</Badge></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Dunning</span><Badge variant="outline">{subscription.dunning_state || "current"}</Badge></div>
            </CardContent>
          </Card>
          <Card data-testid="tenant-billing-card">
            <CardHeader><CardTitle className="text-base">Billing & Dunning</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <div><div className="text-muted-foreground">First failed</div><div>{dt(subscription.first_payment_failed_at)}</div></div>
                <div><div className="text-muted-foreground">Last paid</div><div>{dt(subscription.last_payment_succeeded_at)}</div></div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => act(() => platformAdminApi.markPaid(tenantId, ""), "Marked paid")} disabled={busy}>Mark Paid</Button>
                <Input className="h-9 w-28" value={threshold} onChange={(e) => setThreshold(e.target.value)} placeholder={account.dunning_failure_threshold ? String(account.dunning_failure_threshold) : "default"} />
                <Button size="sm" variant="outline" onClick={() => act(() => platformAdminApi.setThreshold(tenantId, threshold ? Number(threshold) : null), "Threshold saved")} disabled={busy}>Set</Button>
              </div>
            </CardContent>
          </Card>
          <Card data-testid="tenant-email-deliverability-card">
            <CardHeader><CardTitle className="text-base">Email Deliverability</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              {["total", "delivered", "pending", "bounced", "complaints", "failed"].map((k) => (
                <div key={k} className="flex justify-between"><span className="capitalize text-muted-foreground">{k}</span><span>{data.email_summary?.[k] || 0}</span></div>
              ))}
              <Button asChild size="sm" variant="outline"><Link to={`/platform-admin/email-logs?tenant=${tenantId}`}>View Logs</Link></Button>
            </CardContent>
          </Card>
        </div>
        <Tabs defaultValue="users">
          <TabsList><TabsTrigger value="users">Users</TabsTrigger><TabsTrigger value="checklist">Onboarding</TabsTrigger></TabsList>
          <TabsContent value="users">
            <Card>
              <CardHeader><CardTitle className="text-base">Users</CardTitle></CardHeader>
              <CardContent>
                <Table><TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Role</TableHead><TableHead></TableHead></TableRow></TableHeader>
                  <TableBody>{(data.users || []).map((u) => (
                    <TableRow key={u.id}><TableCell>{u.full_name}</TableCell><TableCell>{u.email}</TableCell><TableCell>{u.role}</TableCell><TableCell className="text-right"><Button size="sm" variant="outline" onClick={() => startImpersonation(u.id)} disabled={tenant?.is_active === false}>Impersonate</Button></TableCell></TableRow>
                  ))}</TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="checklist">
            <Card>
              <CardHeader><CardTitle className="text-base">Onboarding Checklist - {progress.percent_complete || 0}%</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {checklist.map((item) => (
                  <div key={item.task_key} className="flex items-center justify-between gap-3 border-b py-2">
                    <div><div className="text-sm font-medium">{item.title}</div><div className="text-xs text-muted-foreground">{item.family} - {item.status}</div></div>
                    <Button size="sm" variant="outline" onClick={() => act(async () => {
                      await api.patch(`/platform-admin/tenants/${tenantId}/checklist/${item.task_key}`, { completed: item.status !== "completed" });
                      return platformAdminApi.tenant(tenantId);
                    }, "Checklist updated")}>{item.status === "completed" ? "Reopen" : "Complete"}</Button>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </PlatformGate>
  );
}

export function PlatformAdminBroadcastEmailPage() {
  const { user } = useAuth();
  const [counts, setCounts] = useState({});
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [target, setTarget] = useState("all_owners");
  const [testTo, setTestTo] = useState(user?.email || "");
  const [result, setResult] = useState(null);
  const htmlBody = useMemo(
    () => body.split(/\n{2,}/).map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br />")}</p>`).join(""),
    [body],
  );

  useEffect(() => { platformAdminApi.broadcastCounts().then(setCounts).catch(() => setCounts({})); }, []);
  const send = async (asTest) => {
    try {
      setResult(await platformAdminApi.sendBroadcast({ subject, html_body: htmlBody, target, test_to: asTest ? testTo : null }));
      toast.success(asTest ? "Test sent" : "Broadcast sent");
    } catch (err) {
      toast.error(extractError(err, "Unable to send broadcast"));
    }
  };

  return (
    <PlatformGate>
      <div className="space-y-4" data-testid="platform-admin-broadcast-page">
        <PageHeader title="Broadcast Email" subtitle="Send one-off emails to tenant owners." actions={<Button asChild size="sm" variant="outline"><Link to="/platform-admin">Back</Link></Button>} />
        <Card><CardContent className="space-y-4 pt-6">
          <div className="grid gap-2"><Label>Subject</Label><Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Service update for {{tenant_name}}" /></div>
          <div className="grid gap-2"><Label>Body</Label><Textarea rows={10} value={body} onChange={(e) => setBody(e.target.value)} placeholder="Hi {{owner_first_name}}, ..." /></div>
          <div className="grid gap-2 md:grid-cols-3">
            <div className="grid gap-2"><Label>Audience</Label><Select value={target} onValueChange={setTarget}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all_owners">All tenant owners ({counts.all_owners || 0})</SelectItem><SelectItem value="active_only">Active only ({counts.active_only || 0})</SelectItem><SelectItem value="suspended_only">Suspended only ({counts.suspended_only || 0})</SelectItem><SelectItem value="founders_only">Founders only ({counts.founders_only || 0})</SelectItem></SelectContent></Select></div>
            <div className="grid gap-2"><Label>Test recipient</Label><Input value={testTo} onChange={(e) => setTestTo(e.target.value)} /></div>
            <div className="flex items-end gap-2"><Button variant="outline" onClick={() => send(true)}>Send Test</Button><Button onClick={() => window.confirm(`Send to ${counts[target] || 0} tenant owners?`) && send(false)}>Send Broadcast</Button></div>
          </div>
        </CardContent></Card>
        {result && <Alert><Mail className="size-4" /><AlertTitle>{result.mode}</AlertTitle><AlertDescription>{result.sent_count} sent, {result.failed_count} failed.</AlertDescription></Alert>}
      </div>
    </PlatformGate>
  );
}

export function PlatformAdminSiteSettingsPage() {
  const [settings, setSettings] = useState({});
  const [message, setMessage] = useState("");
  const [severity, setSeverity] = useState("info");
  const [dismissable, setDismissable] = useState(true);
  const [expiresAt, setExpiresAt] = useState("");
  const [maintenanceMessage, setMaintenanceMessage] = useState("");
  const load = useCallback(async () => {
    const data = await platformAdminApi.settings();
    setSettings(data);
    setMessage(data.announcement?.message || "");
    setSeverity(data.announcement?.severity || "info");
    setDismissable(data.announcement?.dismissable !== false);
    setExpiresAt(datetimeLocalValue(data.announcement?.expires_at));
    setMaintenanceMessage(data.maintenance?.message || "");
  }, []);
  useEffect(() => { load().catch(() => {}); }, [load]);
  const maintenance = settings.maintenance || { enabled: false };
  return (
    <PlatformGate>
      <div className="space-y-4" data-testid="site-settings-page">
        <PageHeader title="Site Settings" subtitle="Announcement banner and maintenance mode." actions={<Button asChild size="sm" variant="outline"><Link to="/platform-admin">Back</Link></Button>} />
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <Card><CardHeader><CardTitle className="text-base">Announcement Banner</CardTitle></CardHeader><CardContent className="space-y-3">
            <Textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Welcome to SignGuy AI." />
            <div className="grid gap-3 md:grid-cols-[160px_1fr_auto] md:items-end">
              <div className="grid gap-1.5"><Label>Severity</Label><Select value={severity} onValueChange={setSeverity}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="info">Info</SelectItem><SelectItem value="warning">Warning</SelectItem><SelectItem value="critical">Critical</SelectItem></SelectContent></Select></div>
              <div className="grid gap-1.5"><Label>Expires at</Label><Input type="datetime-local" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} /></div>
              <label className="flex items-center gap-2 pb-2 text-sm"><Checkbox checked={dismissable} onCheckedChange={setDismissable} />Dismissable</label>
            </div>
            <div className="flex gap-2"><Button onClick={() => platformAdminApi.setAnnouncement({ message, severity, dismissable, expires_at: expiresAt || null }).then(load).then(() => toast.success("Announcement saved"))}>Publish</Button><Button variant="outline" onClick={() => platformAdminApi.setAnnouncement({ message: "" }).then(load).then(() => toast.success("Announcement cleared"))}>Clear</Button></div>
          </CardContent></Card>
          <Card data-testid="site-settings-maintenance-card"><CardHeader><CardTitle className="text-base flex items-center gap-2"><Wrench className="size-4" />Maintenance Mode {maintenance.enabled && <Badge variant="destructive">On</Badge>}</CardTitle></CardHeader><CardContent className="space-y-3">
            <Textarea value={maintenanceMessage} onChange={(e) => setMaintenanceMessage(e.target.value)} placeholder="Scheduled maintenance, back shortly." />
            <div className="flex gap-2">{maintenance.enabled ? <Button variant="outline" onClick={() => platformAdminApi.setMaintenance({ enabled: false }).then(load).then(() => toast.success("Maintenance disabled"))}>Disable</Button> : <Button variant="destructive" onClick={() => platformAdminApi.setMaintenance({ enabled: true, message: maintenanceMessage }).then(load).then(() => toast.success("Maintenance enabled"))}>Enable</Button>}</div>
            {maintenance.enabled && <div className="text-xs text-muted-foreground">Started {dt(maintenance.started_at)} by {maintenance.started_by_email}</div>}
          </CardContent></Card>
        </div>
      </div>
    </PlatformGate>
  );
}

export function PlatformAdminEmailLogsPage() {
  const [params] = useSearchParams();
  const [tenantId, setTenantId] = useState(params.get("tenant") || "");
  const [toEmail, setToEmail] = useState("");
  const [status, setStatus] = useState("all");
  const [since, setSince] = useState("");
  const [selected, setSelected] = useState(null);
  const [data, setData] = useState({ items: [] });
  const [summary, setSummary] = useState({});
  const load = useCallback(async () => {
    const p = {
      tenant_id: tenantId || undefined,
      to_email: toEmail || undefined,
      status: status === "all" ? undefined : status,
      since: since || undefined,
    };
    setData(await platformAdminApi.emailLogs(p));
    setSummary(await platformAdminApi.emailSummary(p));
  }, [since, status, tenantId, toEmail]);
  useEffect(() => { load().catch(() => {}); }, [load]);
  return (
    <PlatformGate>
      <LogTablePage
        title="Email Deliverability"
        back="/platform-admin"
        filters={<><Input placeholder="Tenant ID" value={tenantId} onChange={(e) => setTenantId(e.target.value)} /><Input placeholder="Recipient email" value={toEmail} onChange={(e) => setToEmail(e.target.value)} /><Select value={status} onValueChange={setStatus}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["all", "queued", "sent", "delivered", "failed", "skipped"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select><Input type="datetime-local" value={since} onChange={(e) => setSince(e.target.value)} /><Button onClick={load}>Apply</Button></>}
        summary={summary}
        rows={data.items || []}
        onSelect={setSelected}
      />
      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Email Events</DialogTitle>
            <DialogDescription>{selected?.subject || "Outgoing email"} - {selected?.to_email}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <div className="grid gap-2 md:grid-cols-3"><div><span className="text-muted-foreground">Tenant</span><div>{selected?.tenant_id || "-"}</div></div><div><span className="text-muted-foreground">Status</span><div>{selected?.status || "-"}</div></div><div><span className="text-muted-foreground">SendGrid</span><div className="break-all">{selected?.sendgrid_message_id || "-"}</div></div></div>
            <Table><TableHeader><TableRow><TableHead>When</TableHead><TableHead>Event</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader><TableBody>{(selected?.events || []).map((event, idx) => <TableRow key={`${event.event || "event"}-${idx}`}><TableCell>{dt(event.event_timestamp || event.created_at)}</TableCell><TableCell>{event.event || event.status || "-"}</TableCell><TableCell>{event.reason || event.response || event.url || "-"}</TableCell></TableRow>)}{(selected?.events || []).length === 0 && <TableRow><TableCell colSpan={3} className="text-sm text-muted-foreground">No provider events captured for this email yet.</TableCell></TableRow>}</TableBody></Table>
          </div>
        </DialogContent>
      </Dialog>
    </PlatformGate>
  );
}

function LogTablePage({ title, back, filters, summary, rows, onSelect }) {
  return (
    <div className="space-y-4" data-testid="platform-admin-email-logs-page">
      <PageHeader title={title} subtitle="Delivery state and provider events." actions={<Button asChild size="sm" variant="outline"><Link to={back}>Back</Link></Button>} />
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">{["total", "delivered", "pending", "bounced", "complaints", "failed"].map((k) => <StatCard key={k} title={k} value={summary?.[k] || 0} icon={Mail} />)}</div>
      <Card><CardContent className="flex flex-col gap-2 pt-6 md:flex-row">{filters}</CardContent></Card>
      <Card><CardContent className="pt-6"><Table><TableHeader><TableRow><TableHead>When</TableHead><TableHead>Tenant</TableHead><TableHead>Recipient</TableHead><TableHead>Subject</TableHead><TableHead>Status</TableHead><TableHead>SendGrid</TableHead></TableRow></TableHeader><TableBody>{rows.map((row) => <TableRow key={row.id} className={onSelect ? "cursor-pointer" : ""} onClick={() => onSelect?.(row)}><TableCell>{dt(row.created_at)}</TableCell><TableCell className="text-xs">{row.tenant_id || "-"}</TableCell><TableCell>{row.to_email}</TableCell><TableCell>{row.subject}</TableCell><TableCell><Badge variant={statusVariant(row.status)}>{row.status}</Badge></TableCell><TableCell className="text-xs">{row.sendgrid_message_id || "-"}</TableCell></TableRow>)}{rows.length === 0 && <TableRow><TableCell colSpan={6} className="text-sm text-muted-foreground">No email logs found.</TableCell></TableRow>}</TableBody></Table></CardContent></Card>
    </div>
  );
}

export function PlatformAdminAuditLogPage() {
  const [action, setAction] = useState("");
  const [actorEmail, setActorEmail] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [rows, setRows] = useState([]);
  const load = useCallback(async () => {
    const data = await platformAdminApi.auditLog({ action: action || undefined, actor_email: actorEmail || undefined, tenant_id: tenantId || undefined });
    setRows(data.items || []);
  }, [action, actorEmail, tenantId]);
  useEffect(() => { load().catch(() => {}); }, [load]);
  return (
    <PlatformGate>
      <div className="space-y-4" data-testid="platform-admin-audit-log-page">
        <PageHeader title="Audit Log" subtitle="Privileged Platform Admin and tenant actions." actions={<Button asChild size="sm" variant="outline"><Link to="/platform-admin">Back</Link></Button>} />
        <Card><CardContent className="grid gap-2 pt-6 md:grid-cols-4"><Input placeholder="Action" value={action} onChange={(e) => setAction(e.target.value)} /><Input placeholder="Actor email" value={actorEmail} onChange={(e) => setActorEmail(e.target.value)} /><Input placeholder="Tenant ID" value={tenantId} onChange={(e) => setTenantId(e.target.value)} /><Button onClick={load}>Apply</Button></CardContent></Card>
        <Card><CardContent className="pt-6"><Table data-testid="audit-log-table"><TableHeader><TableRow><TableHead>When</TableHead><TableHead>Actor</TableHead><TableHead>Action</TableHead><TableHead>Target</TableHead><TableHead>Summary</TableHead></TableRow></TableHeader><TableBody>{rows.map((row) => <TableRow key={row.id}><TableCell>{dt(row.created_at)}</TableCell><TableCell>{row.actor_email}</TableCell><TableCell className="font-mono text-xs">{row.action}</TableCell><TableCell>{row.entity_type}:{row.entity_id}</TableCell><TableCell>{row.summary}</TableCell></TableRow>)}{rows.length === 0 && <TableRow><TableCell colSpan={5} className="text-sm text-muted-foreground">No audit rows found.</TableCell></TableRow>}</TableBody></Table></CardContent></Card>
      </div>
    </PlatformGate>
  );
}

export function PlatformAdminAnalyticsPage() {
  const [range, setRange] = useState("30d");
  const [data, setData] = useState(null);
  const load = useCallback(() => platformAdminApi.analytics(range).then(setData), [range]);
  useEffect(() => { load().catch(() => {}); }, [load]);
  const o = data?.overview || {};
  return (
    <PlatformGate>
      <div className="space-y-4" data-testid="platform-admin-analytics-page">
        <PageHeader title="Platform Analytics" subtitle="Activity, adoption, commercial conversion, AI cost, and suspicious activity." actions={<Button asChild size="sm" variant="outline"><Link to="/platform-admin">Back</Link></Button>} />
        <div className="flex gap-2">{["today", "7d", "14d", "30d"].map((r) => <Button key={r} size="sm" variant={range === r ? "default" : "outline"} onClick={() => setRange(r)}>{r}</Button>)}</div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard title="Tenants" value={o.total_tenants} icon={UserRound} />
          <StatCard title="Users" value={o.total_users} icon={UserRound} />
          <StatCard title="Sessions" value={o.sessions} icon={BarChart3} />
          <StatCard title="Visitors" value={o.visitors} icon={BarChart3} />
          <StatCard title="Subscriptions" value={o.subscriptions} icon={ShieldCheck} />
          <StatCard title="Dunning" value={o.dunning_subscriptions} icon={Ban} />
          <StatCard title="New Orders" value={o.new_orders} icon={BarChart3} />
          <StatCard title="New Quotes" value={o.new_quotes} icon={BarChart3} />
          <StatCard title="AI Usage" value={o.ai_usage_events} icon={BarChart3} />
          <StatCard title="AI Cost Cents" value={data?.ai_cost?.actual_cost_cents || 0} icon={BarChart3} />
          <StatCard title="Errors" value={o.error_events} icon={Ban} />
          <StatCard title="Suspicious" value={o.suspicious_events} icon={Ban} />
          <StatCard title="Active Tenants" value={o.active_tenants_in_period} icon={UserRound} />
        </div>
        <Card><CardHeader><CardTitle className="text-base">Activity Chart</CardTitle></CardHeader><CardContent><Table><TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Users</TableHead><TableHead>Quotes</TableHead><TableHead>Orders</TableHead><TableHead>Events</TableHead></TableRow></TableHeader><TableBody>{(data?.activity_chart || []).map((b) => <TableRow key={b.date}><TableCell>{b.date}</TableCell><TableCell>{b.users}</TableCell><TableCell>{b.quotes}</TableCell><TableCell>{b.orders}</TableCell><TableCell>{b.events}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <MiniRows title="Routes" rows={data?.routes || []} columns={[{ key: "route", label: "Route" }, { key: "events", label: "Events" }, { key: "sessions", label: "Sessions" }]} />
          <MiniRows title="Referrers" rows={data?.referrers || []} columns={[{ key: "referrer", label: "Referrer" }, { key: "events", label: "Events" }, { key: "visitors", label: "Visitors" }]} />
          <MiniRows title="Feature Usage" rows={data?.feature_usage || []} columns={[{ key: "event_type", label: "Event" }, { key: "events", label: "Events" }, { key: "sessions", label: "Sessions" }]} />
          <MiniRows title="AI Feature Usage" rows={data?.ai_feature_usage || []} columns={[{ key: "feature_key", label: "Feature" }, { key: "uses", label: "Uses" }, { key: "credits", label: "Credits" }]} />
          <MiniRows title="Trial Funnel" rows={data?.trial_funnel || []} columns={[{ key: "status", label: "Status" }, { key: "count", label: "Count" }]} />
          <MiniRows title="AI Credit Activity" rows={data?.ai_credit_activity || []} columns={[{ key: "entry_type", label: "Type" }, { key: "credits", label: "Credits" }, { key: "count", label: "Rows" }]} />
        </div>
      </div>
    </PlatformGate>
  );
}
