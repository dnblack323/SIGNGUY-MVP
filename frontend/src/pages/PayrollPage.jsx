import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { centsToDollarsString, formatDate, formatMinutes, parseDollarsToCents } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";
import { AlertTriangle, Calculator, CheckCircle2, ChevronLeft, ChevronRight, DollarSign, Lock, RotateCcw, Wallet, XCircle } from "lucide-react";

function shiftDate(iso, days) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function ReasonDialog({ trigger, title, description, submitLabel, onSubmit, requireReason, reasonLabel = "Reason" }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await onSubmit(reason || undefined);
      setOpen(false);
      setReason("");
    } catch { /* toast handled by caller */ }
    finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>{reasonLabel}{requireReason ? "*" : " (optional — required only if there are unresolved warnings or an unpaid balance)"}</Label>
            <Textarea rows={2} required={requireReason} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="payroll-reason-textarea" />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy || (requireReason && !reason.trim())} data-testid="payroll-reason-submit-button">{busy ? "Working…" : submitLabel}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PeriodActions({ period, canManage, onAction }) {
  if (!canManage) return null;
  if (period.status === "open" || period.status === "review") {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        <Button size="sm" variant="outline" onClick={() => onAction("recalculate")} data-testid="payroll-recalculate-button">
          <Calculator className="size-4 mr-1" />Recalculate
        </Button>
        <ReasonDialog
          trigger={<Button size="sm" data-testid="payroll-approve-button"><CheckCircle2 className="size-4 mr-1" />Approve</Button>}
          title="Approve Pay Period" reasonLabel="Override reason" submitLabel="Approve"
          description="Locks this period's earnings. If any employee has an unresolved warning, an override reason is required."
          onSubmit={(reason) => onAction("approve", { override_reason: reason })}
        />
      </div>
    );
  }
  if (period.status === "approved" || period.status === "partially_paid") {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        <ReasonDialog
          trigger={<Button size="sm" variant="outline" data-testid="payroll-reopen-button"><RotateCcw className="size-4 mr-1" />Reopen</Button>}
          title="Reopen Pay Period" reasonLabel="Reason" submitLabel="Reopen" requireReason
          description="Unlocks earnings for recalculation. A reason is required and will be recorded in the audit trail."
          onSubmit={(reason) => onAction("reopen", { reason })}
        />
        <ReasonDialog
          trigger={<Button size="sm" data-testid="payroll-close-button"><Lock className="size-4 mr-1" />Close</Button>}
          title="Close Pay Period" reasonLabel="Override reason" submitLabel="Close"
          description="Closes this period. Any unpaid balance will be carried over to the next Pay Period. If there's an unpaid balance or unresolved warnings, an override reason is required."
          onSubmit={(reason) => onAction("close", { override_reason: reason })}
        />
        <ReasonDialog
          trigger={<Button size="sm" variant="destructive" data-testid="payroll-void-button"><XCircle className="size-4 mr-1" />Void</Button>}
          title="Void Pay Period" reasonLabel="Reason" submitLabel="Void" requireReason
          description="Reverses every transaction in this period with an offsetting ledger entry. This cannot be undone."
          onSubmit={(reason) => onAction("void", { reason })}
        />
      </div>
    );
  }
  if (period.status === "paid") {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        <ReasonDialog
          trigger={<Button size="sm" data-testid="payroll-close-button"><Lock className="size-4 mr-1" />Close</Button>}
          title="Close Pay Period" reasonLabel="Override reason" submitLabel="Close"
          onSubmit={(reason) => onAction("close", { override_reason: reason })}
        />
      </div>
    );
  }
  return null;
}

function SnapshotRow({ snap, onOpenLedger }) {
  return (
    <tr className="border-b last:border-0" data-testid={`payroll-snapshot-row-${snap.employee_id}`}>
      <td className="py-2 pr-3 font-medium">{snap.employee_name}</td>
      <td className="py-2 pr-3 tabular-nums">{formatMinutes(snap.regular_minutes)}</td>
      <td className="py-2 pr-3 tabular-nums">{formatMinutes(snap.overtime_minutes)}</td>
      <td className="py-2 pr-3 tabular-nums">{centsToDollarsString(snap.gross_regular_cents + snap.gross_overtime_cents)}</td>
      <td className="py-2 pr-3 tabular-nums">{centsToDollarsString(snap.total_paid_cents)}</td>
      <td className="py-2 pr-3 tabular-nums font-medium">{centsToDollarsString(snap.remaining_balance_cents)}</td>
      <td className="py-2 pr-3">
        {snap.warnings?.length > 0 && (
          <span className="inline-flex items-center gap-1 text-amber-700 text-xs" data-testid={`payroll-warning-${snap.employee_id}`} title={snap.warnings.join("; ")}>
            <AlertTriangle className="size-3.5" />{snap.warnings.length}
          </span>
        )}
      </td>
      <td className="py-2">
        <Button size="sm" variant="ghost" onClick={() => onOpenLedger(snap.employee_id)} data-testid={`payroll-view-ledger-${snap.employee_id}`}>
          <Wallet className="size-4 mr-1" />Ledger
        </Button>
      </td>
    </tr>
  );
}

