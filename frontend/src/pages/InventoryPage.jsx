import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { money } from "@/lib/ec7";
import { relativeTime } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";

// -------- Adjustment dialogs --------

// Physical Count wizard: pick location + material + observed qty → compute
// delta preview against current on-hand (backend still authoritative), reason
// required. Idempotency-Key protects against accidental double-submits.
function PhysicalCountDialog({ locations, onDone }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [locationId, setLocationId] = useState("");
  const [materialId, setMaterialId] = useState("");
  const [observed, setObserved] = useState("");
  const [reason, setReason] = useState("");

  // fetch current on-hand for the selected material+location
  const balQ = useQuery({
    enabled: Boolean(open && materialId && locationId),
    queryKey: ["inv-item-lookup", materialId, locationId],
    queryFn: async () => (await api.get("/inventory/items", { params: { material_id: materialId, location_id: locationId } })).data,
  });
  const currentOnHand = balQ.data?.items?.[0]?.quantity_on_hand ?? 0;
  const observedNum = observed === "" ? null : Number(observed);
  const delta = observedNum == null || Number.isNaN(observedNum) ? null : observedNum - Number(currentOnHand || 0);

  async function submit() {
    if (busy) return;
    if (!locationId || !materialId) { toast.error("Location and material are required"); return; }
    if (observedNum == null || Number.isNaN(observedNum) || observedNum < 0) { toast.error("Observed quantity must be a non-negative number"); return; }
    if (!reason.trim()) { toast.error("Reason is required for a physical count"); return; }
    setBusy(true);
    try {
      const key = crypto.randomUUID();
      await api.post(
        "/inventory/adjustments/count",
        { material_id: materialId, location_id: locationId, observed_quantity: observedNum, reason },
        { headers: { "Idempotency-Key": key } },
      );
      toast.success("Physical count recorded");
      setOpen(false); setMaterialId(""); setObserved(""); setReason(""); onDone?.();
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" data-testid="physical-count-open">Physical count</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Physical count</DialogTitle>
          <DialogDescription>
            Record an observed count. The backend writes an immutable inventory movement, updates on-hand to the observed quantity, and stamps a reason on the audit trail.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>Location</Label>
            <select value={locationId} onChange={(e) => setLocationId(e.target.value)} data-testid="physical-count-location" className="h-9 rounded-md border bg-background px-2 text-sm">
              <option value="">Select a location…</option>
              {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </div>
          <div className="grid gap-1.5">
            <Label>Material ID</Label>
            <Input placeholder="Paste material id from Inventory > Materials" value={materialId} onChange={(e) => setMaterialId(e.target.value)} data-testid="physical-count-material" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>Current on-hand</Label>
              <div className="h-9 rounded-md border bg-muted/40 px-2 text-sm flex items-center" data-testid="physical-count-current">
                {materialId && locationId ? (balQ.isLoading ? "loading…" : currentOnHand) : "—"}
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label>Observed</Label>
              <Input type="number" min="0" step="0.01" value={observed} onChange={(e) => setObserved(e.target.value)} data-testid="physical-count-observed" />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Delta preview</Label>
            <div className="h-9 rounded-md border bg-muted/40 px-2 text-sm flex items-center" data-testid="physical-count-delta">
              {delta == null ? "—" : (delta > 0 ? `+${delta}` : String(delta))}
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Reason (required)</Label>
            <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="physical-count-reason" placeholder="e.g. quarterly cycle count" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={submit} disabled={busy} data-testid="physical-count-confirm">{busy ? "Recording…" : "Record count"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Inventory Transfer: move stock from one location to another. Backend writes
// paired transfer_out / transfer_in movements atomically.
function TransferDialog({ locations, onDone }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [materialId, setMaterialId] = useState("");
  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");
  const [qty, setQty] = useState("");
  const [reason, setReason] = useState("");

  async function submit() {
    if (busy) return;
    if (!materialId || !fromId || !toId) { toast.error("Material and both locations are required"); return; }
    if (fromId === toId) { toast.error("From and to locations must differ"); return; }
    const q = Number(qty);
    if (!q || Number.isNaN(q) || q <= 0) { toast.error("Quantity must be greater than zero"); return; }
    setBusy(true);
    try {
      const key = crypto.randomUUID();
      await api.post(
        "/inventory/transfers",
        { material_id: materialId, from_location_id: fromId, to_location_id: toId, quantity: q, reason: reason || undefined },
        { headers: { "Idempotency-Key": key } },
      );
      toast.success("Transfer recorded");
      setOpen(false); setMaterialId(""); setFromId(""); setToId(""); setQty(""); setReason(""); onDone?.();
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" data-testid="transfer-open">Transfer stock</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Transfer inventory</DialogTitle>
          <DialogDescription>
            Move stock between locations. The backend writes paired transfer_out and transfer_in movements — the on-hand total across locations does not change.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>Material ID</Label>
            <Input placeholder="Paste material id from Inventory > Materials" value={materialId} onChange={(e) => setMaterialId(e.target.value)} data-testid="transfer-material" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>From location</Label>
              <select value={fromId} onChange={(e) => setFromId(e.target.value)} data-testid="transfer-from" className="h-9 rounded-md border bg-background px-2 text-sm">
                <option value="">Select…</option>
                {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
            <div className="grid gap-1.5">
              <Label>To location</Label>
              <select value={toId} onChange={(e) => setToId(e.target.value)} data-testid="transfer-to" className="h-9 rounded-md border bg-background px-2 text-sm">
                <option value="">Select…</option>
                {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Quantity</Label>
            <Input type="number" min="0" step="0.01" value={qty} onChange={(e) => setQty(e.target.value)} data-testid="transfer-quantity" />
          </div>
          <div className="grid gap-1.5">
            <Label>Reason (optional)</Label>
            <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="transfer-reason" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={submit} disabled={busy} data-testid="transfer-confirm">{busy ? "Transferring…" : "Confirm transfer"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// -------- Tabs --------

function MaterialsTab() {
  const [q, setQ] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["materials", q],
    queryFn: async () => (await api.get("/materials", { params: { search: q || undefined, limit: 200 } })).data,
  });
  const items = data?.items || [];
  return (
    <div className="space-y-3" data-testid="inventory-materials-tab">
      <Input placeholder="Search by name / SKU" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-md" data-testid="materials-search" />
      <div className="rounded-xl border bg-card overflow-hidden">
        <Table data-testid="materials-table">
          <TableHeader><TableRow>
            <TableHead>SKU</TableHead><TableHead>Name</TableHead><TableHead>Category</TableHead>
            <TableHead>Unit</TableHead><TableHead className="text-right">Cost</TableHead>
            <TableHead className="text-right">Low-stock threshold</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {isLoading ? <TableRow><TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-6">Loading…</TableCell></TableRow>
            : items.length === 0 ? <TableRow><TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-6">No materials yet.</TableCell></TableRow>
            : items.map((m) => (
              <TableRow key={m.id} data-testid={`material-row-${m.id}`}>
                <TableCell className="font-mono text-xs">{m.sku || "—"}</TableCell>
                <TableCell>
                  <Link to={`/materials/${m.id}`} className="text-primary hover:underline" data-testid={`material-open-${m.id}`}>{m.name}</Link>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{m.category || "—"}</TableCell>
                <TableCell className="text-sm">{m.purchase_unit || "each"}</TableCell>
                <TableCell className="text-right text-sm">{money(m.current_cost_cents)}</TableCell>
                <TableCell className="text-right text-sm">{m.low_stock_threshold ?? m.reorder_point ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function ItemsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["inv-items"],
    queryFn: async () => (await api.get("/inventory/items", { params: { limit: 500 } })).data,
  });
  const items = data?.items || [];
  return (
    <div data-testid="inventory-items-tab">
      <div className="rounded-xl border bg-card overflow-hidden">
        <Table data-testid="inventory-items-table">
          <TableHeader><TableRow>
            <TableHead>Material</TableHead><TableHead>Location</TableHead>
            <TableHead className="text-right">On hand</TableHead>
            <TableHead className="text-right">Reserved</TableHead>
            <TableHead className="text-right">Available</TableHead>
            <TableHead>Last received</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {isLoading ? <TableRow><TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-6">Loading…</TableCell></TableRow>
            : items.length === 0 ? <TableRow><TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-6">No stock recorded yet.</TableCell></TableRow>
            : items.map((it) => {
              const available = Math.max((it.quantity_on_hand || 0) - (it.quantity_reserved || 0), 0);
              return (
                <TableRow key={it.id} data-testid={`inv-item-row-${it.id}`}>
                  <TableCell className="text-sm">
                    <Link to={`/materials/${it.material_id}`} className="text-primary hover:underline">{it.material_id}</Link>
                  </TableCell>
                  <TableCell className="text-sm">{it.location_id}</TableCell>
                  <TableCell className="text-right text-sm">{it.quantity_on_hand}</TableCell>
                  <TableCell className="text-right text-sm text-muted-foreground">{it.quantity_reserved}</TableCell>
                  <TableCell className="text-right text-sm font-medium">{available}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{relativeTime(it.last_received_at)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground mt-2">Reserved stock is NOT physically removed from inventory — it is on hand but earmarked for open orders.</p>
    </div>
  );
}

function MovementsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["inv-movements"],
    queryFn: async () => (await api.get("/inventory/movements", { params: { limit: 200 } })).data,
  });
  const rows = data?.items || [];
  return (
    <div data-testid="inventory-movements-tab" className="rounded-xl border bg-card overflow-hidden">
      <Table data-testid="inventory-movements-table">
        <TableHeader><TableRow>
          <TableHead>Timestamp</TableHead><TableHead>Type</TableHead><TableHead>Direction</TableHead>
          <TableHead className="text-right">Qty</TableHead><TableHead>Material</TableHead>
          <TableHead>Location</TableHead><TableHead>Reason</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {isLoading ? <TableRow><TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-6">Loading…</TableCell></TableRow>
          : rows.length === 0 ? <TableRow><TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-6">No movements yet.</TableCell></TableRow>
          : rows.map((m) => (
            <TableRow key={m.id}>
              <TableCell className="text-sm text-muted-foreground">{relativeTime(m.created_at)}</TableCell>
              <TableCell className="text-sm">{m.movement_type}</TableCell>
              <TableCell className="text-xs">{m.direction}</TableCell>
              <TableCell className="text-right text-sm">{m.quantity}</TableCell>
              <TableCell className="text-sm">{m.material_id}</TableCell>
              <TableCell className="text-sm">{m.location_id}</TableCell>
              <TableCell className="text-sm text-muted-foreground">{m.reason || "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function LocationsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["inv-locations"],
    queryFn: async () => (await api.get("/inventory/locations")).data,
  });
  const items = data?.items || [];
  return (
    <div data-testid="inventory-locations-tab" className="rounded-xl border bg-card overflow-hidden">
      <Table data-testid="inventory-locations-table">
        <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Kind</TableHead><TableHead>Active</TableHead></TableRow></TableHeader>
        <TableBody>
          {isLoading ? <TableRow><TableCell colSpan={3} className="text-center text-sm text-muted-foreground py-6">Loading…</TableCell></TableRow>
          : items.length === 0 ? <TableRow><TableCell colSpan={3} className="text-center text-sm text-muted-foreground py-6">No locations yet.</TableCell></TableRow>
          : items.map((l) => (
            <TableRow key={l.id}><TableCell>{l.name}</TableCell><TableCell className="text-xs">{l.kind}</TableCell><TableCell>{l.active ? "Yes" : "No"}</TableCell></TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default function InventoryPage() {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm ? hasPerm("inventory:write") : true;
  const locs = useQuery({ queryKey: ["inv-locations"], queryFn: async () => (await api.get("/inventory/locations")).data });
  const locations = locs.data?.items || [];
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["inv-items"] });
    qc.invalidateQueries({ queryKey: ["inv-movements"] });
    qc.invalidateQueries({ queryKey: ["inv-item-lookup"] });
  };

  return (
    <div className="space-y-4" data-testid="inventory-page">
      <PageHeader
        title="Inventory & Purchasing"
        subtitle="Materials, stock levels, movements, and locations. Reserved stock remains on hand — it is not physically removed."
        actions={
          canWrite && (
            <div className="flex items-center gap-2">
              <PhysicalCountDialog locations={locations} onDone={invalidate} />
              <TransferDialog locations={locations} onDone={invalidate} />
            </div>
          )
        }
      />
      <Tabs defaultValue="items" className="w-full">
        <TabsList data-testid="inventory-tabs">
          <TabsTrigger value="items" data-testid="tab-items">Items</TabsTrigger>
          <TabsTrigger value="materials" data-testid="tab-materials">Materials</TabsTrigger>
          <TabsTrigger value="movements" data-testid="tab-movements">Movements</TabsTrigger>
          <TabsTrigger value="locations" data-testid="tab-locations">Locations</TabsTrigger>
        </TabsList>
        <TabsContent value="items" className="mt-4"><ItemsTab /></TabsContent>
        <TabsContent value="materials" className="mt-4"><MaterialsTab /></TabsContent>
        <TabsContent value="movements" className="mt-4"><MovementsTab /></TabsContent>
        <TabsContent value="locations" className="mt-4"><LocationsTab /></TabsContent>
      </Tabs>
      <p className="text-xs text-muted-foreground">Also see: Supply Center (supplier catalog + shortage recommendations) and Purchase Orders.</p>
    </div>
  );
}
