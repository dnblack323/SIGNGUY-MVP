import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import portalApi, { portalExtractError } from "./portalApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";

// Never render Stripe client_secret or publishable key verbatim as visible text.
// The publishable key is used by Stripe.js at runtime only.
// This page uses AUTH_DEV_BYPASS dev-simulate confirmation to avoid live Stripe
// test key requirement in the preview environment. Real Stripe.js Payment
// Element wiring is a drop-in when a live publishable key is present.

function money(cents) { return `$${((cents || 0) / 100).toFixed(2)}`; }

export default function PortalInvoicePayPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [invoice, setInvoice] = useState(null);
  const [err, setErr] = useState(null);
  const [amount, setAmount] = useState("");
  const [paymentId, setPaymentId] = useState(null);
  const [phase, setPhase] = useState("idle"); // idle | initiating | pending | confirmed | failed
  // Keep the client_secret + publishable_key in memory (state) but NEVER
  // interpolate them into the DOM.
  const [_stripe, _setStripe] = useState({ client_secret: null, publishable_key: null });

  const load = useCallback(async () => {
    try {
      const r = await portalApi.get(`/portal/invoices/${id}`);
      setInvoice(r.data);
    } catch (e) { setErr(portalExtractError(e)); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const balance = useMemo(() => Number(invoice?.invoice?.balance_due_cents || 0), [invoice]);
  const canPay = balance > 0 && invoice?.invoice?.document_status !== "void";

  async function initiate() {
    const cents = Math.round(parseFloat(amount || "0") * 100);
    if (!cents || cents <= 0) { toast.error("Enter an amount"); return; }
    if (cents > balance) { toast.error("Amount exceeds balance"); return; }
    setPhase("initiating");
    try {
      const r = await portalApi.post(`/portal/invoices/${id}/stripe-intents`, { amount_cents: cents });
      setPaymentId(r.data.payment_id);
      _setStripe({ client_secret: r.data.client_secret, publishable_key: r.data.publishable_key });
      setPhase("pending");
      toast.info("Payment initiated. Complete card details to confirm.");
    } catch (e) { setPhase("failed"); toast.error(portalExtractError(e)); }
  }

  async function devConfirm() {
    if (!paymentId) return;
    try {
      await portalApi.post(`/portal/payments/${paymentId}/dev-simulate-confirm`);
      setPhase("confirmed");
      toast.success("Payment confirmed");
      await load();
    } catch (e) { toast.error(portalExtractError(e)); }
  }

  if (err) return <div className="p-4 text-rose-700" data-testid="portal-pay-error">{err}</div>;
  if (!invoice) return <div className="p-4 text-slate-500" data-testid="portal-pay-loading">Loading…</div>;

  const inv = invoice.invoice;
  return (
    <div className="max-w-2xl space-y-4" data-testid="portal-pay-page">
      <Card>
        <CardHeader><CardTitle data-testid="portal-pay-title">Invoice I-{inv.number}</CardTitle></CardHeader>
        <CardContent className="grid gap-2 text-sm">
          <Row label="Document status">{inv.document_status}</Row>
          <Row label="Financial status" testId="portal-pay-financial-status">{inv.financial_status}</Row>
          <Row label="Invoice total" testId="portal-pay-total">{money(inv.total_cents)}</Row>
          <Row label="Amount paid" testId="portal-pay-paid">{money(inv.amount_paid_cents)}</Row>
          <Row label="Balance due" testId="portal-pay-balance">{money(inv.balance_due_cents)}</Row>
        </CardContent>
      </Card>

      {inv.document_status === "void" && (
        <Card data-testid="portal-pay-void-note"><CardContent className="text-sm text-rose-700 p-4">This invoice is void and cannot accept payment.</CardContent></Card>
      )}
      {inv.financial_status === "paid" && (
        <Card data-testid="portal-pay-paid-note"><CardContent className="text-sm text-emerald-700 p-4">This invoice is fully paid.</CardContent></Card>
      )}

      {canPay && phase !== "confirmed" && (
        <Card>
          <CardHeader><CardTitle>Pay this invoice</CardTitle></CardHeader>
          <CardContent className="grid gap-3">
            <div className="flex items-end gap-2">
              <div className="grid gap-1.5 flex-1">
                <Label>Amount to pay (up to balance {money(balance)})</Label>
                <Input type="number" step="0.01" min="0.01" max={(balance / 100).toFixed(2)}
                  value={amount} onChange={(e) => setAmount(e.target.value)} data-testid="portal-pay-amount"
                  disabled={phase === "pending" || phase === "initiating"} />
              </div>
              <Button variant="outline" size="sm" onClick={() => setAmount((balance / 100).toFixed(2))}
                disabled={phase === "pending"} data-testid="portal-pay-full-balance">Full balance</Button>
            </div>
            {phase !== "pending" && (
              <Button onClick={initiate} disabled={phase === "initiating"} data-testid="portal-pay-initiate">
                {phase === "initiating" ? "Initiating…" : "Continue to secure card entry"}
              </Button>
            )}
            {phase === "pending" && (
              <div className="grid gap-2 text-sm" data-testid="portal-pay-pending">
                <div className="text-slate-600">Payment initiated. Complete card details in Stripe's secure Payment Element to confirm.</div>
                {/* In production: mount Stripe.js Payment Element using publishable_key + client_secret in memory. */}
                <div className="text-xs text-slate-500 italic">(This preview uses a signed dev-simulate confirmation that exercises the real EC4 webhook reconciliation path.)</div>
                <Button variant="secondary" onClick={devConfirm} data-testid="portal-pay-dev-confirm">Simulate secure card confirmation</Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {phase === "confirmed" && (
        <Card data-testid="portal-pay-confirmed">
          <CardHeader><CardTitle>Thank you — payment confirmed</CardTitle></CardHeader>
          <CardContent className="text-sm text-slate-700 grid gap-3">
            <div>Your payment has been reconciled with the invoice. Balance now: <span className="font-medium">{money(inv.balance_due_cents)}</span>.</div>
            <Button onClick={() => nav(`/portal/invoices`)} data-testid="portal-pay-back">Back to invoices</Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-sm">Payment history</CardTitle></CardHeader>
        <CardContent>
          {(invoice.payments || []).length === 0 ? <div className="text-xs text-slate-500 italic">No payments yet.</div> : (
            <ul className="divide-y text-sm" data-testid="portal-pay-history">
              {invoice.payments.map((p) => (
                <li key={p.id} className="py-2 flex items-center justify-between" data-testid={`portal-pay-history-row-${p.id}`}>
                  <span className="capitalize">{p.source}{p.source === "manual" ? " (recorded)" : ""} · {p.status}</span>
                  <span className="tabular-nums">{money(p.amount_cents)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, children, testId }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium" data-testid={testId}>{children}</span>
    </div>
  );
}
