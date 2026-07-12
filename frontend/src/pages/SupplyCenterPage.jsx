import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Sparkles, ShieldAlert } from "lucide-react";
import { money } from "@/lib/ec7";
import { useAuth } from "@/auth/AuthContext";

const DEMO_BANNER = "SYNTHETIC DEMO DATA — NOT REAL SUPPLIER PRICING. Test adapter only.";

export default function SupplyCenterPage() {
  const qc = useQueryClient();
  const { hasPerm, devBypass } = useAuth();
  const canWrite = hasPerm("purchasing:write");
  const [q, setQ] = useState("");

  const catalog = useQuery({
    queryKey: ["supply-catalog", q],
    queryFn: async () => (await api.get("/supply/catalog", { params: { q: q || undefined, limit: 100 } })).data,
  });
  const vendors = useQuery({
    queryKey: ["vendors"],
    queryFn: async () => (await api.get("/vendors")).data,
  });
  const seedMut = useMutation({
    mutationFn: async () => (await api.post("/vendors/seed/test-adapter?reset=false")).data,
    onSuccess: (data) => { toast.success(`Seeded ${data.products} synthetic SKUs`); qc.invalidateQueries({ queryKey: ["supply-catalog"] }); qc.invalidateQueries({ queryKey: ["vendors"] }); },
    onError: (err) => toast.error(extractError(err)),
  });

  const items = catalog.data?.items || [];
  const isSynthetic = items.some((it) => it.seed_source === "test_adapter");
  const hasVendors = (vendors.data?.items || []).length > 0;

  return (
    <div className="space-y-4" data-testid="supply-center-page">
      <PageHeader
        title="Supply Center"
        subtitle="Search the supplier catalog, compare warehouses, and build purchase orders. Recommendation engine never crosses compatibility groups."
        actions={canWrite && devBypass && (
          <Button variant="outline" onClick={() => seedMut.mutate()} disabled={seedMut.isPending} data-testid="supply-seed-button">
            <Sparkles className="size-4 mr-1" />{seedMut.isPending ? "Seeding…" : "Seed synthetic catalog"}
          </Button>
        )}
      />
      {isSynthetic && (
        <div className="rounded-md border border-amber-200 bg-amber-50 text-amber-900 text-xs px-3 py-2 flex items-center gap-2" data-testid="supply-synthetic-banner">
          <ShieldAlert className="size-4" /><span>{DEMO_BANNER}</span>
        </div>
      )}
      {!hasVendors && (
        <div className="rounded-xl border bg-muted/40 p-6 text-center text-sm text-muted-foreground" data-testid="supply-empty-state">
          No vendors configured yet. In dev/test, click <b>Seed synthetic catalog</b> to load ~80 SKUs across 4 synthetic vendors.
        </div>
      )}
      <div className="flex items-center gap-2">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by description, SKU, brand, or family" className="max-w-md" data-testid="supply-search" />
      </div>
      <div className="rounded-xl border bg-card overflow-hidden">
        <Table data-testid="supply-catalog-table">
          <TableHeader><TableRow>
            <TableHead>SKU</TableHead><TableHead>Description</TableHead>
            <TableHead>Category</TableHead><TableHead>Vendor</TableHead>
            <TableHead className="text-right">Account price</TableHead>
            <TableHead>Compat group</TableHead>
            <TableHead>Status</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {catalog.isLoading ? <TableRow><TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-6">Loading…</TableCell></TableRow>
            : items.length === 0 ? <TableRow><TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-6">No supplier products {q ? `matching "${q}"` : "yet"}.</TableCell></TableRow>
            : items.map((p) => (
              <TableRow key={p.id} data-testid={`supplier-product-row-${p.id}`}>
                <TableCell className="font-mono text-xs">{p.supplier_sku}</TableCell>
                <TableCell className="text-sm">{p.description}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{p.category}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{p.brand}</TableCell>
                <TableCell className="text-right text-sm">{money(p.account_price_cents)}</TableCell>
                <TableCell className="text-xs">{p.compatible_group || "—"}</TableCell>
                <TableCell>{p.discontinued ? <Badge className="bg-rose-100 text-rose-800">Discontinued</Badge> : <Badge className="bg-emerald-100 text-emerald-800">Active</Badge>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">Shortage detection, price comparison across warehouses, and PO cart checkout are backed by <span className="mono">/api/supply/*</span>. The recommender NEVER treats products from different compatibility groups (e.g. cast vs calendared vinyl) as substitutes.</p>
    </div>
  );
}
