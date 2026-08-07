import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
  Activity,
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  Eye,
  Globe,
  Mail,
  Megaphone,
  RefreshCcw,
  Search,
  Settings,
  ShieldCheck,
  ScrollText,
  TrendingUp,
  UserRound,
  Wrench,
} from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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
  const [seeding, setSeeding] = useState(false);
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

  const loadSampleData = async () => {
    setSeeding(true);
    setError("");
    try {
      await platformAdminApi.seedSampleData();
      toast.success("Sample Platform Admin data loaded");
      await load();
    } catch (err) {
      setError(extractError(err, "Unable to load sample data"));
    } finally {
      setSeeding(false);
    }
  };

  const stats = useMemo(() => {
    const summary = data.summary || {};
    const items = data.items || [];
    return {
      tenants: summary.total_tenants ?? data.total ?? items.length,
      users: summary.total_users ?? items.reduce((sum, t) => sum + (t.user_count || 0), 0),
      suspended: summary.suspended_tenants ?? items.filter((t) => t.is_active === false || t.status === "suspended").length,
      founders: summary.founder_tenants ?? items.filter((t) => t.is_founder).length,
    };
  }, [data]);

  return (
    <PlatformGate>
      <div className="space-y-4" data-testid="platform-admin-page">
        <PageHeader
          title="Platform Admin"
          subtitle="Tenant oversight, support controls, communications, analytics, and governance."
          actions={<div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={loadSampleData} disabled={seeding}>{seeding ? "Loading..." : "Load Sample Data"}</Button><Button size="sm" variant="outline" onClick={load} disabled={loading}><RefreshCcw className="size-4 mr-2" />Refresh</Button></div>}
        />
        {error && <Alert variant="destructive"><AlertTitle>Unable to load</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/analytics"><BarChart3 className="size-4 mr-2" />Analytics</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/broadcast-email"><Megaphone className="size-4 mr-2" />Broadcast Email</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/site-settings"><Settings className="size-4 mr-2" />Site Settings</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/email-logs"><Mail className="size-4 mr-2" />Email Deliverability</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/audit-log"><ShieldCheck className="size-4 mr-2" />Audit Log</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/platform-admin/impersonation-logs"><ScrollText className="size-4 mr-2" />Impersonation Logs</Link></Button>
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
              <CardTitle>Tenant List {data.total != null && <span className="text-sm font-normal text-muted-foreground">({(data.items || []).length} of {data.total})</span>}</CardTitle>
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
                {(data.items || []).length === 0 && <TableRow><TableCell colSpan={5} className="space-y-2 text-sm text-muted-foreground"><div>No tenants found.</div><Button size="sm" variant="outline" onClick={loadSampleData} disabled={seeding}>{seeding ? "Loading sample data..." : "Load sample tenants"}</Button></TableCell></TableRow>}
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
  const [loadError, setLoadError] = useState("");
  const [suspendOpen, setSuspendOpen] = useState(false);
  const [suspensionReason, setSuspensionReason] = useState("");
  const [reactivateOpen, setReactivateOpen] = useState(false);
  const [reactivateNote, setReactivateNote] = useState("");
  const [notifyOwner, setNotifyOwner] = useState(true);
  const [thresholdOpen, setThresholdOpen] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoadError("");
    try {
      setData(await platformAdminApi.tenant(tenantId));
    } catch (err) {
      setLoadError(extractError(err, "Unable to load tenant"));
      setData(null);
    }
  }, [tenantId]);

  useEffect(() => { load(); }, [load]);

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
  const dunning = data?.billing?.dunning || {};
  const checklist = data?.onboarding?.items || [];
  const progress = data?.onboarding?.progress || {};
  const tenantAuditEvents = data?.audit_events || [];
  const tenantImpersonationLogs = data?.impersonation_logs || [];
  const reviewAfterDays = dunning.review_after_days || account.dunning_review_after_days || account.dunning_failure_threshold || 15;

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

  if (loadError) {
    return (
      <PlatformGate>
        <div className="space-y-4" data-testid="platform-admin-tenant-load-error">
          <PageHeader title="Tenant" subtitle="The tenant detail could not be loaded." actions={<Button size="sm" variant="outline" onClick={() => navigate("/platform-admin")}>Back</Button>} />
          <Alert variant="destructive"><AlertTitle>Unable to load tenant</AlertTitle><AlertDescription>{loadError}</AlertDescription></Alert>
        </div>
      </PlatformGate>
    );
  }

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
                <Button size="sm" onClick={() => setReactivateOpen(true)} disabled={busy}><CheckCircle2 className="size-4 mr-2" />Reactivate</Button>
              ) : (
                <Button size="sm" variant="destructive" onClick={() => setSuspendOpen(true)} disabled={busy}><Ban className="size-4 mr-2" />Suspend</Button>
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
              <div className="flex justify-between"><span className="text-muted-foreground">Last activity</span><span>{dt(tenant.last_activity_at)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Founder</span><Badge variant={tenant.is_founder ? "secondary" : "outline"}>{tenant.is_founder ? "Yes" : "No"}</Badge></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Billing</span><Badge variant={statusVariant(account.status)}>{account.status || "not configured"}</Badge></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Dunning</span><Badge variant="outline">{dunning.state || subscription.dunning_state || "current"}</Badge></div>
            </CardContent>
          </Card>
          <Card data-testid="tenant-billing-card">
            <CardHeader><CardTitle className="text-base">Billing & Dunning</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <div><div className="text-muted-foreground">Stage</div><div>{dunning.state || "current"}</div></div>
                <div><div className="text-muted-foreground">Days past due</div><div>{dunning.days_past_due ?? 0}</div></div>
                <div><div className="text-muted-foreground">Failed since</div><div>{dt(dunning.failed_since)}</div></div>
                <div><div className="text-muted-foreground">Last failed</div><div>{dt(dunning.last_failed_at)}</div></div>
                <div><div className="text-muted-foreground">Last paid</div><div>{dt(dunning.last_paid_at)}</div></div>
                <div><div className="text-muted-foreground">Review day</div><div>{reviewAfterDays}</div></div>
                <div><div className="text-muted-foreground">Review eligible</div><div>{dt(dunning.review_eligible_at)}</div></div>
                <div><div className="text-muted-foreground">Grace until</div><div>{dt(dunning.manual_grace_until)}</div></div>
              </div>
              {dunning.suspension_review_eligible && <Alert variant="destructive"><AlertTriangle className="size-4" /><AlertTitle>Suspension review eligible</AlertTitle><AlertDescription>This tenant is past the configured dunning review day.</AlertDescription></Alert>}
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => act(() => platformAdminApi.markPaid(tenantId, ""), "Marked paid")} disabled={busy}>Mark Paid</Button>
                <Button size="sm" variant="outline" onClick={() => { setThreshold(reviewAfterDays ? String(reviewAfterDays) : ""); setThresholdOpen(true); }} disabled={busy}>Set Review Day</Button>
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
          <TabsList className="flex h-auto flex-wrap justify-start"><TabsTrigger value="users">Overview & Users</TabsTrigger><TabsTrigger value="checklist">Onboarding</TabsTrigger><TabsTrigger value="support">Support Log</TabsTrigger></TabsList>
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
          <TabsContent value="support" className="space-y-4">
            <MiniRows title="Recent Tenant Audit Events" rows={tenantAuditEvents} columns={[{ key: "created_at", label: "When", render: (row) => dt(row.created_at) }, { key: "actor_email", label: "Actor" }, { key: "action", label: "Action" }, { key: "entity_type", label: "Target" }, { key: "summary", label: "Summary" }]} />
            <MiniRows title="Support Impersonation Sessions" rows={tenantImpersonationLogs} columns={[{ key: "started_at", label: "Started", render: (row) => dt(row.started_at) }, { key: "platform_admin_email", label: "Platform Admin" }, { key: "target_user_email", label: "Target User" }, { key: "ended_at", label: "Ended", render: (row) => dt(row.ended_at) }, { key: "duration_seconds", label: "Duration" }]} />
          </TabsContent>
        </Tabs>
        <Dialog open={suspendOpen} onOpenChange={setSuspendOpen}>
          <DialogContent data-testid="tenant-suspend-dialog">
            <DialogHeader><DialogTitle>Suspend Tenant</DialogTitle><DialogDescription>Record a clear reason. Tenant users will be blocked from normal app access.</DialogDescription></DialogHeader>
            <div className="space-y-3"><Textarea value={suspensionReason} onChange={(e) => setSuspensionReason(e.target.value)} placeholder="Reason for suspension" rows={4} /><div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setSuspendOpen(false)}>Cancel</Button><Button variant="destructive" disabled={busy || !suspensionReason.trim()} onClick={() => act(async () => { const next = await platformAdminApi.suspend(tenantId, suspensionReason.trim()); setSuspendOpen(false); setSuspensionReason(""); return next; }, "Tenant suspended")}>Suspend Tenant</Button></div></div>
          </DialogContent>
        </Dialog>
        <Dialog open={reactivateOpen} onOpenChange={setReactivateOpen}>
          <DialogContent data-testid="tenant-reactivate-dialog">
            <DialogHeader><DialogTitle>Reactivate Tenant</DialogTitle><DialogDescription>Reactivate access and optionally notify the owner.</DialogDescription></DialogHeader>
            <div className="space-y-3"><Textarea value={reactivateNote} onChange={(e) => setReactivateNote(e.target.value)} placeholder="Optional note for the owner or audit trail" rows={4} /><label className="flex items-center gap-2 text-sm"><Checkbox checked={notifyOwner} onCheckedChange={setNotifyOwner} />Notify owner</label><div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setReactivateOpen(false)}>Cancel</Button><Button disabled={busy} onClick={() => act(async () => { const next = await platformAdminApi.reactivate(tenantId, { note: reactivateNote, notify_owner: notifyOwner }); setReactivateOpen(false); setReactivateNote(""); return next; }, "Tenant reactivated")}>Reactivate Tenant</Button></div></div>
          </DialogContent>
        </Dialog>
        <Dialog open={thresholdOpen} onOpenChange={setThresholdOpen}>
          <DialogContent data-testid="tenant-threshold-dialog">
            <DialogHeader><DialogTitle>Set Dunning Review Day</DialogTitle><DialogDescription>Override the day after first failed payment when this tenant becomes eligible for suspension review. Leave blank to use the default day 15 review.</DialogDescription></DialogHeader>
            <div className="space-y-3"><Input type="number" min="1" max="45" value={threshold} onChange={(e) => setThreshold(e.target.value)} placeholder="15" /><div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setThresholdOpen(false)}>Cancel</Button><Button disabled={busy} onClick={() => act(async () => { const next = await platformAdminApi.setThreshold(tenantId, threshold ? Number(threshold) : null); setThresholdOpen(false); return next; }, "Review day saved")}>Save Review Day</Button></div></div>
          </DialogContent>
        </Dialog>
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
  const [entityType, setEntityType] = useState("all");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [options, setOptions] = useState({ actions: [], entity_types: [] });
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(null);
  const load = useCallback(async () => {
    const data = await platformAdminApi.auditLog({
      action: action && action !== "all" ? action : undefined,
      actor_email: actorEmail || undefined,
      tenant_id: tenantId || undefined,
      entity_type: entityType !== "all" ? entityType : undefined,
      since: since || undefined,
      until: until || undefined,
    });
    setRows(data.items || []);
  }, [action, actorEmail, entityType, since, tenantId, until]);
  useEffect(() => { load().catch(() => {}); }, [load]);
  useEffect(() => { platformAdminApi.auditActions().then(setOptions).catch(() => setOptions({ actions: [], entity_types: [] })); }, []);
  const inspect = async (row) => {
    setSelected(row);
    try {
      setSelected(await platformAdminApi.auditEntry(row.id));
    } catch {
      setSelected(row);
    }
  };
  return (
    <PlatformGate>
      <div className="space-y-4" data-testid="platform-admin-audit-log-page">
        <PageHeader title="Audit Log" subtitle="Privileged Platform Admin and tenant actions." actions={<Button asChild size="sm" variant="outline"><Link to="/platform-admin">Back</Link></Button>} />
        <Card><CardContent className="grid gap-2 pt-6 md:grid-cols-3 xl:grid-cols-7">
          <Select value={action || "all"} onValueChange={setAction}><SelectTrigger><SelectValue placeholder="Action" /></SelectTrigger><SelectContent><SelectItem value="all">All actions</SelectItem>{(options.actions || []).map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}</SelectContent></Select>
          <Select value={entityType} onValueChange={setEntityType}><SelectTrigger><SelectValue placeholder="Target" /></SelectTrigger><SelectContent><SelectItem value="all">All targets</SelectItem>{(options.entity_types || []).map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}</SelectContent></Select>
          <Input placeholder="Actor email" value={actorEmail} onChange={(e) => setActorEmail(e.target.value)} />
          <Input placeholder="Tenant ID" value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
          <Input type="datetime-local" value={since} onChange={(e) => setSince(e.target.value)} />
          <Input type="datetime-local" value={until} onChange={(e) => setUntil(e.target.value)} />
          <Button onClick={load}>Apply</Button>
        </CardContent></Card>
        <Card><CardContent className="pt-6"><Table data-testid="audit-log-table"><TableHeader><TableRow><TableHead>When</TableHead><TableHead>Actor</TableHead><TableHead>Action</TableHead><TableHead>Target</TableHead><TableHead>Summary</TableHead></TableRow></TableHeader><TableBody>{rows.map((row) => <TableRow key={row.id} className="cursor-pointer" onClick={() => inspect(row)}><TableCell>{dt(row.created_at)}</TableCell><TableCell>{row.actor_email}</TableCell><TableCell className="font-mono text-xs">{row.action}</TableCell><TableCell>{row.entity_type}:{row.entity_id}</TableCell><TableCell>{row.summary}</TableCell></TableRow>)}{rows.length === 0 && <TableRow><TableCell colSpan={5} className="text-sm text-muted-foreground">No audit rows found.</TableCell></TableRow>}</TableBody></Table></CardContent></Card>
      </div>
      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Audit Detail</DialogTitle>
            <DialogDescription>{selected?.action || "Audit event"} - {dt(selected?.created_at)}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 text-sm md:grid-cols-2">
            <div><span className="text-muted-foreground">Actor</span><div>{selected?.actor_email || "-"}</div></div>
            <div><span className="text-muted-foreground">Tenant</span><div>{selected?.tenant_id || "-"}</div></div>
            <div><span className="text-muted-foreground">Target</span><div>{selected?.entity_type || "-"}:{selected?.entity_id || "-"}</div></div>
            <div><span className="text-muted-foreground">Summary</span><div>{selected?.summary || "-"}</div></div>
          </div>
          <pre className="max-h-80 overflow-auto rounded border bg-muted p-3 text-xs">{JSON.stringify(selected?.diff || {}, null, 2)}</pre>
        </DialogContent>
      </Dialog>
    </PlatformGate>
  );
}

