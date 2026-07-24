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
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import { LayoutList, Plus, Search, Users } from "lucide-react";
import { toast } from "sonner";
import { relativeTime } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";
import { buildCustomersRibbonGroups } from "@/lib/shopOperationRibbon";

function NewCustomerDialog({ onCreated, open: controlledOpen, onOpenChange, trigger }) {
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlledOpen ?? localOpen;
  const setOpen = onOpenChange ?? setLocalOpen;
  const [form, setForm] = useState({ name: "", company: "", email: "", phone: "", notes: "" });
  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => { if (!payload[k]) delete payload[k]; });
      const { data } = await api.post("/customers", payload);
      toast.success("Customer created");
      setOpen(false);
      setForm({ name: "", company: "", email: "", phone: "", notes: "" });
      onCreated?.(data);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger !== null && (
        <DialogTrigger asChild>
          {trigger || <Button data-testid="customers-create-button"><Plus className="size-4 mr-1" />New customer</Button>}
        </DialogTrigger>
      )}
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>New customer</DialogTitle>
          <DialogDescription>Add a customer to your shop.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5"><Label>Name*</Label><Input required value={form.name} onChange={upd("name")} data-testid="customer-name-input" /></div>
          <div className="grid gap-1.5"><Label>Company</Label><Input value={form.company} onChange={upd("company")} data-testid="customer-company-input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Email</Label><Input type="email" value={form.email} onChange={upd("email")} data-testid="customer-email-input" /></div>
            <div className="grid gap-1.5"><Label>Phone</Label><Input value={form.phone} onChange={upd("phone")} data-testid="customer-phone-input" /></div>
          </div>
          <div className="grid gap-1.5"><Label>Notes</Label><Textarea rows={3} value={form.notes} onChange={upd("notes")} /></div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy} data-testid="customer-submit-button">{busy ? "Saving..." : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function CustomersPage() {
  const [q, setQ] = useState("");
  const [newCustomerOpen, setNewCustomerOpen] = useState(false);
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("customer:write");
  const handleNewCustomerOpenChange = (nextOpen) => {
    setNewCustomerOpen(nextOpen);
    if (!nextOpen) {
      window.requestAnimationFrame(() => {
        document.querySelector('[data-testid="ribbon-new-customer"]')?.focus();
      });
    }
  };
  const { data, isLoading, error } = useQuery({
    queryKey: ["customers", q],
    queryFn: async () => (await api.get("/customers", { params: { search: q || undefined, limit: 100 } })).data,
  });
  const items = data?.items || [];
  const ribbonGroups = buildCustomersRibbonGroups({
    canWrite,
    onNewCustomer: () => setNewCustomerOpen(true),
  });

  return (
    <div className="space-y-4" data-testid="customers-page">
      <CommandRibbon groups={ribbonGroups} data-testid="customers-command-ribbon" />
      <PageHeader breadcrumb="Shop Operations / Customers" title="Customers" subtitle="Everyone you've done work for." />
      <NewCustomerDialog
        open={newCustomerOpen}
        onOpenChange={handleNewCustomerOpenChange}
        trigger={null}
        onCreated={() => qc.invalidateQueries({ queryKey: ["customers"] })}
      />
      <div className="flex flex-wrap items-center gap-1 rounded-lg border bg-card p-1" data-testid="customers-page-tabs" aria-label="Customer tabs">
        <button
          type="button"
          data-testid="customers-tab-all"
          aria-current="page"
          className="h-8 rounded-md bg-slate-950 px-3 text-sm font-medium text-white shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          All Customers
        </button>
      </div>
      <div className="flex flex-col gap-2 rounded-lg border bg-card p-3 md:flex-row md:items-center md:justify-between" data-testid="customers-search-views-filters">
        <div className="relative w-full md:max-w-md">
          <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, company, or email" className="pl-9" data-testid="customers-search-input" />
        </div>
        <div className="inline-flex h-9 w-fit items-center gap-2 rounded-md border bg-background px-3 text-sm text-muted-foreground" data-testid="customers-table-view">
          <LayoutList className="size-4" aria-hidden="true" />
          Table
        </div>
      </div>
      {isLoading ? <TableSkeleton /> : error ? (
        <EmptyState title="Couldn't load customers" description="Please try again." />
      ) : items.length === 0 ? (
        <EmptyState icon={Users} title={q ? "No matches" : "No customers yet"} description={q ? "Try a different search." : "Create your first customer to get started."} action={canWrite && !q ? <NewCustomerDialog onCreated={() => qc.invalidateQueries({ queryKey: ["customers"] })} /> : null} />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="customers-table">
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead>Added</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((c) => (
                <TableRow key={c.id} className="hover:bg-muted/40" data-testid={`customer-row-${c.id}`}>
                  <TableCell><Link className="font-medium hover:underline" to={`/customers/${c.id}`}>{c.name}</Link></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{c.company || "-"}</TableCell>
                  <TableCell className="text-sm">{c.email || "-"}</TableCell>
                  <TableCell className="text-sm">{c.phone || "-"}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{relativeTime(c.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
