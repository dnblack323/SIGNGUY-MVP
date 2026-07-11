import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import InvoicePairedStatus from "@/components/invoices/InvoicePairedStatus";
import { centsToDollarsString, relativeTime } from "@/lib/format";
import { Receipt } from "lucide-react";

export default function InvoicesPage() {
  const [status, setStatus] = useState("all");
  const { data, isLoading } = useQuery({
    queryKey: ["invoices", status],
    queryFn: async () => (await api.get("/invoices", { params: { status: status === "all" ? undefined : status, limit: 100 } })).data,
  });
  const items = data?.items || [];
  return (
    <div className="space-y-4" data-testid="invoices-page">
      <PageHeader title="Invoices" subtitle="One per order. Dual document + financial status." />
      <div className="flex flex-wrap gap-2">
        {["all", "draft", "sent", "viewed", "partially_paid", "paid", "overdue", "void"].map((s) => (
          <Button key={s} variant={status === s ? "default" : "outline"} size="sm" onClick={() => setStatus(s)} data-testid={`invoices-filter-${s}`}>
            <span className="capitalize">{s.replace("_", " ")}</span>
          </Button>
        ))}
      </div>
      {isLoading ? <TableSkeleton /> : items.length === 0 ? (
        <EmptyState icon={Receipt} title="No invoices yet" description="Create an invoice from an Order." />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="invoices-table">
            <TableHeader><TableRow>
              <TableHead>#</TableHead>
              <TableHead>Title</TableHead>
              <TableHead className="text-right">Total</TableHead>
              <TableHead className="text-right">Balance</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map((inv) => (
                <TableRow key={inv.id} className="hover:bg-muted/40" data-testid={`invoice-row-${inv.id}`}>
                  <TableCell className="mono text-xs">I-{inv.number}</TableCell>
                  <TableCell><Link className="font-medium hover:underline" to={`/invoices/${inv.id}`}>{inv.title}</Link></TableCell>
                  <TableCell className="text-right tabular-nums">{centsToDollarsString(inv.total_cents)}</TableCell>
                  <TableCell className="text-right tabular-nums">{centsToDollarsString(inv.balance_due_cents)}</TableCell>
                  <TableCell>
                    <InvoicePairedStatus
                      documentStatus={inv.document_status || (inv.status === "void" ? "void" : inv.status === "draft" ? "draft" : "issued")}
                      financialStatus={inv.financial_status || (inv.balance_due_cents === 0 && inv.total_cents > 0 ? "paid" : (inv.paid_cents > 0 ? "partial" : "unpaid"))}
                    />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{relativeTime(inv.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
