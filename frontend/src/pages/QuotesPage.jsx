import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import CommandRibbon from "@/components/command-ribbon/CommandRibbon";
import SalesPageTabs from "@/components/sales/SalesPageTabs";
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
import MoneyInput from "@/components/forms/MoneyInput";
import { centsToDollarsString, relativeTime } from "@/lib/format";
import { toast } from "sonner";
import { Plus, FileText } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { buildQuotesRibbonGroups } from "@/lib/shopOperationRibbon";

function NewQuoteDialog({ onCreated, open: controlledOpen, onOpenChange, trigger }) {
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlledOpen ?? localOpen;
  const setOpen = onOpenChange ?? setLocalOpen;
  const [customerId, setCustomerId] = useState("");
  const [jobName, setJobName] = useState("");
  const [notes, setNotes] = useState("");
  const [totalCents, setTotalCents] = useState(0);
  const [busy, setBusy] = useState(false);

  const { data: cust } = useQuery({
    queryKey: ["customers", "all"],
    queryFn: async () => (await api.get("/customers", { params: { limit: 200 } })).data,
    enabled: open,
  });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/quotes", { customer_id: customerId, job_name: jobName, notes, total_cents: totalCents });
      toast.success(`Quote Q-${data.number} created`);
      setOpen(false);
      setJobName(""); setNotes(""); setTotalCents(0); setCustomerId("");
      onCreated?.(data);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger !== null && (
        <DialogTrigger asChild>
          {trigger || <Button data-testid="quotes-create-button"><Plus className="size-4 mr-1" />New quote</Button>}
        </DialogTrigger>
      )}
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader><DialogTitle>New quote</DialogTitle><DialogDescription>Enter a manually-typed price.</DialogDescription></DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>Customer*</Label>
            <Select value={customerId} onValueChange={setCustomerId}>
              <SelectTrigger data-testid="quote-customer-select"><SelectValue placeholder="Choose a customer" /></SelectTrigger>
              <SelectContent>
                {cust?.items?.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}{c.company ? ` · ${c.company}` : ""}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Job name*</Label><Input required value={jobName} onChange={(e) => setJobName(e.target.value)} data-testid="quote-job-name-input" /></div>
          <div className="grid gap-1.5"><Label>Total (USD)</Label><MoneyInput value={totalCents} onChange={setTotalCents} testId="quote-total-input" /></div>
          <div className="grid gap-1.5"><Label>Notes</Label><Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy || !customerId || !jobName} data-testid="quote-submit-button">{busy ? "Saving…" : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function QuotesPage() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("all");
  const [newQuoteOpen, setNewQuoteOpen] = useState(false);
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("quote:write");
  const handleNewQuoteOpenChange = (nextOpen) => {
    setNewQuoteOpen(nextOpen);
    if (!nextOpen) {
      window.requestAnimationFrame(() => {
        document.querySelector('[data-testid="ribbon-new-quote"]')?.focus();
      });
    }
  };
  const { data, isLoading } = useQuery({
    queryKey: ["quotes", status],
    queryFn: async () => (await api.get("/quotes", { params: { status: status === "all" ? undefined : status, limit: 100 } })).data,
  });
  const items = data?.items || [];
  const ribbonGroups = buildQuotesRibbonGroups({
    canWrite,
    onNewQuote: () => setNewQuoteOpen(true),
  });

  return (
    <div className="space-y-4" data-testid="quotes-page">
      <CommandRibbon groups={ribbonGroups} data-testid="quotes-command-ribbon" />
      <PageHeader
        breadcrumb="Shop Operations / Sales / Quotes"
        title="Quotes" subtitle="Manual pricing. No calculators."
        actions={canWrite && <NewQuoteDialog onCreated={() => qc.invalidateQueries({ queryKey: ["quotes"] })} />}
      />
      <NewQuoteDialog
        open={newQuoteOpen}
        onOpenChange={handleNewQuoteOpenChange}
        trigger={null}
        onCreated={() => qc.invalidateQueries({ queryKey: ["quotes"] })}
      />
      <SalesPageTabs />
      <div className="flex flex-wrap gap-2">
        {["all","draft","sent","approved","declined","converted"].map((s) => (
          <Button key={s} variant={status === s ? "default" : "outline"} size="sm" onClick={() => setStatus(s)} data-testid={`quotes-filter-${s}`}>
            <span className="capitalize">{s}</span>
          </Button>
        ))}
      </div>
      {isLoading ? <TableSkeleton /> : items.length === 0 ? (
        <EmptyState icon={FileText} title="No quotes" description="Create your first quote." action={canWrite ? <NewQuoteDialog onCreated={() => qc.invalidateQueries({ queryKey: ["quotes"] })} /> : null} />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="quotes-table">
            <TableHeader><TableRow>
              <TableHead>#</TableHead>
              <TableHead>Job</TableHead>
              <TableHead className="text-right">Total</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map((q) => (
                <TableRow key={q.id} className="hover:bg-muted/40" data-testid={`quote-row-${q.id}`}>
                  <TableCell className="mono text-xs">Q-{q.number}</TableCell>
                  <TableCell><Link className="font-medium hover:underline" to={`/quotes/${q.id}`}>{q.job_name}</Link></TableCell>
                  <TableCell className="text-right tabular-nums">{centsToDollarsString(q.total_cents)}</TableCell>
                  <TableCell><StatusPill kind="quote" value={q.status} /></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{relativeTime(q.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
