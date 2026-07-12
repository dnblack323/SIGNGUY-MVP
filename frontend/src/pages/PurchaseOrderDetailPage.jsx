import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";
import { money, PO_STATUS_TONE } from "@/lib/ec7";
import { relativeTime } from "@/lib/format";

// One receiving dialog handles BOTH partial and complete receiving. The user
// enters received quantity per line; over-quantity is rejected by the backend.
// Each click generates a fresh Idempotency-Key so replays are safe.
function ReceiveDialog({ po, lines, locations, onDone }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [locationId, setLocationId] = useState(po.ship_to_location_id || locations?.[0]?.id || "");
  const [notes, setNotes] = useState("");
  // Quantity per line — defaults to remaining.
  const remainingByLine = Object.fromEntries(
    lines.map((l) => [l.id, Math.max((l.quantity_ordered || 0) - (l.quantity_received || 0), 0)])
  );
  const [qtys, setQtys] = useState({});

  function receivable(l) {
    return remainingByLine[l.id] || 0;
  }
  function currentQty(l) {
    return qtys[l.id] !== undefined ? qtys[l.id] : receivable(l);
  }
  function setAllToRemaining() {
    const next = {};
    lines.forEach((l) => { next[l.id] = receivable(l); });
    setQtys(next);
  }
  async function submit() {
    if (busy) return;
    const payloadLines = lines
      .map((l) => ({ po_line_id: l.id, quantity: Number(currentQty(l) || 0), location_id: locationId || undefined }))
      .filter((r) => r.quantity > 0);
    if (payloadLines.length === 0) { toast.error("Enter at least one non-zero quantity"); return; }
    for (const r of payloadLines) {
      if (r.quantity < 0) { toast.error("Negative quantity not allowed"); return; }
    }
    setBusy(true);
    try {
      const key = crypto.randomUUID();
      await api.post(`/purchase-orders/${po.id}/receive`, { lines: payloadLines, default_location_id: locationId || undefined, notes: notes || undefined }, { headers: { "Idempotency-Key": key } });
      toast.success("Received");
      setOpen(false); setNotes(""); setQtys({}); onDone?.();
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }
  const disabled = ["received", "cancelled", "draft"].includes(po.status);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" disabled={disabled} data-testid="po-receive-button">Receive</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[720px]">
        <DialogHeader>
          <DialogTitle>Receive against PO #{po.number}</DialogTitle>
          <DialogDescription>
            Enter received quantity per line. Backend rejects over-receiving. Every action creates immutable inventory movements + audit rows; the Idempotency-Key makes replays safe.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-3 gap-3">
          <div className="grid gap-1.5 col-span-2">
            <Label>Receiving location</Label>
            <select value={locationId} onChange={(e) => setLocationId(e.target.value)} data-testid="po-receive-location"
              className="h-9 rounded-md border bg-background px-2 text-sm">
              {(locations || []).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </div>
          <div className="grid gap-1.5"><Label>&nbsp;</Label>
            <Button size="sm" variant="outline" onClick={setAllToRemaining} data-testid="po-receive-all-remaining">Fill remaining</Button>
          </div>
        </div>
        <div className="rounded-lg border overflow-hidden max-h-[280px] overflow-y-auto">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Line</TableHead><TableHead>Ordered</TableHead><TableHead>Received</TableHead>
              <TableHead>Remaining</TableHead><TableHead className="text-right">Receive now</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {lines.map((l) => (
                <TableRow key={l.id} data-testid={`po-receive-line-${l.id}`}>
                  <TableCell className="text-sm">{l.description}</TableCell>
                  <TableCell className="text-sm">{l.quantity_ordered}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{l.quantity_received || 0}</TableCell>
                  <TableCell className="text-sm font-medium">{receivable(l)}</TableCell>
                  <TableCell className="text-right">
                    <Input type="number" min="0" step="0.01" value={currentQty(l)} onChange={(e) => setQtys((q) => ({ ...q, [l.id]: e.target.value }))} className="w-24 h-8 text-right ml-auto" data-testid={`po-receive-qty-${l.id}`} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <div className="grid gap-1.5"><Label>Packing-slip / reference / notes</Label><Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="po-receive-notes" /></div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={submit} disabled={busy} data-testid="po-receive-confirm">{busy ? "Receiving…" : "Confirm receive"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function PurchaseOrderDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const detail = useQuery({
    queryKey: ["po", id],
    queryFn: async () => (await api.get(`/purchase-orders/${id}`)).data,
  });
  const locs = useQuery({ queryKey: ["inv-locations"], queryFn: async () => (await api.get("/inventory/locations")).data });
  const supplierOrders = useQuery({
    queryKey: ["po-supplier-orders", id],
    queryFn: async () => (await api.get("/supply/supplier-orders", { params: { purchase_order_id: id } })).data,
  });
  if (detail.isLoading) return <div className="text-sm text-muted-foreground" data-testid="po-detail-loading">Loading…</div>;
  if (!detail.data) return <div className="text-sm text-muted-foreground">Not found.</div>;
  const po = detail.data.purchase_order;
  const lines = detail.data.lines || [];
  const receiving = detail.data.receiving_records || [];
  const remaining = lines.reduce((n, l) => n + Math.max((l.quantity_ordered || 0) - (l.quantity_received || 0), 0), 0);

  return (
    <div className="space-y-4" data-testid="po-detail-page">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to="/purchase-orders" className="flex items-center gap-1 hover:text-foreground" data-testid="po-back-link"><ArrowLeft className="size-3" /> Back to Purchase Orders</Link>
      </div>
      <PageHeader
        title={`PO #${po.number}`}
        subtitle={<span className="flex items-center gap-2"><Badge className={PO_STATUS_TONE[po.status] || ""} data-testid="po-detail-status">{po.status}</Badge>{po.tracking_status && <span className="text-xs">tracking: {po.tracking_status}</span>}</span>}
        actions={<ReceiveDialog po={po} lines={lines} locations={locs.data?.items || []} onDone={() => { qc.invalidateQueries({ queryKey: ["po", id] }); qc.invalidateQueries({ queryKey: ["purchase-orders"] }); }} />}
      />

      <div className="grid md:grid-cols-4 gap-3">
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Vendor</CardTitle></CardHeader><CardContent><div className="text-sm font-medium">{po.vendor_snapshot?.name || po.vendor_id}</div></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Subtotal</CardTitle></CardHeader><CardContent><div className="text-lg font-semibold">{money(po.subtotal_cents)}</div></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Shipping + handling</CardTitle></CardHeader><CardContent><div className="text-lg font-semibold">{money((po.shipping_cents || 0) + (po.handling_cents || 0))}</div></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Total</CardTitle></CardHeader><CardContent><div className="text-lg font-semibold">{money(po.total_cents)}</div><div className="text-[10px] text-muted-foreground mt-1">{remaining} unit(s) remaining to receive</div></CardContent></Card>
      </div>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Lines</CardTitle></CardHeader>
        <CardContent>
          <div className="rounded-lg border overflow-hidden"><Table data-testid="po-detail-lines">
            <TableHeader><TableRow>
              <TableHead>Description</TableHead><TableHead>SKU</TableHead>
              <TableHead className="text-right">Ordered</TableHead>
              <TableHead className="text-right">Received</TableHead>
              <TableHead className="text-right">Remaining</TableHead>
              <TableHead className="text-right">Unit</TableHead>
              <TableHead className="text-right">Extended</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {lines.length === 0 ? <TableRow><TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-6">No lines on this PO.</TableCell></TableRow>
              : lines.map((l) => (
                <TableRow key={l.id} data-testid={`po-line-${l.id}`}>
                  <TableCell className="text-sm">{l.description}</TableCell>
                  <TableCell className="font-mono text-xs">{l.supplier_sku || "—"}</TableCell>
                  <TableCell className="text-right text-sm">{l.quantity_ordered}</TableCell>
                  <TableCell className="text-right text-sm">{l.quantity_received || 0}</TableCell>
                  <TableCell className="text-right text-sm font-medium">{Math.max((l.quantity_ordered || 0) - (l.quantity_received || 0), 0)}</TableCell>
                  <TableCell className="text-right text-sm">{money(l.unit_price_cents)}</TableCell>
                  <TableCell className="text-right text-sm">{money(l.line_extended_cents)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table></div>
        </CardContent>
      </Card>

      <div className="grid md:grid-cols-2 gap-3">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Receiving history</CardTitle></CardHeader>
          <CardContent>
            <Table data-testid="po-receiving-history">
              <TableHeader><TableRow><TableHead>Received at</TableHead><TableHead>Lines</TableHead><TableHead>By</TableHead></TableRow></TableHeader>
              <TableBody>
                {receiving.length === 0 ? <TableRow><TableCell colSpan={3} className="text-center text-sm text-muted-foreground py-4">No receiving yet.</TableCell></TableRow>
                : receiving.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="text-sm">{relativeTime(r.received_at)}</TableCell>
                    <TableCell className="text-sm">{(r.lines || []).length} line(s)</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{r.received_by_user_id?.slice(0, 8)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Supplier submission history</CardTitle></CardHeader>
          <CardContent>
            <Table data-testid="po-supplier-history">
              <TableHeader><TableRow><TableHead>Submitted</TableHead><TableHead>Supplier order id</TableHead><TableHead>Status</TableHead><TableHead>Tracking</TableHead></TableRow></TableHeader>
              <TableBody>
                {(supplierOrders.data?.items || []).length === 0 ? <TableRow><TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-4">No submissions yet.</TableCell></TableRow>
                : supplierOrders.data.items.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="text-sm">{relativeTime(s.submitted_at)}</TableCell>
                    <TableCell className="font-mono text-xs">{s.supplier_order_id || "—"}</TableCell>
                    <TableCell className="text-xs">{s.response_status}</TableCell>
                    <TableCell className="text-xs">{s.tracking_status || "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