export function PlatformAdminImpersonationLogsPage() {
  const [tenantId, setTenantId] = useState("");
  const [rows, setRows] = useState([]);
  const [busyId, setBusyId] = useState("");
  const load = useCallback(async () => {
    const data = await platformAdminApi.impersonationLogs({ tenant_id: tenantId || undefined });
    setRows(data.items || []);
  }, [tenantId]);
  useEffect(() => { load().catch(() => {}); }, [load]);
  const endSession = async (row) => {
    setBusyId(row.id);
    try {
      await platformAdminApi.endImpersonation(row.id);
      await load();
      toast.success("Impersonation session ended");
    } catch (err) {
      toast.error(extractError(err, "Unable to end impersonation"));
    } finally {
      setBusyId("");
    }
  };
  return (
    <PlatformGate>
      <div className="space-y-4" data-testid="platform-admin-impersonation-logs-page">
        <PageHeader title="Impersonation Logs" subtitle="Support-mode access, duration, and audit trail." actions={<Button asChild size="sm" variant="outline"><Link to="/platform-admin">Back</Link></Button>} />
        <Card><CardContent className="grid gap-2 pt-6 md:grid-cols-[1fr_auto]"><Input placeholder="Tenant ID" value={tenantId} onChange={(e) => setTenantId(e.target.value)} /><Button onClick={load}>Apply</Button></CardContent></Card>
        <Card><CardContent className="pt-6"><Table><TableHeader><TableRow><TableHead>Started</TableHead><TableHead>Platform Admin</TableHead><TableHead>Target User</TableHead><TableHead>Tenant</TableHead><TableHead>Status</TableHead><TableHead></TableHead></TableRow></TableHeader><TableBody>{rows.map((row) => <TableRow key={row.id}><TableCell>{dt(row.started_at)}</TableCell><TableCell>{row.platform_admin_email}</TableCell><TableCell>{row.target_user_email}</TableCell><TableCell>{row.tenant_name || row.tenant_id}</TableCell><TableCell><Badge variant={row.ended_at ? "outline" : "secondary"}>{row.ended_at ? `Ended ${dt(row.ended_at)}` : "Active"}</Badge></TableCell><TableCell className="text-right">{!row.ended_at && <Button size="sm" variant="outline" disabled={busyId === row.id} onClick={() => endSession(row)}>End</Button>}</TableCell></TableRow>)}{rows.length === 0 && <TableRow><TableCell colSpan={6} className="text-sm text-muted-foreground">No impersonation sessions found.</TableCell></TableRow>}</TableBody></Table></CardContent></Card>
      </div>
    </PlatformGate>
  );
}

