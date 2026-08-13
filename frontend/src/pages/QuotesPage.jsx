import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
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
import { centsToDollarsString, relativeTime } from "@/lib/format";
import { toast } from "sonner";
import { Plus, FileText } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";

function NewQuoteDialog({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [jobName, setJobName] = useState("");
  const [notes, setNotes] = useState("");
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
      const { data } = await api.post("/quotes", { customer_id: customerId, job_name: jobName, notes });
      toast.success(`Quote Q-${data.number} created`);
      setOpen(false);
      setJobName(""); setNotes(""); setCustomerId("");
      onCreated?.(data);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button data-testid="quotes-create-button"><Plus className="size-4 mr-1" />New quote</Button></DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader><DialogTitle>New quote</DialogTitle><DialogDescription>Add line items after creating the quote.</DialogDescription></DialogHeader>
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
          <div className="grid gap-1.5"><Label>Project name*</Label><Input required value={jobName} onChange={(e) => setJobName(e.target.value)} data-testid="quote-job-name-input" /></div>
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
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("quote:write");
  const { data, isLoading } = useQuery({
    queryKey: ["quotes", status],
    queryFn: async () => (await api.get("/quotes", { params: { status: status === "all" ? undefined : status, limit: 100 } })).data,
  });
  const items = data?.items || [];

  return (
    <div className="space-y-4" data-testid="quotes-page">
      <PageHeader
        title="Quotes" subtitle="Create, price, send, and track customer quotes."
        actions={canWrite && <NewQuoteDialog onCreated={() => qc.invalidateQueries({ queryKey: ["quotes"] })} />}
      />
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
              <TableHead>Project</TableHead>
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
