import { useParams, Link } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger, SheetDescription } from "@/components/ui/sheet";
import { ArrowLeft } from "lucide-react";
import { money } from "@/lib/ec7";
import { relativeTime, formatDateTime } from "@/lib/format";

// EC7 phase 7d closure — Material Detail
// Shows material metadata + per-location balances + Cost History drawer.
// Cost history is a read-only immutable ledger written by receiving and manual
// cost changes; historical rows never mutate.
function CostHistoryDrawer({ history }) {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button size="sm" variant="outline" data-testid="material-cost-history-open">
          View cost history
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full sm:max-w-lg" data-testid="material-cost-history-drawer">
        <SheetHeader>
          <SheetTitle>Material cost history</SheetTitle>
          <SheetDescription>
            Immutable append-only ledger. Every cost change from receiving or a manual edit is recorded here without rewriting historical rows.
          </SheetDescription>
        </SheetHeader>
        <div className="mt-4 rounded-lg border overflow-hidden">
          <Table data-testid="material-cost-history-table">
            <TableHeader><TableRow>
              <TableHead>Effective</TableHead>
              <TableHead className="text-right">Cost</TableHead>
              <TableHead>Unit</TableHead>
              <TableHead>Source</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {history.length === 0 ? <TableRow><TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-4">No cost history yet.</TableCell></TableRow>
              : history.map((h) => (
                <TableRow key={h.id} data-testid={`material-cost-row-${h.id}`}>
                  <TableCell className="text-xs">{formatDateTime(h.effective_at)}</TableCell>
                  <TableCell className="text-right text-sm">{money(h.cost_cents)}</TableCell>
                  <TableCell className="text-xs">{h.cost_unit}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{h.source || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default function MaterialDetailPage() {
  const { id } = useParams();
  const matQ = useQuery({
    queryKey: ["material", id],
    queryFn: async () => (await api.get(`/materials/${id}`)).data,
  });
  const movementsQ = useQuery({
    queryKey: ["material-movements", id],
    queryFn: async () => (await api.get("/inventory/movements", { params: { material_id: id, limit: 100 } })).data,
    enabled: Boolean(id),
  });

  if (matQ.isLoading) return <div className="text-sm text-muted-foreground" data-testid="material-detail-loading">Loading…</div>;
  if (!matQ.data) return <div className="text-sm text-muted-foreground" data-testid="material-detail-not-found">Material not found.</div>;

  const material = matQ.data.material || {};
  const balances = matQ.data.balances || [];
  const costHistory = matQ.data.cost_history || [];
  const movements = movementsQ.data?.items || [];

  const totalOnHand = balances.reduce((n, b) => n + Number(b.quantity_on_hand || 0), 0);
  const totalReserved = balances.reduce((n, b) => n + Number(b.quantity_reserved || 0), 0);
  const totalAvailable = Math.max(totalOnHand - totalReserved, 0);

  return (
    <div className="space-y-4" data-testid="material-detail-page">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to="/inventory" className="flex items-center gap-1 hover:text-foreground" data-testid="material-back-link">
          <ArrowLeft className="size-3" /> Back to Inventory
        </Link>
      </div>
      <PageHeader
        title={material.name}
        subtitle={
          <span className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs" data-testid="material-sku">{material.sku || "no SKU"}</span>
            {material.category && <Badge variant="outline">{material.category}</Badge>}
            {!material.active && <Badge className="bg-slate-100 text-slate-700">archived</Badge>}
          </span>
        }
        actions={<CostHistoryDrawer history={costHistory} />}
      />

      <div className="grid md:grid-cols-4 gap-3">
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Current cost</CardTitle></CardHeader>
          <CardContent>
            <div className="text-lg font-semibold" data-testid="material-current-cost">{money(material.current_cost_cents)}</div>
            <div className="text-[10px] text-muted-foreground mt-1">per {material.cost_unit || "each"}</div>
          </CardContent>
        </Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">On hand</CardTitle></CardHeader>
          <CardContent><div className="text-lg font-semibold" data-testid="material-on-hand">{totalOnHand}</div></CardContent>
        </Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Reserved</CardTitle></CardHeader>
          <CardContent><div className="text-lg font-semibold" data-testid="material-reserved">{totalReserved}</div></CardContent>
        </Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Available</CardTitle></CardHeader>
          <CardContent><div className="text-lg font-semibold" data-testid="material-available">{totalAvailable}</div></CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Metadata</CardTitle></CardHeader>
        <CardContent className="grid md:grid-cols-3 gap-3 text-sm">
          <div><div className="text-xs text-muted-foreground">Manufacturer</div><div>{material.manufacturer || "—"}</div></div>
          <div><div className="text-xs text-muted-foreground">Brand</div><div>{material.brand || "—"}</div></div>
          <div><div className="text-xs text-muted-foreground">Series</div><div>{material.series || "—"}</div></div>
          <div><div className="text-xs text-muted-foreground">Purchase unit</div><div>{material.purchase_unit || "each"}</div></div>
          <div><div className="text-xs text-muted-foreground">Unit of measure</div><div>{material.unit_of_measure || "each"}</div></div>
          <div><div className="text-xs text-muted-foreground">Reorder point</div><div>{material.reorder_point ?? "—"}</div></div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Balances by location</CardTitle></CardHeader>
        <CardContent>
          <div className="rounded-lg border overflow-hidden">
            <Table data-testid="material-balances-table">
              <TableHeader><TableRow>
                <TableHead>Location</TableHead>
                <TableHead className="text-right">On hand</TableHead>
                <TableHead className="text-right">Reserved</TableHead>
                <TableHead className="text-right">Available</TableHead>
                <TableHead>Last received</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {balances.length === 0 ? <TableRow><TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-4">No stock recorded for this material.</TableCell></TableRow>
                : balances.map((b) => {
                  const avail = Math.max(Number(b.quantity_on_hand || 0) - Number(b.quantity_reserved || 0), 0);
                  return (
                    <TableRow key={b.id} data-testid={`material-balance-row-${b.location_id}`}>
                      <TableCell className="text-sm">{b.location_id}</TableCell>
                      <TableCell className="text-right text-sm">{b.quantity_on_hand}</TableCell>
                      <TableCell className="text-right text-sm text-muted-foreground">{b.quantity_reserved}</TableCell>
                      <TableCell className="text-right text-sm font-medium">{avail}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{relativeTime(b.last_received_at)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Recent movements</CardTitle></CardHeader>
        <CardContent>
          <div className="rounded-lg border overflow-hidden">
            <Table data-testid="material-movements-table">
              <TableHeader><TableRow>
                <TableHead>Timestamp</TableHead><TableHead>Type</TableHead><TableHead>Direction</TableHead>
                <TableHead className="text-right">Qty</TableHead><TableHead>Location</TableHead><TableHead>Reason</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {movementsQ.isLoading ? <TableRow><TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-4">Loading…</TableCell></TableRow>
                : movements.length === 0 ? <TableRow><TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-4">No movements recorded for this material.</TableCell></TableRow>
                : movements.map((m) => (
                  <TableRow key={m.id} data-testid={`material-movement-row-${m.id}`}>
                    <TableCell className="text-xs text-muted-foreground">{relativeTime(m.created_at)}</TableCell>
                    <TableCell className="text-sm">{m.movement_type}</TableCell>
                    <TableCell className="text-xs">{m.direction}</TableCell>
                    <TableCell className="text-right text-sm">{m.quantity}</TableCell>
                    <TableCell className="text-sm">{m.location_id}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{m.reason || "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
