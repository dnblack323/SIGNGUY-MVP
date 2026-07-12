import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import StatusPill from "@/components/common/StatusPill";
import EmptyState from "@/components/common/EmptyState";
import { centsToDollarsString, formatDate, formatMinutes, relativeTime } from "@/lib/format";
import { ArrowLeft, Save, UserCog, KeyRound, Ban, Send, Wallet } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";

const STATUSES = ["active", "suspended", "inactive", "terminated", "archived"];

function PayrollHistoryTab({ employeeId }) {
  const { hasPerm } = useAuth();
  const canView = hasPerm("payroll:read");
  const { data } = useQuery({
    queryKey: ["employee-payroll-snapshots", employeeId],
    queryFn: async () => (await api.get(`/payroll/employees/${employeeId}/snapshots`)).data,
    enabled: !!employeeId && canView,
  });
  if (!canView) return <EmptyState icon={Wallet} title="No access" description="You don't have permission to view Payroll." />;
  if (!data) return <div className="text-sm text-muted-foreground">Loading…</div>;
  if (!data.items.length) return <EmptyState icon={Wallet} title="No pay history yet" description="This employee hasn't been included in a Payroll recalculation yet." />;
  return (
    <Card>
      <CardHeader><CardTitle>Pay history</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="employee-payroll-history-table">
          <thead className="text-left text-xs text-muted-foreground border-b">
            <tr><th className="py-2 pr-3">Pay Period</th><th className="py-2 pr-3">Regular</th><th className="py-2 pr-3">Overtime</th><th className="py-2 pr-3">Gross</th><th className="py-2 pr-3">Paid</th><th className="py-2 pr-3">Balance</th><th className="py-2">Status</th></tr>
          </thead>
          <tbody>
            {data.items.map((s) => (
              <tr key={s.pay_period_id} className="border-b last:border-0" data-testid={`employee-payroll-row-${s.pay_period_id}`}>
                <td className="py-2 pr-3">{formatDate(s.period_start)} – {formatDate(s.period_end)}</td>
                <td className="py-2 pr-3">{formatMinutes(s.regular_minutes)}</td>
                <td className="py-2 pr-3">{formatMinutes(s.overtime_minutes)}</td>
                <td className="py-2 pr-3">{centsToDollarsString(s.gross_regular_cents + s.gross_overtime_cents)}</td>
                <td className="py-2 pr-3">{centsToDollarsString(s.total_paid_cents)}</td>
                <td className="py-2 pr-3 font-medium">{centsToDollarsString(s.remaining_balance_cents)}</td>
                <td className="py-2"><StatusPill kind="payroll" value={s.period_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function Field({ label, value, onChange, textarea, type = "text", testId }) {
  const Comp = textarea ? Textarea : Input;
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Comp value={value || ""} onChange={(e) => onChange(e.target.value)} type={type} data-testid={testId} />
    </div>
  );
}

function StatusChangeDialog({ employee, onChanged }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post(`/employees/${employee.id}/status`, { status, reason });
      toast.success("Status updated");
      setOpen(false);
      setStatus(""); setReason("");
      onChanged?.();
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" data-testid="employee-change-status-button"><UserCog className="size-4 mr-1" />Change status</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>Change employment status</DialogTitle>
          <DialogDescription>Current status: <StatusPill kind="employee" value={employee.status} /></DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>New status*</Label>
            <Select value={status} onValueChange={setStatus} required>
              <SelectTrigger data-testid="employee-status-select"><SelectValue placeholder="Select status" /></SelectTrigger>
              <SelectContent>
                {STATUSES.filter((s) => s !== employee.status).map((s) => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Reason*</Label><Textarea required rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="employee-status-reason-input" /></div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy || !status} data-testid="employee-status-submit-button">{busy ? "Saving…" : "Confirm"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function EmployeeDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canManage = hasPerm("employee:manage");

  const { data: emp, isLoading } = useQuery({
    queryKey: ["employee", id],
    queryFn: async () => (await api.get(`/employees/${id}`)).data,
  });
  const { data: audit } = useQuery({
    queryKey: ["employee-audit", id],
    queryFn: async () => (await api.get(`/audit`, { params: { entity_type: "employee", entity_id: id, limit: 50 } })).data,
    enabled: !!id,
  });
  const { data: portalStatus } = useQuery({
    queryKey: ["employee-portal-status", id],
    queryFn: async () => (await api.get(`/employee-portal/${id}`)).data,
    enabled: !!id && canManage,
  });

  const [form, setForm] = useState({});
  const editForm = { ...emp, ...form };

  const save = useMutation({
    mutationFn: async (payload) => (await api.patch(`/employees/${id}`, payload)).data,
    onSuccess: () => {
      toast.success("Employee updated");
      qc.invalidateQueries({ queryKey: ["employee", id] });
      qc.invalidateQueries({ queryKey: ["employee-audit", id] });
      setForm({});
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const invitePortal = useMutation({
    mutationFn: async () => (await api.post(`/employee-portal/${id}/invite`)).data,
    onSuccess: () => {
      toast.success("Employee Portal invitation sent");
      qc.invalidateQueries({ queryKey: ["employee-portal-status", id] });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const suspendPortal = useMutation({
    mutationFn: async () => (await api.post(`/employee-portal/${id}/suspend`)).data,
    onSuccess: () => {
      toast.success("Employee Portal access suspended");
      qc.invalidateQueries({ queryKey: ["employee-portal-status", id] });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  if (isLoading || !emp) return <div className="text-sm text-muted-foreground">Loading…</div>;

  return (
    <div className="space-y-4" data-testid="employee-detail-page">
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="icon"><Link to="/team/employees"><ArrowLeft className="size-4" /></Link></Button>
        <PageHeader
          title={emp.name}
          subtitle={<span className="flex items-center gap-2">{emp.role_label || "Employee"} <StatusPill kind="employee" value={emp.status} /></span>}
          actions={canManage && (
            <div className="flex items-center gap-2">
              {Object.keys(form).length > 0 && (
                <Button onClick={() => save.mutate(form)} disabled={save.isPending} data-testid="employee-save-button">
                  <Save className="size-4 mr-1" /> Save changes
                </Button>
              )}
              <StatusChangeDialog employee={emp} onChanged={() => qc.invalidateQueries({ queryKey: ["employee", id] })} />
            </div>
          )}
        />
      </div>

      <Tabs defaultValue="details" data-testid="detail-tabs">
        <TabsList>
          <TabsTrigger value="details" data-testid="detail-tab-details">Details</TabsTrigger>
          <TabsTrigger value="payroll" data-testid="detail-tab-payroll">Payroll</TabsTrigger>
          <TabsTrigger value="activity" data-testid="detail-tab-activity">Activity</TabsTrigger>
        </TabsList>
        <TabsContent value="details" className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Employee info</CardTitle></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <Field label="Name" value={editForm.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} testId="employee-detail-name-input" />
              <Field label="Role / title" value={editForm.role_label} onChange={(v) => setForm((f) => ({ ...f, role_label: v }))} testId="employee-detail-role-input" />
              <Field label="Email" type="email" value={editForm.email} onChange={(v) => setForm((f) => ({ ...f, email: v }))} testId="employee-detail-email-input" />
              <Field label="Phone" value={editForm.phone} onChange={(v) => setForm((f) => ({ ...f, phone: v }))} testId="employee-detail-phone-input" />
              <Field label="Hourly rate (cents)" type="number" value={editForm.hourly_rate_cents} onChange={(v) => setForm((f) => ({ ...f, hourly_rate_cents: Number(v) }))} testId="employee-detail-rate-input" />
              <Field label="Hire date" type="date" value={editForm.hire_date} onChange={(v) => setForm((f) => ({ ...f, hire_date: v }))} testId="employee-detail-hire-date-input" />
              <Field label="Emergency contact name" value={editForm.emergency_contact_name} onChange={(v) => setForm((f) => ({ ...f, emergency_contact_name: v }))} />
              <Field label="Emergency contact phone" value={editForm.emergency_contact_phone} onChange={(v) => setForm((f) => ({ ...f, emergency_contact_phone: v }))} />
              <div className="md:col-span-2"><Field label="Notes" textarea value={editForm.notes} onChange={(v) => setForm((f) => ({ ...f, notes: v }))} testId="employee-detail-notes-input" /></div>
            </CardContent>
          </Card>
          {emp.status_history?.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Status history</CardTitle></CardHeader>
              <CardContent>
                <ul className="divide-y" data-testid="employee-status-history">
                  {emp.status_history.slice().reverse().map((h, i) => (
                    <li key={i} className="py-2 text-sm flex items-center justify-between gap-2">
                      <div><span className="capitalize">{h.from}</span> → <span className="capitalize font-medium">{h.to}</span> — {h.reason}</div>
                      <span className="text-xs text-muted-foreground">{relativeTime(h.at)}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          {canManage && (
            <Card>
              <CardHeader><CardTitle>Employee Portal access</CardTitle></CardHeader>
              <CardContent className="flex items-center justify-between gap-3 text-sm">
                {!portalStatus?.invited ? (
                  <>
                    <span className="text-muted-foreground">Not yet invited to the Employee Portal.</span>
                    <Button size="sm" onClick={() => invitePortal.mutate()} disabled={invitePortal.isPending} data-testid="employee-portal-invite-button">
                      <Send className="size-4 mr-1" />Invite to Portal
                    </Button>
                  </>
                ) : (
                  <>
                    <div className="flex items-center gap-2">
                      <Badge variant={portalStatus.identity.status === "active" ? "default" : "secondary"} data-testid="employee-portal-identity-status">
                        {portalStatus.identity.status === "active" ? "Portal active" : "Portal suspended"}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {portalStatus.identity.last_login_at ? `Last login ${relativeTime(portalStatus.identity.last_login_at)}` : "Never signed in yet"}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => invitePortal.mutate()} disabled={invitePortal.isPending} data-testid="employee-portal-resend-button">
                        <KeyRound className="size-4 mr-1" />Resend invite
                      </Button>
                      {portalStatus.identity.status === "active" && (
                        <Button size="sm" variant="destructive" onClick={() => suspendPortal.mutate()} disabled={suspendPortal.isPending} data-testid="employee-portal-suspend-button">
                          <Ban className="size-4 mr-1" />Suspend
                        </Button>
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>
        <TabsContent value="payroll">
          <PayrollHistoryTab employeeId={id} />
        </TabsContent>
        <TabsContent value="activity">
          <AuditTimeline events={audit?.items || []} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
