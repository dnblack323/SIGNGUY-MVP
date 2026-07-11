import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import MoneyInput from "@/components/forms/MoneyInput";
import { toast } from "sonner";
import { centsToDollarsString } from "@/lib/format";
import { CreditCard, Plus, RotateCcw, Undo2 } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import InvoicePairedStatus from "@/components/invoices/InvoicePairedStatus";

// ---------------- Record Manual Payment ----------------

export function RecordManualPaymentDialog({ invoiceId, balanceDueCents, onDone }) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState(0);
  const [method, setMethod] = useState("cash");
  const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10));
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!amount || amount <= 0) { toast.error("Amount is required"); return; }
    if (amount > balanceDueCents) {
      toast.error(`Amount exceeds current balance of ${centsToDollarsString(balanceDueCents)}`);
      return;
    }
    setBusy(true);
    try {
      const ikey = `pm-${crypto.randomUUID()}`;
      const { data } = await api.post(`/invoices/${invoiceId}/manual-payments`, {
        amount_cents: amount, method, paid_on: paidOn,
        reference: reference || null, notes: notes || null,
      }, { headers: { "Idempotency-Key": ikey } });
      toast.success(data.already_exists ? "Payment already recorded" : "Payment recorded");
      onDone?.();
      setOpen(false);
      setAmount(0); setReference(""); setNotes("");
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button onClick={() => { setOpen(true); setAmount(balanceDueCents); }} data-testid="record-payment-open">
        <Plus className="size-4 mr-1" />Record payment
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="record-payment-dialog">
          <DialogHeader>
            <DialogTitle>Record manual payment</DialogTitle>
            <DialogDescription>
              Balance due <span className="font-semibold tabular-nums">{centsToDollarsString(balanceDueCents)}</span>.
              Overpayments are rejected server-side.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-1.5"><Label>Amount</Label><MoneyInput value={amount} onChange={setAmount} testId="payment-amount" /></div>
            <div className="grid gap-1.5">
              <Label>Method</Label>
              <Select value={method} onValueChange={setMethod}>
                <SelectTrigger data-testid="payment-method"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["cash", "check", "card_external", "bank_transfer_external", "other"].map((m) => (
                    <SelectItem key={m} value={m}><span className="capitalize">{m.replace(/_/g, " ")}</span></SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5"><Label>Paid on</Label><Input type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} data-testid="payment-paid-on" /></div>
            <div className="grid gap-1.5"><Label>Reference</Label><Input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="Check #, txn id…" data-testid="payment-reference" /></div>
            <div className="grid gap-1.5"><Label>Notes</Label><Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="payment-notes" /></div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)} type="button">Cancel</Button>
            <Button onClick={submit} disabled={busy || !amount} data-testid="payment-submit">
              {busy ? "Saving…" : "Record"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ---------------- Void Manual Payment ----------------

export function VoidPaymentButton({ payment, onDone }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const { hasPerm } = useAuth();

  if (!hasPerm("payment:void")) return null;
  const eligible = payment.source === "manual" && payment.status === "confirmed";
  if (!eligible) return null;

  async function submit() {
    if (!reason.trim()) { toast.error("Reason required"); return; }
    setBusy(true);
    try {
      await api.post(`/payments/${payment.id}/void`, { reason: reason.trim() });
      toast.success("Payment voided");
      onDone?.(); setOpen(false); setReason("");
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)} data-testid={`payment-void-${payment.id}`}>
        <Undo2 className="size-3.5 mr-1" />Void
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="void-payment-dialog">
          <DialogHeader>
            <DialogTitle>Void payment</DialogTitle>
            <DialogDescription>
              This preserves the original record and excludes it from the invoice balance.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label>Reason*</Label>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. entered against wrong invoice" data-testid="void-reason" />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)} type="button">Cancel</Button>
            <Button onClick={submit} disabled={busy || !reason.trim()} data-testid="void-submit">
              {busy ? "Voiding…" : "Void payment"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ---------------- Stripe Initiate ----------------

export function InitiateStripePaymentButton({ invoiceId, balanceDueCents, onDone }) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(null);

  async function submit() {
    if (!amount || amount <= 0 || amount > balanceDueCents) {
      toast.error("Enter an amount not exceeding the balance");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post(`/invoices/${invoiceId}/stripe-intents`, { amount_cents: amount },
        { headers: { "Idempotency-Key": `pi-${crypto.randomUUID()}` } });
      setPending(data);
      toast.info("Payment intent created — Stripe will confirm via webhook");
      onDone?.();
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="outline" onClick={() => { setOpen(true); setAmount(balanceDueCents); }} data-testid="stripe-initiate-open">
        <CreditCard className="size-4 mr-1" />Stripe payment
      </Button>
      <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) setPending(null); }}>
        <DialogContent data-testid="stripe-initiate-dialog">
          <DialogHeader>
            <DialogTitle>Take payment via Stripe</DialogTitle>
            <DialogDescription>
              Balance due <span className="font-semibold tabular-nums">{centsToDollarsString(balanceDueCents)}</span>.
              Payment is confirmed only after Stripe delivers a signed <code>payment_intent.succeeded</code> webhook.
            </DialogDescription>
          </DialogHeader>
          {!pending ? (
            <div className="grid gap-3">
              <div className="grid gap-1.5"><Label>Amount</Label><MoneyInput value={amount} onChange={setAmount} testId="stripe-amount" /></div>
            </div>
          ) : (
            <div className="grid gap-2" data-testid="stripe-pending">
              <div className="text-sm">Client secret returned: <code className="text-xs">{pending.client_secret?.slice(0, 20)}…</code></div>
              <div className="text-sm">Publishable key: <code className="text-xs">{pending.publishable_key || "unset (STRIPE_PUBLISHABLE_KEY)"}</code></div>
              <div className="text-sm text-muted-foreground">
                Payment status will flip to <b>paid</b> once Stripe confirms via webhook.
                Use Stripe test card <code>4242 4242 4242 4242</code> in a Payment Element wired to this client_secret.
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)} type="button">Close</Button>
            {!pending && (
              <Button onClick={submit} disabled={busy || !amount} data-testid="stripe-submit">
                {busy ? "Creating…" : "Create payment intent"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ---------------- Refund ----------------

export function RefundButton({ payment, onDone }) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState(payment.amount_cents);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const { hasPerm } = useAuth();

  if (!hasPerm("payment:refund")) return null;
  if (payment.source !== "stripe" || payment.status !== "confirmed") return null;
  if (payment.refund_of_payment_id) return null;   // never refund a refund row

  async function submit() {
    if (!reason.trim()) { toast.error("Reason required"); return; }
    if (amount <= 0 || amount > payment.amount_cents) { toast.error("Invalid amount"); return; }
    setBusy(true);
    try {
      await api.post(`/payments/${payment.id}/refund`, {
        amount_cents: amount, reason: reason.trim(),
      });
      toast.success("Refund initiated");
      onDone?.(); setOpen(false);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)} data-testid={`refund-open-${payment.id}`}>
        <RotateCcw className="size-3.5 mr-1" />Refund
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="refund-dialog">
          <DialogHeader>
            <DialogTitle>Refund Stripe payment</DialogTitle>
            <DialogDescription>Stripe will confirm via <code>charge.refunded</code> webhook.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-1.5"><Label>Amount (max {centsToDollarsString(payment.amount_cents)})</Label><MoneyInput value={amount} onChange={setAmount} testId="refund-amount" /></div>
            <div className="grid gap-1.5"><Label>Reason*</Label><Input value={reason} onChange={(e) => setReason(e.target.value)} data-testid="refund-reason" /></div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)} type="button">Cancel</Button>
            <Button onClick={submit} disabled={busy || !reason.trim() || amount <= 0} data-testid="refund-submit">
              {busy ? "Refunding…" : "Initiate refund"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
