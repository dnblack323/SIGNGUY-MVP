import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AlertTriangle, Info } from "lucide-react";
import { money, basisLabel } from "@/lib/ec7";

function BasisCard({ title, metric, hint }) {
  if (!metric) return null;
  const empty = metric.empty;
  return (
    <Card data-testid={`finance-card-${title.replace(/\s+/g, "-").toLowerCase()}`} className="min-w-0">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm text-muted-foreground">{title}</CardTitle>
          <Badge variant="outline" data-testid="finance-basis-badge" className="text-[10px] uppercase tracking-wider">
            {basisLabel(metric.basis)}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold">
          {typeof metric.value_cents === "number" ? money(metric.value_cents) : "—"}
        </div>
        {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
        {empty && (
          <div className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
            <Info className="size-3" /> No data in range
          </div>
        )}
        {Array.isArray(metric.warnings) && metric.warnings.length > 0 && (
          <div className="text-xs text-amber-700 mt-2 flex items-start gap-1">
            <AlertTriangle className="size-3 mt-0.5 shrink-0" />
            <span>{metric.warnings.join("; ")}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TrendChart({ title, series, basis }) {
  if (!series?.length) return null;
  const max = Math.max(1, ...series.map((s) => s.value_cents));
  return (
    <Card data-testid={`finance-trend-${title.replace(/\s+/g, "-").toLowerCase()}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm text-muted-foreground">{title}</CardTitle>
          <Badge variant="outline" className="text-[10px] uppercase tracking-wider">{basisLabel(basis)}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-1 h-32">
          {series.map((s) => (
            <div key={s.period} className="flex-1 flex flex-col items-center gap-1 min-w-0">
              <div className="w-full bg-primary/70 rounded-sm" style={{ height: `${(s.value_cents / max) * 100}%` }} title={`${s.period}: ${money(s.value_cents)}`} />
              <div className="text-[10px] text-muted-foreground truncate w-full text-center">{s.period.slice(2)}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function Filters({ range, setRange }) {
  return (
    <div className="grid grid-cols-2 gap-3 max-w-md" data-testid="finance-filters">
      <div className="grid gap-1"><Label className="text-xs">From</Label><Input type="date" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} data-testid="finance-from-input" /></div>
      <div className="grid gap-1"><Label className="text-xs">To</Label><Input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} data-testid="finance-to-input" /></div>
    </div>
  );
}

export default function FinanceDashboardPage() {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() - 5, 1);
  const [range, setRange] = useState({
    from: start.toISOString().slice(0, 10),
    to: now.toISOString().slice(0, 10),
  });
  const params = useMemo(() => ({ date_from: range.from, date_to: range.to }), [range]);

  const summary = useQuery({
    queryKey: ["finance-summary", params],
    queryFn: async () => (await api.get("/finance/summary", { params })).data,
  });
  const revTrend = useQuery({
    queryKey: ["finance-rev-trend", params],
    queryFn: async () => (await api.get("/finance/revenue-trend", { params })).data,
  });
  const payTrend = useQuery({
    queryKey: ["finance-pay-trend", params],
    queryFn: async () => (await api.get("/finance/payments-received-trend", { params })).data,
  });
  const expTrend = useQuery({
    queryKey: ["finance-exp-trend", params],
    queryFn: async () => (await api.get("/finance/expense-trend", { params })).data,
  });

  const s = summary.data;
  return (
    <div className="space-y-4" data-testid="finance-page">
      <PageHeader
        title="Finance Dashboard"
        subtitle="Labeled-basis metrics. Cash-received and Invoice-basis totals are shown side by side — never silently mixed."
      />
      <Filters range={range} setRange={setRange} />

      {summary.isLoading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : summary.error ? (
        <div className="text-sm text-rose-700">Couldn't load summary.</div>
      ) : s ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <BasisCard title="Invoice revenue" metric={s.revenue_issued_invoices} hint="Issued invoices in range" />
            <BasisCard title="Payments received" metric={s.payments_received} hint="Confirmed cash + card + Stripe" />
            <BasisCard title="Refunds" metric={s.refunds} hint="Never silently netted from revenue" />
            <BasisCard title="Outstanding A/R" metric={s.outstanding_receivables} hint="Unpaid + partial invoices" />
            <BasisCard title="Expenses" metric={s.expenses} hint="Active only (voided + archived excluded)" />
            <BasisCard title="Tax collected" metric={s.tax_collected} hint="Historical snapshot values" />
            <BasisCard title="Estimated gross profit" metric={s.estimated_gross_profit} hint={`Coverage: ${s.estimated_gross_profit?.coverage_label || "unknown"}`} />
            <BasisCard title="Estimated net operating" metric={s.estimated_net_operating} hint="Revenue − Expenses − Refunds" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {revTrend.data && <TrendChart title="Revenue trend" series={revTrend.data.series} basis={revTrend.data.basis} />}
            {payTrend.data && <TrendChart title="Payments trend" series={payTrend.data.series} basis={payTrend.data.basis} />}
            {expTrend.data && <TrendChart title="Expense trend" series={expTrend.data.series} basis={expTrend.data.basis} />}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Card data-testid="finance-top-customers">
              <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Top customers by revenue</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader><TableRow><TableHead>Customer</TableHead><TableHead>Invoices</TableHead><TableHead className="text-right">Revenue</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {(s.top_customers?.items || []).map((r) => (
                      <TableRow key={r.customer_id}>
                        <TableCell>{r.customer_name || r.customer_id}</TableCell>
                        <TableCell>{r.invoice_count}</TableCell>
                        <TableCell className="text-right">{money(r.revenue_cents)}</TableCell>
                      </TableRow>
                    ))}
                    {!(s.top_customers?.items?.length) && <TableRow><TableCell colSpan={3} className="text-sm text-muted-foreground text-center">No customers in range.</TableCell></TableRow>}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card data-testid="finance-pm-breakdown">
              <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Payment method breakdown</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader><TableRow><TableHead>Source</TableHead><TableHead>Method</TableHead><TableHead>Count</TableHead><TableHead className="text-right">Received</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {(s.payment_method_breakdown?.items || []).map((r, i) => (
                      <TableRow key={i}>
                        <TableCell>{r.source}</TableCell>
                        <TableCell>{r.method || "—"}</TableCell>
                        <TableCell>{r.count}</TableCell>
                        <TableCell className="text-right">{money(r.value_cents)}</TableCell>
                      </TableRow>
                    ))}
                    {!(s.payment_method_breakdown?.items?.length) && <TableRow><TableCell colSpan={4} className="text-sm text-muted-foreground text-center">No payments in range.</TableCell></TableRow>}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Limitations</CardTitle></CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-1">
              {(s.limitations || []).map((l, i) => <div key={i}>• {l}</div>)}
              <div className="pt-2 italic">Operational summary — not audited accounting output.</div>
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
