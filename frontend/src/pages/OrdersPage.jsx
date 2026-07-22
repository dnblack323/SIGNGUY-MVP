import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import CommandRibbon from "@/components/command-ribbon/CommandRibbon";
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
import { Plus, ShoppingBag } from "lucide-react";
import { relativeTime } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";
import { buildOrdersRibbonGroups, ORDER_SOURCE_FILTER_FALLBACK } from "@/lib/shopOperationRibbon";

function NewOrderDialog({ onCreated, open: controlledOpen, onOpenChange, trigger }) {
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlledOpen ?? localOpen;
  const setOpen = onOpenChange ?? setLocalOpen;
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
      {trigger !== null && (
        <DialogTrigger asChild>
          {trigger || <Button data-testid="orders-create-button"><Plus className="size-4 mr-1" />New order</Button>}
        </DialogTrigger>
      )}
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
          <div className="grid gap-1.5"><Label>Job name*</Label><Input required value={jobName} onChange={(e) => setJobName(e.target.value)} data-testid="order-job-name-input" /></div>
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
  const [status, setStatus] = useState("all");
  const [source, setSource] = useState("all");
  const [newOrderOpen, setNewOrderOpen] = useState(false);
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("order:write");
  const handleNewOrderOpenChange = (nextOpen) => {
    setNewOrderOpen(nextOpen);
    if (!nextOpen) {
      window.requestAnimationFrame(() => {
        document.querySelector('[data-testid="ribbon-new-order"]')?.focus();
      });
    }
  };
  const sourceFilters = useQuery({
    queryKey: ["orders", "source-filters"],
    queryFn: async () => (await api.get("/orders/source-filters")).data,
  });
  const { data, isLoading } = useQuery({
    queryKey: ["orders", status, source],
    queryFn: async () => (await api.get("/orders", {
      params: {
        status: status === "all" ? undefined : status,
        order_source: source === "all" ? undefined : source,
        limit: 100,
      },
    })).data,
  });
  const items = data?.items || [];
  const ribbonGroups = buildOrdersRibbonGroups({
    canWrite,
    onNewOrder: () => setNewOrderOpen(true),
    status,
    setStatus,
    source,
    setSource,
    sourceFilters: sourceFilters.data?.visible_sources || ORDER_SOURCE_FILTER_FALLBACK,
  });

  return (
    <div className="space-y-4" data-testid="orders-page">
      <PageHeader title="Orders" subtitle="Everything in flight." />
      <CommandRibbon groups={ribbonGroups} data-testid="orders-command-ribbon" />
      <NewOrderDialog
        open={newOrderOpen}
        onOpenChange={handleNewOrderOpenChange}
        trigger={null}
        onCreated={() => qc.invalidateQueries({ queryKey: ["orders"] })}
      />
      {isLoading ? <TableSkeleton /> : items.length === 0 ? (
        <EmptyState icon={ShoppingBag} title="No orders yet" description="Convert a quote or create an order directly." action={canWrite ? <NewOrderDialog onCreated={() => qc.invalidateQueries({ queryKey: ["orders"] })} /> : null} />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="orders-table">
            <TableHeader><TableRow>
              <TableHead>#</TableHead>
              <TableHead>Job</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Created</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map((o) => (
                <TableRow key={o.id} className="hover:bg-muted/40" data-testid={`order-row-${o.id}`}>
                  <TableCell className="mono text-xs">O-{o.number}</TableCell>
                  <TableCell><Link className="font-medium hover:underline" to={`/orders/${o.id}`}>{o.job_name}</Link></TableCell>
                  <TableCell><StatusPill kind="order" value={o.status} /></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{String(o.order_source || "legacy_unknown").replace("legacy_unknown", "Legacy / Unknown").replace("wrap_lab", "Wrap Lab").replace("webstore", "Webstore").replace("manual", "Manual").replace("quote", "Quote")}</TableCell>
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
