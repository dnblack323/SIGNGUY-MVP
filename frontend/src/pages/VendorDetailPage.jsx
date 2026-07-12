import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft } from "lucide-react";
import { money, PO_STATUS_TONE } from "@/lib/ec7";
import { relativeTime } from "@/lib/format";

// EC7 phase 7d closure — Vendor Detail
// Shows vendor identity/capabilities + linked materials + purchase-order history.
// All money is backend `_cents`; no client-side pricing math.
export default function VendorDetailPage() {
  const { id } = useParams();
  const vendorQ = useQuery({
    queryKey: ["vendor", id],
    queryFn: async () => (await api.get(`/vendors/${id}`)).data,
  });
  const materialsQ = useQuery({
    queryKey: ["vendor-materials", id],
    queryFn: async () => (await api.get("/vendors/materials", { params: { vendor_id: id } })).data,
    enabled: Boolean(id),
  });
  const posQ = useQuery({
    queryKey: ["vendor-pos", id],
    queryFn: async () => (await api.get("/purchase-orders", { params: { vendor_id: id, limit: 100 } })).data,
    enabled: Boolean(id),
  });

  if (vendorQ.isLoading) return <div className="text-sm text-muted-foreground" data-testid="vendor-detail-loading">Loading…</div>;
  if (!vendorQ.data) return <div className="text-sm text-muted-foreground" data-testid="vendor-detail-not-found">Vendor not found.</div>;

  const vendor = vendorQ.data.vendor || {};
  const warehouses = vendorQ.data.warehouses || [];
  const linkedMaterials = materialsQ.data?.items || [];
  const pos = posQ.data?.items || [];

  return (
    <div className="space-y-4" data-testid="vendor-detail-page">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to="/purchase-orders" className="flex items-center gap-1 hover:text-foreground" data-testid="vendor-back-link">
          <ArrowLeft className="size-3" /> Back
        </Link>
      </div>
      <PageHeader
        title={vendor.display_name || vendor.name}
        subtitle={
          <span className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" data-testid="vendor-connector-badge">connector: {vendor.connector_key || "manual"}</Badge>
            <Badge variant="outline">tier: {vendor.connector_tier || "manual"}</Badge>
            {vendor.preferred && <Badge className="bg-emerald-100 text-emerald-800" data-testid="vendor-preferred-badge">preferred</Badge>}
            <Badge className={vendor.active ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700"} data-testid="vendor-active-badge">
              {vendor.active ? "active" : "archived"}
            </Badge>
          </span>
        }
      />

      <div className="grid md:grid-cols-3 gap-3">
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Account</CardTitle></CardHeader>
          <CardContent><div className="text-sm font-mono" data-testid="vendor-account-number">{vendor.account_number || "—"}</div></CardContent>
        </Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Contact</CardTitle></CardHeader>
          <CardContent>
            <div className="text-sm" data-testid="vendor-contact-email">{vendor.contact_email || "—"}</div>
            <div className="text-xs text-muted-foreground">{vendor.contact_phone || ""}</div>
          </CardContent>
        </Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">Website</CardTitle></CardHeader>
          <CardContent><div className="text-sm truncate" data-testid="vendor-website">{vendor.website || "—"}</div></CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Categories</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-1.5" data-testid="vendor-categories">
            {(vendor.categories || []).length === 0
              ? <span className="text-xs text-muted-foreground">No categories declared.</span>
              : (vendor.categories || []).map((c) => <Badge key={c} variant="secondary">{c}</Badge>)}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Warehouses</CardTitle></CardHeader>
        <CardContent>
          <div className="rounded-lg border overflow-hidden">
            <Table data-testid="vendor-warehouses-table">
              <TableHeader><TableRow>
                <TableHead>Code</TableHead><TableHead>Name</TableHead>
                <TableHead>Region</TableHead><TableHead>Lead time</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {warehouses.length === 0 ? <TableRow><TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-4">No warehouses on file.</TableCell></TableRow>
                : warehouses.map((w) => (
                  <TableRow key={w.id} data-testid={`vendor-warehouse-row-${w.code || w.id}`}>
                    <TableCell className="font-mono text-xs">{w.code || "—"}</TableCell>
                    <TableCell className="text-sm">{w.name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{w.region || "—"}</TableCell>
                    <TableCell className="text-sm">{w.lead_time_days != null ? `${w.lead_time_days} day(s)` : "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Linked materials</CardTitle></CardHeader>
        <CardContent>
          <div className="rounded-lg border overflow-hidden">
            <Table data-testid="vendor-materials-table">
              <TableHeader><TableRow>
                <TableHead>Material</TableHead><TableHead>Supplier SKU</TableHead>
                <TableHead>Preferred</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {materialsQ.isLoading ? <TableRow><TableCell colSpan={3} className="text-center text-sm text-muted-foreground py-4">Loading…</TableCell></TableRow>
                : linkedMaterials.length === 0 ? <TableRow><TableCell colSpan={3} className="text-center text-sm text-muted-foreground py-4">No materials linked to this vendor.</TableCell></TableRow>
                : linkedMaterials.map((m) => (
                  <TableRow key={m.id} data-testid={`vendor-material-row-${m.id}`}>
                    <TableCell className="text-sm">
                      <Link to={`/materials/${m.material_id}`} className="text-primary hover:underline">{m.material_id}</Link>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{m.supplier_sku || "—"}</TableCell>
                    <TableCell className="text-xs">{m.preferred ? "yes" : "no"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Purchase order history</CardTitle></CardHeader>
        <CardContent>
          <div className="rounded-lg border overflow-hidden">
            <Table data-testid="vendor-po-history-table">
              <TableHeader><TableRow>
                <TableHead>#</TableHead><TableHead>Status</TableHead>
                <TableHead className="text-right">Total</TableHead><TableHead>Created</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {posQ.isLoading ? <TableRow><TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-4">Loading…</TableCell></TableRow>
                : pos.length === 0 ? <TableRow><TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-4">No purchase orders for this vendor.</TableCell></TableRow>
                : pos.map((po) => (
                  <TableRow key={po.id} data-testid={`vendor-po-row-${po.id}`}>
                    <TableCell><Link to={`/purchase-orders/${po.id}`} className="text-primary hover:underline">#{po.number}</Link></TableCell>
                    <TableCell><Badge className={PO_STATUS_TONE[po.status] || ""}>{po.status}</Badge></TableCell>
                    <TableCell className="text-right text-sm">{money(po.total_cents)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{relativeTime(po.created_at)}</TableCell>
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