function PayPeriodsTab({ canManage, onOpenLedger }) {
  const qc = useQueryClient();
  const [anchor, setAnchor] = useState(() => new Date().toISOString().slice(0, 10));

  const { data: detail, isLoading } = useQuery({
    queryKey: ["payroll-period-current", anchor],
    queryFn: async () => (await api.get("/payroll/periods/current", { params: { period_start: anchor } })).data,
    enabled: canManage,
  });
  const { data: history } = useQuery({
    queryKey: ["payroll-periods-history"],
    queryFn: async () => (await api.get("/payroll/periods")).data,
    enabled: canManage,
  });

  const act = useMutation({
    mutationFn: async ({ action, body }) => (await api.post(`/payroll/periods/${detail.period.id}/${action}`, body || {})).data,
    onSuccess: () => {
      toast.success("Pay Period updated");
      qc.invalidateQueries({ queryKey: ["payroll-period-current"] });
      qc.invalidateQueries({ queryKey: ["payroll-periods-history"] });
    },
    onError: (e) => { toast.error(extractError(e)); throw e; },
  });

  if (!canManage) return <EmptyState icon={Lock} title="No access" description="You don't have permission to view Payroll." />;
  if (isLoading || !detail) return <div className="text-sm text-muted-foreground">Loading…</div>;
  const { period, snapshots, summary } = detail;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Button size="icon" variant="ghost" onClick={() => setAnchor((a) => shiftDate(a, -7))} data-testid="payroll-prev-period-button"><ChevronLeft className="size-4" /></Button>
            <div>
              <CardTitle className="text-base">{formatDate(period.start_date)} – {formatDate(period.end_date)}</CardTitle>
              <div className="text-xs text-muted-foreground">Payday {formatDate(period.payday)}</div>
            </div>
            <Button size="icon" variant="ghost" onClick={() => setAnchor((a) => shiftDate(a, 7))} data-testid="payroll-next-period-button"><ChevronRight className="size-4" /></Button>
          </div>
          <div className="flex items-center gap-3">
            <StatusPill kind="payroll" value={period.status} />
            <PeriodActions period={period} canManage={canManage} onAction={(action, body) => act.mutate({ action, body })} />
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 text-sm">
            <div><div className="text-muted-foreground text-xs">Employees</div><div className="font-semibold" data-testid="payroll-summary-employee-count">{summary.employee_count}</div></div>
            <div><div className="text-muted-foreground text-xs">Total gross</div><div className="font-semibold">{centsToDollarsString(summary.total_gross_cents)}</div></div>
            <div><div className="text-muted-foreground text-xs">Total paid</div><div className="font-semibold">{centsToDollarsString(summary.total_paid_cents)}</div></div>
            <div><div className="text-muted-foreground text-xs">Balance remaining</div><div className="font-semibold" data-testid="payroll-summary-remaining">{centsToDollarsString(summary.total_remaining_cents)}</div></div>
          </div>
          {snapshots.length === 0 ? (
            <EmptyState icon={Calculator} title="Nothing calculated yet" description="Click Recalculate to pull this week's approved hours into Payroll." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="payroll-snapshot-table">
                <thead className="text-left text-xs text-muted-foreground border-b">
                  <tr>
                    <th className="py-2 pr-3">Employee</th><th className="py-2 pr-3">Regular</th><th className="py-2 pr-3">Overtime</th>
                    <th className="py-2 pr-3">Gross</th><th className="py-2 pr-3">Paid</th><th className="py-2 pr-3">Balance</th>
                    <th className="py-2 pr-3">Warnings</th><th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {snapshots.map((s) => <SnapshotRow key={s.employee_id} snap={s} onOpenLedger={onOpenLedger} />)}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Pay Period history</CardTitle></CardHeader>
        <CardContent>
          {!history?.items?.length ? (
            <p className="text-sm text-muted-foreground">No prior Pay Periods yet.</p>
          ) : (
            <ul className="divide-y" data-testid="payroll-history-list">
              {history.items.map((p) => (
                <li key={p.id} className="py-2 flex items-center justify-between text-sm">
                  <button className="text-left hover:underline" onClick={() => setAnchor(p.start_date)} data-testid={`payroll-history-item-${p.id}`}>
                    {formatDate(p.start_date)} – {formatDate(p.end_date)}
                  </button>
                  <div className="flex items-center gap-3">
                    <span className="text-muted-foreground text-xs">{centsToDollarsString(p.summary.total_gross_cents)}</span>
                    <StatusPill kind="payroll" value={p.status} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const MANUAL_TYPES = [
  { value: "advance", label: "Advance" },
  { value: "payment", label: "Payment" },
  { value: "adjustment", label: "Adjustment" },
  { value: "advance_repayment", label: "Advance repayment" },
];

function AddTransactionForm({ employeeId, periodId, onAdded }) {
  const [type, setType] = useState("payment");
  const [amount, setAmount] = useState("");
  const [effectiveDate, setEffectiveDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/payroll/transactions", {
        employee_id: employeeId, pay_period_id: periodId, type, amount_cents: parseDollarsToCents(amount),
        effective_date: effectiveDate, reference: reference || undefined,
      });
      toast.success("Transaction recorded");
      setAmount(""); setReference("");
      onAdded();
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <form onSubmit={submit} className="grid gap-2 sm:grid-cols-4 items-end border rounded-lg p-3 bg-muted/30">
      <div className="grid gap-1"><Label className="text-xs">Type</Label>
        <Select value={type} onValueChange={setType}>
          <SelectTrigger data-testid="payroll-txn-type-select"><SelectValue /></SelectTrigger>
          <SelectContent>{MANUAL_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div className="grid gap-1"><Label className="text-xs">Amount ($)</Label><Input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" data-testid="payroll-txn-amount-input" /></div>
      <div className="grid gap-1"><Label className="text-xs">Effective date</Label><Input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} data-testid="payroll-txn-date-input" /></div>
      <div className="grid gap-1"><Label className="text-xs">Reference (safe, no bank info)</Label><Input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="e.g. Check #1042" data-testid="payroll-txn-reference-input" /></div>
      <div className="sm:col-span-4"><Button type="submit" size="sm" disabled={busy || !amount} data-testid="payroll-txn-submit-button">{busy ? "Recording…" : "Record transaction"}</Button></div>
    </form>
  );
}

function EmployeeLedgerTab({ initialEmployeeId }) {
  const { data: employees } = useQuery({ queryKey: ["employees-for-payroll"], queryFn: async () => (await api.get("/employees")).data });
  const { data: periods } = useQuery({ queryKey: ["payroll-periods-history"], queryFn: async () => (await api.get("/payroll/periods")).data });
  const [employeeId, setEmployeeId] = useState(initialEmployeeId || "");
  const [periodId, setPeriodId] = useState("");

  useEffect(() => {
    if (initialEmployeeId) setEmployeeId(initialEmployeeId);
  }, [initialEmployeeId]);

  const { data: txns, refetch } = useQuery({
    queryKey: ["payroll-transactions", employeeId, periodId],
    queryFn: async () => (await api.get("/payroll/transactions", { params: { employee_id: employeeId, pay_period_id: periodId || undefined } })).data,
    enabled: !!employeeId,
  });

  async function voidTxn(id) {
    const reason = window.prompt("Reason for voiding this transaction?");
    if (!reason) return;
    try {
      await api.post(`/payroll/transactions/${id}/void`, { reason });
      toast.success("Transaction voided");
      refetch();
    } catch (err) { toast.error(extractError(err)); }
  }

  const employeeOptions = employees?.items || [];
  const periodOptions = periods?.items || [];

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Employee Ledger</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5"><Label>Employee</Label>
            <Select value={employeeId} onValueChange={setEmployeeId}>
              <SelectTrigger data-testid="payroll-ledger-employee-select"><SelectValue placeholder="Select employee" /></SelectTrigger>
              <SelectContent>{employeeOptions.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Pay Period (optional filter)</Label>
            <Select value={periodId || "__all__"} onValueChange={(v) => setPeriodId(v === "__all__" ? "" : v)}>
              <SelectTrigger data-testid="payroll-ledger-period-select"><SelectValue placeholder="All periods" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All periods</SelectItem>
                {periodOptions.map((p) => <SelectItem key={p.id} value={p.id}>{formatDate(p.start_date)} – {formatDate(p.end_date)}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        {employeeId && periodId && <AddTransactionForm employeeId={employeeId} periodId={periodId} onAdded={refetch} />}
        {employeeId && !periodId && <p className="text-xs text-muted-foreground">Select a specific Pay Period above to record a new transaction.</p>}

        {employeeId ? (
          !txns?.items?.length ? (
            <EmptyState icon={DollarSign} title="No transactions" description="This employee has no ledger activity for the selected filter." />
          ) : (
            <table className="w-full text-sm" data-testid="payroll-ledger-table">
              <thead className="text-left text-xs text-muted-foreground border-b">
                <tr><th className="py-2 pr-3">Date</th><th className="py-2 pr-3">Type</th><th className="py-2 pr-3">Amount</th><th className="py-2 pr-3">Reference</th><th className="py-2"></th></tr>
              </thead>
              <tbody>
                {txns.items.map((t) => (
                  <tr key={t.id} className="border-b last:border-0" data-testid={`payroll-txn-row-${t.id}`}>
                    <td className="py-2 pr-3">{formatDate(t.effective_date)}</td>
                    <td className="py-2 pr-3 capitalize">{t.type.replace(/_/g, " ")}</td>
                    <td className="py-2 pr-3 tabular-nums">{centsToDollarsString(t.amount_cents)}</td>
                    <td className="py-2 pr-3 text-muted-foreground">{t.reference || "—"}</td>
                    <td className="py-2">
                      {!["earning", "overtime_earning", "void"].includes(t.type) && (
                        <Button size="sm" variant="ghost" onClick={() => voidTxn(t.id)} data-testid={`payroll-void-txn-${t.id}`}>Void</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          <EmptyState icon={Wallet} title="Choose an employee" description="Select an employee above to view their pay ledger." />
        )}
      </CardContent>
    </Card>
  );
}

function PayrollSettingsTab() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["payroll-settings"], queryFn: async () => (await api.get("/payroll/settings")).data });
  const [form, setForm] = useState(null);
  const settings = form || data;

  const save = useMutation({
    mutationFn: async (payload) => (await api.put("/payroll/settings", payload)).data,
    onSuccess: () => { toast.success("Payroll settings saved"); qc.invalidateQueries({ queryKey: ["payroll-settings"] }); setForm(null); },
    onError: (e) => toast.error(extractError(e)),
  });

  if (!settings) return <div className="text-sm text-muted-foreground">Loading…</div>;
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Overtime policy (tenant default)</CardTitle></CardHeader>
      <CardContent className="space-y-4 max-w-md">
        <div className="flex items-center justify-between">
          <Label>Overtime enabled</Label>
          <Switch checked={settings.overtime_enabled} onCheckedChange={(v) => setForm({ ...settings, overtime_enabled: v })} data-testid="payroll-settings-ot-enabled-switch" />
        </div>
        <div className="grid gap-1.5">
          <Label>Weekly threshold (hours)</Label>
          <Input type="number" value={settings.weekly_threshold_minutes / 60} onChange={(e) => setForm({ ...settings, weekly_threshold_minutes: Number(e.target.value) * 60 })} data-testid="payroll-settings-threshold-input" />
        </div>
        <div className="grid gap-1.5">
          <Label>Overtime multiplier</Label>
          <Input type="number" step="0.1" value={settings.overtime_multiplier} onChange={(e) => setForm({ ...settings, overtime_multiplier: Number(e.target.value) })} data-testid="payroll-settings-multiplier-input" />
        </div>
        <p className="text-xs text-muted-foreground">
          Work week is locked to Saturday–Friday with a Friday payday. Overtime is a configurable internal
          estimate only — this is not a certified legal payroll calculation, and does not include tax withholding.
        </p>
        {form && (
          <Button onClick={() => save.mutate(form)} disabled={save.isPending} data-testid="payroll-settings-save-button">
            {save.isPending ? "Saving…" : "Save settings"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export default function PayrollPage() {
  const { hasPerm } = useAuth();
  const canManage = hasPerm("payroll:manage");
  const [tab, setTab] = useState("periods");
  const [ledgerEmployee, setLedgerEmployee] = useState(null);

  const openLedger = useMemo(() => (employeeId) => { setLedgerEmployee(employeeId); setTab("ledger"); }, []);

  return (
    <div className="space-y-4" data-testid="payroll-page">
      <PageHeader title="Payroll" subtitle="Internal gross-pay ledger — hours, advances, payments and carryover. Not a tax or filing service." />
      <Tabs value={tab} onValueChange={setTab} data-testid="payroll-tabs">
        <TabsList>
          <TabsTrigger value="periods" data-testid="payroll-tab-periods">Pay Periods</TabsTrigger>
          <TabsTrigger value="ledger" data-testid="payroll-tab-ledger">Employee Ledger</TabsTrigger>
          <TabsTrigger value="settings" data-testid="payroll-tab-settings">Settings</TabsTrigger>
        </TabsList>
        <TabsContent value="periods"><PayPeriodsTab canManage={canManage} onOpenLedger={openLedger} /></TabsContent>
        <TabsContent value="ledger"><EmployeeLedgerTab initialEmployeeId={ledgerEmployee} /></TabsContent>
        <TabsContent value="settings"><PayrollSettingsTab /></TabsContent>
      </Tabs>
    </div>
  );
}
