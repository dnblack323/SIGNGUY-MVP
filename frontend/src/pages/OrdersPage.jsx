import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { toast } from "sonner";
import { ShoppingBag } from "lucide-react";
import { relativeTime } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";

const ORDER_STATUS_OPTIONS = new Set(["all", "draft", "confirmed", "ready", "in_production", "completed", "cancelled"]);

function NewOrderDialog({ onCreated, open: controlledOpen, onOpenChange, trigger = null }) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false);
  const open = controlledOpen ?? uncontrolledOpen;
  const setOpen = onOpenChange ?? setUncontrolledOpen;
  const [customerId, setCustomerId] = useState("");
  const [jobName, setJobName] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const { data: cust } = useQuery({ queryKey: ["customers", "all-orders"], queryFn: async () => (await api.get("/customers", { params: { limit: 200 } })).data, enabled: open });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/orders", { customer_id: customerId, job_name: jobName, notes });
      toast.success(`Order O-${data.number} created`);
      setOpen(false); setJobName(""); setNotes(""); setCustomerId("");
      onCreated?.(data);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>}
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader><DialogTitle>New order</DialogTitle><DialogDescription>Create an order directly (not from a quote).</DialogDescription></DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>Customer*</Label>
            <Select value={customerId} onValueChange={setCustomerId}>
              <SelectTrigger data-testid="order-customer-select"><SelectValue placeholder="Choose a customer" /></SelectTrigger>
              <SelectContent>{cust?.items?.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Project name*</Label><Input required value={jobName} onChange={(e) => setJobName(e.target.value)} data-testid="order-job-name-input" /></div>
          <div className="grid gap-1.5"><Label>Notes</Label><Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)} type="button">Cancel</Button>
            <Button type="submit" disabled={busy || !customerId || !jobName} data-testid="order-submit-button">{busy ? "Saving…" : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function OrdersPage() {
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const statusParam = searchParams.get("status");
  const status = ORDER_STATUS_OPTIONS.has(statusParam) ? statusParam : "all";
  const newOrderRequested = searchParams.get("new") === "1";
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("order:write");
  const { data, isLoading } = useQuery({
    queryKey: ["orders", status],
    queryFn: async () => (await api.get("/orders", { params: { status: status === "all" ? undefined : status, limit: 100 } })).data,
  });
  const items = data?.items || [];
  const countLabel = isLoading ? "Loading orders" : `${items.length} ${items.length === 1 ? "order" : "orders"}`;

  useEffect(() => {
    if (!newOrderRequested || canWrite) return;
    const next = new URLSearchParams(searchParams);
    next.delete("new");
    setSearchParams(next, { replace: true });
  }, [canWrite, newOrderRequested, searchParams, setSearchParams]);

  function closeNewOrderDialog(nextOpen) {
    if (nextOpen) return;
    const next = new URLSearchParams(searchParams);
    next.delete("new");
    setSearchParams(next, { replace: true });
  }

  return (
    <div className="space-y-2" data-testid="orders-page" data-active-order-view={status}>
      {canWrite && (
        <NewOrderDialog
          open={newOrderRequested}
          onOpenChange={closeNewOrderDialog}
          onCreated={() => qc.invalidateQueries({ queryKey: ["orders"] })}
        />
      )}
      <div className="flex h-10 items-center justify-between gap-3" data-testid="orders-table-utility-row">
        <p className="text-sm text-slate-500" data-testid="orders-result-count">{countLabel}</p>
        <div className="min-w-0 shrink-0" aria-hidden="true" />
      </div>
      {isLoading ? <TableSkeleton /> : items.length === 0 ? (
        <EmptyState icon={ShoppingBag} title="No orders yet" description="Convert a quote or use New Order from the ribbon." />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="orders-table">
            <TableHeader><TableRow>
              <TableHead>#</TableHead>
              <TableHead>Project</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map((o) => (
                <TableRow key={o.id} className="hover:bg-muted/40" data-testid={`order-row-${o.id}`}>
                  <TableCell className="mono text-xs">O-{o.number}</TableCell>
                  <TableCell><Link className="font-medium hover:underline" to={`/orders/${o.id}`}>{o.job_name}</Link></TableCell>
                  <TableCell><StatusPill kind="order" value={o.status} /></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{relativeTime(o.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
