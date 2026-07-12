import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { money } from "@/lib/ec7";

export default function TaxReportsPage() {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 1);
  const [range, setRange] = useState({ from: start.toISOString().slice(0, 10), to: now.toISOString().slice(0, 10) });
  const params = useMemo(() => ({ date_from: range.from, date_to: range.to }), [range]);

  const total = useQuery({ queryKey: ["tax-collected", params], queryFn: async () => (await api.get("/tax/collected", { params })).data });
  const byJur = useQuery({ queryKey: ["tax-jurisdiction", params], queryFn: async () => (await api.get("/tax/collected-by-jurisdiction", { params })).data });
  const overrides = useQuery({ queryKey: ["tax-overrides", params], queryFn: async () => (await api.get("/tax/manual-overrides", { params })).data });
  const exempts = useQuery({ queryKey: ["tax-exempt-customers", params], queryFn: async () => (await api.get("/tax/exempt-customers", { params })).data });
  const exemptions = useQuery({ queryKey: ["tax-exemption-list"], queryFn: async () => (await api.get("/tax/exemptions")).data });

  return (
    <div className="space-y-4" data-testid="tax-page">
      <PageHeader title="Tax Reports" subtitle="Historical Invoice tax values use stored snapshots. Changing current tax settings does not rewrite history. Reports are operational summaries, not filing advice." />
      <div className="grid grid-cols-2 gap-3 max-w-md">
        <div className="grid gap-1"><Label className="text-xs">From</Label><Input type="date" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} data-testid="tax-from-input" /></div>
        <div className="grid gap-1"><Label className="text-xs">To</Label><Input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} data-testid="tax-to-input" /></div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Card data-testid="tax-total-card">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Tax collected (snapshot basis)</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-semibold">{money(total.data?.value_cents || 0)}</div><div className="text-xs text-muted-foreground mt-1">{total.data?.invoice_count || 0} invoice(s)</div></CardContent>
        </Card>
        <Card data-testid="tax-manual-count">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Manual overrides</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-semibold">{overrides.data?.items?.length || 0}</div></CardContent>
        </Card>
        <Card data-testid="tax-exempt-count">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Exempt customers</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-semibold">{exempts.data?.items?.length || 0}</div></CardContent>
        </Card>
      </div>

      <Tabs defaultValue="jurisdiction">
        <TabsList data-testid="tax-tabs">
          <TabsTrigger value="jurisdiction" data-testid="tab-jurisdiction">By jurisdiction</TabsTrigger>
          <TabsTrigger value="exempt" data-testid="tab-exempt">Exempt customers</TabsTrigger>
          <TabsTrigger value="exemptions" data-testid="tab-exemptions">Exemption records</TabsTrigger>
          <TabsTrigger value="overrides" data-testid="tab-overrides">Manual overrides</TabsTrigger>
        </TabsList>
        <TabsContent value="jurisdiction" className="mt-3">
          <div className="rounded-xl border bg-card overflow-hidden"><Table>
            <TableHeader><TableRow><TableHead>Jurisdiction</TableHead><TableHead className="text-right">Subtotal</TableHead><TableHead className="text-right">Tax</TableHead><TableHead className="text-right">Invoices</TableHead></TableRow></TableHeader>
            <TableBody>
              {(byJur.data?.items || []).map((r, i) => (<TableRow key={i}><TableCell>{r.jurisdiction}</TableCell><TableCell className="text-right">{money(r.subtotal_cents)}</TableCell><TableCell className="text-right font-medium">{money(r.tax_cents)}</TableCell><TableCell className="text-right">{r.invoice_count}</TableCell></TableRow>))}
              {!byJur.data?.items?.length && <TableRow><TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-6">No tax collected in range.</TableCell></TableRow>}
            </TableBody>
          </Table></div>
        </TabsContent>
        <TabsContent value="exempt" className="mt-3">
          <div className="rounded-xl border bg-card overflow-hidden"><Table>
            <TableHeader><TableRow><TableHead>Customer</TableHead><TableHead>Company</TableHead><TableHead className="text-right">Invoices</TableHead><TableHead className="text-right">Subtotal</TableHead><TableHead className="text-right">Tax charged</TableHead></TableRow></TableHeader>
            <TableBody>
              {(exempts.data?.items || []).map((r) => (<TableRow key={r.customer_id}><TableCell>{r.customer_name}</TableCell><TableCell className="text-muted-foreground text-sm">{r.customer_company || "—"}</TableCell><TableCell className="text-right">{r.invoice_count}</TableCell><TableCell className="text-right">{money(r.subtotal_cents)}</TableCell><TableCell className="text-right">{money(r.tax_cents)}</TableCell></TableRow>))}
              {!exempts.data?.items?.length && <TableRow><TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-6">No exempt customers.</TableCell></TableRow>}
            </TableBody>
          </Table></div>
        </TabsContent>
        <TabsContent value="exemptions" className="mt-3">
          <div className="rounded-xl border bg-card overflow-hidden"><Table>
            <TableHeader><TableRow><TableHead>Customer</TableHead><TableHead>Jurisdiction</TableHead><TableHead>Reference</TableHead><TableHead>Effective from</TableHead><TableHead>Effective to</TableHead></TableRow></TableHeader>
            <TableBody>
              {(exemptions.data?.items || []).map((r) => (<TableRow key={r.id}><TableCell>{r.customer_id}</TableCell><TableCell>{r.jurisdiction}</TableCell><TableCell>{r.reference}</TableCell><TableCell>{r.effective_from}</TableCell><TableCell>{r.effective_to || "—"}</TableCell></TableRow>))}
              {!exemptions.data?.items?.length && <TableRow><TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-6">No exemptions recorded.</TableCell></TableRow>}
            </TableBody>
          </Table></div>
        </TabsContent>
        <TabsContent value="overrides" className="mt-3">
          <div className="rounded-xl border bg-card overflow-hidden"><Table>
            <TableHeader><TableRow><TableHead>Invoice #</TableHead><TableHead>Issued</TableHead><TableHead className="text-right">Tax</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader>
            <TableBody>
              {(overrides.data?.items || []).map((r) => (<TableRow key={r.invoice_id}><TableCell>#{r.number}</TableCell><TableCell className="text-sm text-muted-foreground">{r.issued_at?.slice(0, 10)}</TableCell><TableCell className="text-right">{money(r.tax_cents)}</TableCell><TableCell className="text-sm">{r.override_reason || "—"}</TableCell></TableRow>))}
              {!overrides.data?.items?.length && <TableRow><TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-6">No manual overrides in range.</TableCell></TableRow>}
            </TableBody>
          </Table></div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
