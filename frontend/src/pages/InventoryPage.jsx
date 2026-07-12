import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { money } from "@/lib/ec7";
import { relativeTime } from "@/lib/format";

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
                <TableCell>{m.name}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{m.category || "—"}</TableCell>
                <TableCell className="text-sm">{m.purchase_unit || "each"}</TableCell>
                <TableCell className="text-right text-sm">{money(m.current_cost_cents)}</TableCell>
                <TableCell className="text-right text-sm">{m.low_stock_threshold ?? "—"}</TableCell>
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
                  <TableCell className="text-sm">{it.material_id}</TableCell>
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
  return (
    <div className="space-y-4" data-testid="inventory-page">
      <PageHeader title="Inventory & Purchasing" subtitle="Materials, stock levels, movements, and locations. Reserved stock remains on hand — it is not physically removed." />
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
