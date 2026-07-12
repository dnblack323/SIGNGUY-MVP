import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { money, PO_STATUS_TONE } from "@/lib/ec7";
import { relativeTime } from "@/lib/format";

function SubmitDialog({ po, onDone }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  // Idempotency-Key is a per-click UUID, so accidental double-clicks don't
  // double-submit; the backend short-circuits replays.
  async function submit() {
    if (busy) return;
    setBusy(true);
    try {
      const key = crypto.randomUUID();
      await api.post(`/purchase-orders/${po.id}/submit`, { confirm: true }, { headers: { "Idempotency-Key": key } });
      toast.success("Submitted to supplier");
      setOpen(false); onDone?.();
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button size="sm" data-testid={`po-submit-${po.id}`}>Submit</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Submit PO #{po.number}?</DialogTitle>
          <DialogDescription>The supplier will be sent this order electronically. Duplicate submissions are safe — the backend short-circuits replays using an Idempotency-Key.</DialogDescription>
        </DialogHeader>
        <div className="text-sm">
          <div className="flex justify-between"><span>Subtotal</span><span>{money(po.subtotal_cents)}</span></div>
          <div className="flex justify-between"><span>Shipping</span><span>{money(po.shipping_cents)}</span></div>
          <div className="flex justify-between font-medium border-t pt-2 mt-2"><span>Total</span><span>{money(po.total_cents)}</span></div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={submit} disabled={busy} data-testid={`po-submit-confirm-${po.id}`}>{busy ? "Submitting…" : "Confirm submit"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CancelDialog({ po, onDone }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit() {
    if (!reason.trim() || busy) return;
    setBusy(true);
    try {
      await api.post(`/purchase-orders/${po.id}/cancel`, { reason });
      toast.success("PO cancelled");
      setOpen(false); setReason(""); onDone?.();
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button size="sm" variant="ghost" data-testid={`po-cancel-${po.id}`}>Cancel</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Cancel PO #{po.number}?</DialogTitle><DialogDescription>Reason is required and is stored on the audit trail.</DialogDescription></DialogHeader>
        <div className="grid gap-1.5"><Label>Reason</Label><Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} data-testid={`po-cancel-reason-${po.id}`} /></div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>Back</Button>
          <Button variant="destructive" onClick={submit} disabled={busy || !reason.trim()} data-testid={`po-cancel-confirm-${po.id}`}>Cancel PO</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function PurchaseOrdersPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["purchase-orders"],
    queryFn: async () => (await api.get("/purchase-orders", { params: { limit: 200 } })).data,
  });
  const items = data?.items || [];
  return (
    <div className="space-y-4" data-testid="purchase-orders-page">
      <PageHeader title="Purchase Orders" subtitle="Draft → Submitted → Acknowledged → Partially Received / Received / Cancelled. Backend statuses are authoritative — the frontend never invents new states." />
      <div className="rounded-xl border bg-card overflow-hidden">
        <Table data-testid="purchase-orders-table">
          <TableHeader><TableRow>
            <TableHead>#</TableHead><TableHead>Vendor</TableHead>
            <TableHead>Status</TableHead><TableHead className="text-right">Total</TableHead>
            <TableHead>Created</TableHead><TableHead>Tracking</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {isLoading ? <TableRow><TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-6">Loading…</TableCell></TableRow>
            : items.length === 0 ? <TableRow><TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-6">No purchase orders yet.</TableCell></TableRow>
            : items.map((po) => (
              <TableRow key={po.id} data-testid={`po-row-${po.id}`}>
                <TableCell className="font-medium">#{po.number}</TableCell>
                <TableCell className="text-sm">{po.vendor_snapshot?.name || po.vendor_id}</TableCell>
                <TableCell><Badge className={PO_STATUS_TONE[po.status] || ""}>{po.status}</Badge></TableCell>
                <TableCell className="text-right text-sm">{money(po.total_cents)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{relativeTime(po.created_at)}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{po.tracking_status || "—"}</TableCell>
                <TableCell className="text-right space-x-1">
                  {po.status === "draft" && <SubmitDialog po={po} onDone={() => qc.invalidateQueries({ queryKey: ["purchase-orders"] })} />}
                  {!["received", "cancelled"].includes(po.status) && <CancelDialog po={po} onDone={() => qc.invalidateQueries({ queryKey: ["purchase-orders"] })} />}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">Receiving records are keyed on an Idempotency-Key so replays never double-count. Cost changes on receiving are appended to Material Cost History without rewriting past rows.</p>
    </div>
  );
}
