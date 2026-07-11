import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import MoneyInput from "@/components/forms/MoneyInput";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { centsToDollarsString, formatDate } from "@/lib/format";
import { ArrowLeft, Save, Send, Mail, XCircle } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import ComposeEmailDialog from "@/components/email/ComposeEmailDialog";
import InvoicePairedStatus from "@/components/invoices/InvoicePairedStatus";
import { RecordManualPaymentDialog, VoidPaymentButton, InitiateStripePaymentButton, RefundButton } from "@/components/invoices/PaymentDialogs";

export default function InvoiceDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { hasPerm } = useAuth();

  const { data, isLoading, isError, error } = useQuery({ queryKey: ["invoice", id], queryFn: async () => (await api.get(`/invoices/${id}`)).data });
  const { data: audit } = useQuery({ queryKey: ["audit-invoice", id], queryFn: async () => (await api.get(`/audit`, { params: { entity_type: "invoice", entity_id: id } })).data, enabled: !!id });
  const { data: customer } = useQuery({ queryKey: ["customer", data?.invoice?.customer_id], queryFn: async () => (await api.get(`/customers/${data.invoice.customer_id}`)).data, enabled: !!data?.invoice?.customer_id });
  const { data: history } = useQuery({
    queryKey: ["invoice-payments", id],
    queryFn: async () => (await api.get(`/invoices/${id}/payment-history`)).data,
    enabled: !!id,
  });

  const inv = data?.invoice;
  const payments = history?.items || [];
  const totals = history?.invoice_totals || {};

  const [form, setForm] = useState({});
  const [voidOpen, setVoidOpen] = useState(false);
  const [voidReason, setVoidReason] = useState("");
  const edit = { ...inv, ...form };

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["invoice", id] });
    qc.invalidateQueries({ queryKey: ["invoice-payments", id] });
    qc.invalidateQueries({ queryKey: ["audit-invoice", id] });
  };

  const patch = useMutation({
    mutationFn: async (payload) => (await api.patch(`/invoices/${id}`, payload)).data,
    onSuccess: () => { toast.success("Saved"); invalidate(); setForm({}); },
    onError: (e) => toast.error(extractError(e)),
  });
  const setDocStatus = useMutation({
    mutationFn: async ({ document_status, reason }) => (await api.post(`/invoices/${id}/status`, { document_status, reason: reason || null })).data,
    onSuccess: () => { invalidate(); setVoidOpen(false); },
    onError: (e) => toast.error(extractError(e)),
  });

  if (isLoading) return <div className="text-sm text-muted-foreground" data-testid="invoice-loading">Loading invoice…</div>;
  if (isError) return <div className="text-sm text-destructive" data-testid="invoice-error">{extractError(error)}</div>;
  if (!inv) return <div className="text-sm text-muted-foreground">Invoice not found.</div>;

  const docStatus = inv.document_status || (inv.status === "void" ? "void" : inv.status === "draft" ? "draft" : "issued");
  const balanceDue = Number(totals.balance_due_cents ?? inv.balance_due_cents ?? 0);
  const canWrite = hasPerm("invoice:write") && docStatus === "draft";
  const canPay = hasPerm("payment:write") && docStatus !== "void" && balanceDue > 0;
  const canVoid = hasPerm("invoice:void") && docStatus !== "void";
  const canIssue = hasPerm("invoice:write") && docStatus === "draft";

  return (
    <div className="space-y-4" data-testid="invoice-detail-page">
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="icon"><Link to="/invoices"><ArrowLeft className="size-4" /></Link></Button>
        <PageHeader
          title={<span><span className="mono text-muted-foreground text-lg mr-2">I-{inv.number}</span>{inv.title}</span>}
          subtitle={<span className="inline-flex items-center gap-2 flex-wrap">
            Order: <Link className="link-underline" to={`/orders/${inv.order_id}`}>Open order</Link>
            {customer && <> · Customer: <Link className="link-underline" to={`/customers/${customer.id}`}>{customer.name}</Link></>}
            <InvoicePairedStatus documentStatus={docStatus} financialStatus={totals.financial_status || inv.financial_status} />
          </span>}
          actions={(
            <div className="flex items-center gap-2 flex-wrap">
              {canIssue && (
                <Button variant="outline" size="sm" onClick={() => setDocStatus.mutate({ document_status: "issued" })} data-testid="invoice-issue-button">
                  <Send className="size-4 mr-1" />Issue
                </Button>
              )}
              {hasPerm("email:send") && customer?.email && (
                <ComposeEmailDialog
                  defaultTemplate="invoice_sent"
                  toEmail={customer.email}
                  customerId={customer.id}
                  relatedType="invoice"
                  relatedId={inv.id}
                  suggestedSubject={`Invoice I-${inv.number} — ${inv.title}`}
                  suggestedBody={`Hi ${customer.name},\n\nAttached is invoice I-${inv.number}.\nTotal: ${centsToDollarsString(inv.total_cents)}\nBalance due: ${centsToDollarsString(balanceDue)}\nDue date: ${inv.due_date || "—"}`}
                  trigger={<Button variant="outline" size="sm" data-testid="invoice-email-button"><Mail className="size-4 mr-1" />Email invoice</Button>}
                />
              )}
              {canVoid && (
                <Button variant="ghost" size="sm" onClick={() => setVoidOpen(true)} data-testid="invoice-void-button">
                  <XCircle className="size-4 mr-1" />Void
                </Button>
              )}
            </div>
          )}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        <Tabs defaultValue="payments" data-testid="detail-tabs">
          <TabsList>
            <TabsTrigger value="payments" data-testid="detail-tab-payments">Payments ({payments.length})</TabsTrigger>
            <TabsTrigger value="details" data-testid="detail-tab-details">Details</TabsTrigger>
            <TabsTrigger value="activity" data-testid="detail-tab-activity">Activity</TabsTrigger>
          </TabsList>

          <TabsContent value="payments">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle>Payment history</CardTitle>
                {canPay && (
                  <div className="flex items-center gap-2">
                    <RecordManualPaymentDialog invoiceId={id} balanceDueCents={balanceDue} onDone={invalidate} />
                    <InitiateStripePaymentButton invoiceId={id} balanceDueCents={balanceDue} onDone={invalidate} />
                  </div>
                )}
              </CardHeader>
              <CardContent>
                {payments.length === 0 ? (
                  <div className="text-sm text-muted-foreground" data-testid="payments-empty">No payments yet.</div>
                ) : (
                  <div className="divide-y">
                    {payments.map((p) => (
                      <div key={p.id} className="grid grid-cols-[110px_1fr_120px_120px_1fr_auto] gap-2 py-2 text-sm items-center" data-testid={`payment-row-${p.id}`}>
                        <div className="text-xs">
                          <div className="uppercase text-muted-foreground">{p.source}</div>
                          <div className="capitalize font-medium">{p.status}</div>
                        </div>
                        <div className="text-muted-foreground text-xs">
                          {p.method ? <span className="capitalize">{p.method.replace(/_/g, " ")}</span> : (p.refund_of_payment_id ? "Refund" : p.source)}
                          {p.void_reason && <span className="ml-1 text-destructive">· voided: {p.void_reason}</span>}
                          {p.refund_reason && <span className="ml-1 text-amber-600">· refund: {p.refund_reason}</span>}
                        </div>
                        <div>{p.paid_on ? formatDate(p.paid_on) : (p.confirmed_at ? formatDate(p.confirmed_at) : "—")}</div>
                        <div className="text-right tabular-nums font-medium">{p.refund_of_payment_id ? "−" : ""}{centsToDollarsString(p.amount_cents)}</div>
                        <div className="text-muted-foreground truncate">{p.reference || p.notes || p.stripe_payment_intent_id || "—"}</div>
                        <div className="flex items-center gap-1 justify-end">
                          <VoidPaymentButton payment={p} onDone={invalidate} />
                          <RefundButton payment={p} onDone={invalidate} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="details">
            <Card>
              <CardHeader><CardTitle>Invoice</CardTitle></CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                <div className="grid gap-1.5"><Label>Title</Label><Input value={edit.title || ""} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} data-testid="invoice-title-input" /></div>
                <div className="grid gap-1.5"><Label>Total</Label><MoneyInput value={edit.total_cents} disabled={!canWrite} onChange={(v) => setForm((f) => ({ ...f, total_cents: v }))} testId="invoice-total-input" /></div>
                <div className="grid gap-1.5"><Label>Due date</Label><Input type="date" value={(edit.due_date || "").slice(0, 10)} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} data-testid="invoice-due-date" /></div>
                <div className="md:col-span-2 grid gap-1.5"><Label>Description</Label><Textarea rows={3} value={edit.description || ""} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} /></div>
                <div className="md:col-span-2 grid gap-1.5"><Label>Notes</Label><Textarea rows={2} value={edit.notes || ""} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></div>
                {canWrite && Object.keys(form).length > 0 && (
                  <div className="md:col-span-2">
                    <Button onClick={() => patch.mutate(form)} data-testid="invoice-save-button">
                      <Save className="size-4 mr-1" />Save
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="activity"><AuditTimeline events={audit?.items || []} /></TabsContent>
        </Tabs>

        <aside className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Status</CardTitle></CardHeader>
            <CardContent>
              <InvoicePairedStatus documentStatus={docStatus} financialStatus={totals.financial_status || inv.financial_status || "unpaid"} />
              {inv.void_reason && (
                <div className="text-xs text-muted-foreground mt-2">Voided: <span className="italic">{inv.void_reason}</span></div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Totals</CardTitle></CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Invoice total</span><span className="tabular-nums font-medium">{centsToDollarsString(totals.total_cents ?? inv.total_cents)}</span></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Paid</span><span className="tabular-nums" data-testid="invoice-paid">{centsToDollarsString(totals.amount_paid_cents ?? 0)}</span></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Refunded</span><span className="tabular-nums">{centsToDollarsString(totals.amount_refunded_cents ?? 0)}</span></div>
              <div className="flex items-center justify-between font-semibold border-t pt-1"><span>Balance due</span><span className="tabular-nums" data-testid="invoice-balance-due">{centsToDollarsString(balanceDue)}</span></div>
            </CardContent>
          </Card>
        </aside>
      </div>

      <AlertDialog open={voidOpen} onOpenChange={setVoidOpen}>
        <AlertDialogContent data-testid="void-invoice-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Void invoice I-{inv.number}?</AlertDialogTitle>
            <AlertDialogDescription>
              Void is blocked while confirmed payments remain. Refund or manually void payments first.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="grid gap-1.5">
            <Label>Reason*</Label>
            <Input value={voidReason} onChange={(e) => setVoidReason(e.target.value)} placeholder="e.g. customer cancelled" data-testid="void-invoice-reason" />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => setDocStatus.mutate({ document_status: "void", reason: voidReason })}
              disabled={!voidReason.trim()}
              data-testid="void-invoice-confirm"
            >
              Void invoice
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