export function PlatformAdminAnalyticsPage() {
  const [range, setRange] = useState("30d");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await platformAdminApi.analytics(range, {
        custom_start: range === "custom" ? customStart || undefined : undefined,
        custom_end: range === "custom" ? customEnd || undefined : undefined,
      }));
    } catch (err) {
      setError(extractError(err, "Unable to load analytics"));
    } finally {
      setLoading(false);
    }
  }, [customEnd, customStart, range]);
  useEffect(() => { load(); }, [load]);
  const o = data?.overview || {};
  const chartRows = data?.activity_chart || [];
  const errors = data?.errors_detail || {};
  const suspicious = data?.suspicious_detail || {};
  return (
    <PlatformGate>
      <div className="space-y-4" data-testid="platform-admin-analytics-page">
        <PageHeader
          title="Platform Analytics"
          subtitle="Activity, adoption, commercial conversion, AI cost, errors, sessions, referrers, and suspicious traffic."
          actions={<div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={load} disabled={loading}><RefreshCcw className="size-4 mr-2" />{loading ? "Loading" : "Refresh"}</Button><Button asChild size="sm" variant="outline"><Link to="/platform-admin">Back</Link></Button></div>}
        />
        {error && <Alert variant="destructive"><AlertTitle>Unable to load analytics</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
        <div className="flex flex-wrap items-center gap-2" data-testid="analytics-date-range-controls">
          {["today", "yesterday", "7d", "14d", "30d", "custom"].map((r) => <Button key={r} size="sm" variant={range === r ? "default" : "outline"} onClick={() => setRange(r)}>{r}</Button>)}
          {range === "custom" && (
            <div className="flex flex-wrap items-center gap-2">
              <Input type="date" className="h-9 w-40" value={customStart} onChange={(e) => setCustomStart(e.target.value)} />
              <Input type="date" className="h-9 w-40" value={customEnd} onChange={(e) => setCustomEnd(e.target.value)} />
              <Button size="sm" onClick={load}>Apply</Button>
            </div>
          )}
        </div>
        <Alert>
          <Activity className="size-4" />
          <AlertTitle>Real usage versus collecting signals</AlertTitle>
          <AlertDescription>Business records such as users, orders, quotes, subscriptions, and audit actions are existing system data. Session, route, referrer, error, and suspicious-traffic analytics collect from browser/API event tracking and will grow as the app is used.</AlertDescription>
        </Alert>
        <Tabs defaultValue="overview" data-testid="analytics-tabs">
          <TabsList className="flex h-auto flex-wrap justify-start">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="charts">Charts</TabsTrigger>
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="routes">Routes</TabsTrigger>
            <TabsTrigger value="sessions">Sessions</TabsTrigger>
            <TabsTrigger value="referrers">Referrers</TabsTrigger>
            <TabsTrigger value="errors">Errors</TabsTrigger>
            <TabsTrigger value="suspicious">Suspicious</TabsTrigger>
            <TabsTrigger value="commercial">Commercial</TabsTrigger>
            <TabsTrigger value="ai">AI Cost</TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <StatCard title="Tenants" value={o.total_tenants} icon={UserRound} />
              <StatCard title="Users" value={o.total_users} icon={UserRound} />
              <StatCard title="New Users" value={o.new_users} icon={UserRound} />
              <StatCard title="Orders" value={o.total_orders} icon={BarChart3} />
              <StatCard title="New Orders" value={o.new_orders} icon={BarChart3} />
              <StatCard title="New Quotes" value={o.new_quotes} icon={BarChart3} />
              <StatCard title="Webstores" value={o.total_webstores} icon={Globe} />
              <StatCard title="New Webstores" value={o.new_webstores} icon={Globe} />
              <StatCard title="Sessions" value={o.total_sessions || o.sessions} icon={Eye} />
              <StatCard title="Visitors" value={o.total_visitors || o.visitors} icon={Eye} />
              <StatCard title="Page Views" value={o.page_views} icon={Activity} />
              <StatCard title="Logged-in Events" value={o.logged_in_visits} icon={ShieldCheck} />
              <StatCard title="Anonymous Events" value={o.anonymous_visits} icon={Activity} />
              <StatCard title="Bot Events" value={o.bot_events} icon={Bot} />
              <StatCard title="Errors" value={o.error_events} icon={AlertTriangle} />
              <StatCard title="Suspicious" value={o.suspicious_events} icon={Ban} />
            </div>
            <Card>
              <CardHeader><CardTitle className="text-base">Real Usage Breakdown</CardTitle><CardDescription>Meaningful business activity separated from request/event volume.</CardDescription></CardHeader>
              <CardContent>
                <Table><TableHeader><TableRow><TableHead>Signal</TableHead><TableHead>Source</TableHead><TableHead className="text-right">Count</TableHead></TableRow></TableHeader><TableBody>{[
                  ["Logged-in app events", "analytics_events", o.logged_in_visits],
                  ["Anonymous visitor events", "analytics_events", o.anonymous_visits],
                  ["New accounts", "users", o.new_users],
                  ["Business actions", "orders + quotes + webstores", (o.new_orders || 0) + (o.new_quotes || 0) + (o.new_webstores || 0)],
                  ["Audit actions", "audit_events", o.audit_actions],
                  ["Error events", "analytics_events", o.error_events],
                ].map((row) => <TableRow key={row[0]}><TableCell>{row[0]}</TableCell><TableCell className="text-muted-foreground">{row[1]}</TableCell><TableCell className="text-right font-mono">{row[2] || 0}</TableCell></TableRow>)}</TableBody></Table>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="charts" className="space-y-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Business Activity Over Time</CardTitle><CardDescription>Orders, quotes, users, and collected events in the selected period.</CardDescription></CardHeader>
              <CardContent className="h-80">
                <ResponsiveContainer width="100%" height="100%"><AreaChart data={chartRows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" /><YAxis allowDecimals={false} /><Tooltip /><Legend /><Area type="monotone" dataKey="orders" stroke="#047857" fill="#047857" fillOpacity={0.16} /><Area type="monotone" dataKey="quotes" stroke="#7c3aed" fill="#7c3aed" fillOpacity={0.12} /><Area type="monotone" dataKey="users" stroke="#2563eb" fill="#2563eb" fillOpacity={0.12} /><Area type="monotone" dataKey="events" stroke="#d97706" fill="#d97706" fillOpacity={0.1} /></AreaChart></ResponsiveContainer>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">Activity Table</CardTitle></CardHeader>
              <CardContent><Table><TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Users</TableHead><TableHead>Quotes</TableHead><TableHead>Orders</TableHead><TableHead>Events</TableHead></TableRow></TableHeader><TableBody>{chartRows.map((b) => <TableRow key={b.date}><TableCell>{b.date}</TableCell><TableCell>{b.users}</TableCell><TableCell>{b.quotes}</TableCell><TableCell>{b.orders}</TableCell><TableCell>{b.events}</TableCell></TableRow>)}</TableBody></Table></CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="users">
            <MiniRows title="Logged-in User Activity" rows={data?.users || []} columns={[{ key: "full_name", label: "Name" }, { key: "email", label: "Email" }, { key: "company_name", label: "Tenant" }, { key: "role", label: "Role" }, { key: "orders", label: "Orders" }, { key: "quotes", label: "Quotes" }, { key: "page_views", label: "Views" }, { key: "last_login_at", label: "Last Login", render: (row) => dt(row.last_login_at) }]} />
          </TabsContent>
          <TabsContent value="routes">
            <MiniRows title="Top Pages & Routes" rows={data?.routes || []} columns={[{ key: "route", label: "Route" }, { key: "requests", label: "Requests" }, { key: "unique_users", label: "Users" }, { key: "unique_visitors", label: "Visitors" }, { key: "last_accessed", label: "Last Accessed", render: (row) => dt(row.last_accessed) }]} />
          </TabsContent>
          <TabsContent value="sessions">
            <MiniRows title="Visitor Sessions" rows={data?.sessions_detail || []} columns={[{ key: "session_id", label: "Session", render: (row) => row.session_id?.slice(0, 12) || "-" }, { key: "ip_address", label: "IP" }, { key: "referrer", label: "Referrer", render: (row) => row.referrer || "Direct" }, { key: "requests", label: "Requests" }, { key: "route_count", label: "Routes" }, { key: "is_logged_in", label: "Logged In", render: (row) => row.is_logged_in ? "Yes" : "No" }, { key: "is_bot", label: "Bot", render: (row) => row.is_bot ? "Yes" : "No" }, { key: "last_seen", label: "Last Seen", render: (row) => dt(row.last_seen) }]} />
          </TabsContent>
          <TabsContent value="referrers" className="space-y-4">
            <MiniRows title="Traffic Sources" rows={data?.referrer_sources || []} columns={[{ key: "source", label: "Source" }, { key: "requests", label: "Requests" }, { key: "unique_visitors", label: "Visitors" }, { key: "pct", label: "Traffic %" }]} />
            <MiniRows title="Raw Referrers" rows={data?.referrers || []} columns={[{ key: "referrer", label: "Referrer" }, { key: "events", label: "Events" }, { key: "visitors", label: "Visitors" }]} />
          </TabsContent>
          <TabsContent value="errors" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4"><StatCard title="Total Errors" value={errors.total_errors} icon={AlertTriangle} /><StatCard title="Frontend Errors" value={errors.frontend_errors} icon={AlertTriangle} /><StatCard title="API Errors" value={errors.api_errors} icon={AlertTriangle} /></div>
            <MiniRows title="Error Log" rows={errors.errors || []} columns={[{ key: "event_type", label: "Type" }, { key: "route", label: "Route" }, { key: "message", label: "Message" }, { key: "count", label: "Count" }, { key: "affected_users", label: "Users" }, { key: "last_occurred", label: "Last Occurred", render: (row) => dt(row.last_occurred) }]} />
          </TabsContent>
          <TabsContent value="suspicious" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4"><StatCard title="Bot Events" value={suspicious.total_bot} icon={Bot} /><StatCard title="Suspicious Events" value={suspicious.total_suspicious} icon={Ban} /><StatCard title="Bot Traffic %" value={`${suspicious.bot_pct || 0}%`} icon={Activity} /></div>
            <MiniRows title="Bot & Suspicious Traffic" rows={suspicious.suspicious || []} columns={[{ key: "ip_address", label: "IP" }, { key: "label", label: "Label" }, { key: "user_agent", label: "User Agent" }, { key: "requests", label: "Requests" }, { key: "session_count", label: "Sessions" }, { key: "first_seen", label: "First Seen", render: (row) => dt(row.first_seen) }, { key: "last_seen", label: "Last Seen", render: (row) => dt(row.last_seen) }]} />
          </TabsContent>
          <TabsContent value="commercial" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4"><StatCard title="Subscriptions" value={o.subscriptions} icon={ShieldCheck} /><StatCard title="Active" value={o.active_subscriptions} icon={ShieldCheck} /><StatCard title="Trialing" value={o.trialing_subscriptions} icon={TrendingUp} /><StatCard title="Dunning" value={o.dunning_subscriptions} icon={Ban} /></div>
            <MiniRows title="Trial Funnel" rows={data?.trial_funnel || []} columns={[{ key: "status", label: "Status" }, { key: "count", label: "Count" }]} />
          </TabsContent>
          <TabsContent value="ai" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4"><StatCard title="AI Usage" value={o.ai_usage_events} icon={BarChart3} /><StatCard title="Cost Rows" value={o.ai_cost_rows} icon={BarChart3} /><StatCard title="Credit Rows" value={o.ai_credit_rows} icon={BarChart3} /><StatCard title="Actual Cost Cents" value={data?.ai_cost?.actual_cost_cents || 0} icon={BarChart3} /></div>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <MiniRows title="AI Feature Usage" rows={data?.ai_feature_usage || []} columns={[{ key: "feature_key", label: "Feature" }, { key: "uses", label: "Uses" }, { key: "credits", label: "Credits" }, { key: "input_units", label: "Input" }, { key: "output_units", label: "Output" }]} />
              <MiniRows title="AI Credit Activity" rows={data?.ai_credit_activity || []} columns={[{ key: "entry_type", label: "Type" }, { key: "credits", label: "Credits" }, { key: "count", label: "Rows" }]} />
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </PlatformGate>
  );
}
