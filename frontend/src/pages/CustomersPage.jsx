import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import { ArchiveRestore, GitMerge, Plus, Search, Users } from "lucide-react";
import { toast } from "sonner";
import { relativeTime } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";

function NewCustomerDialog({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    company: "",
    customer_type: "business",
    lifecycle_status: "active",
    email: "",
    phone: "",
    address_line1: "",
    city: "",
    state: "",
    postal_code: "",
    notes: "",
  });
  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => { if (!payload[k]) delete payload[k]; });
      payload.contacts = [{
        name: payload.name,
        email: payload.email,
        phone: payload.phone,
        role: "primary",
        is_primary: true,
      }].filter((item) => item.name || item.email || item.phone);
      payload.addresses = [{
        label: "Primary address",
        line1: payload.address_line1,
        city: payload.city,
        state: payload.state,
        postal_code: payload.postal_code,
        purposes: ["billing", "shipping"],
        is_default: true,
      }].filter((item) => item.line1 || item.city || item.state || item.postal_code);
      const { data } = await api.post("/customers", payload);
      toast.success("Customer created");
      setOpen(false);
      setForm({ name: "", company: "", customer_type: "business", lifecycle_status: "active", email: "", phone: "", address_line1: "", city: "", state: "", postal_code: "", notes: "" });
      onCreated?.(data);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button data-testid="customers-create-button"><Plus className="size-4 mr-1" />New customer</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>New customer</DialogTitle>
          <DialogDescription>Add a customer to your shop.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5"><Label>Name*</Label><Input required value={form.name} onChange={upd("name")} data-testid="customer-name-input" /></div>
          <div className="grid gap-1.5"><Label>Company</Label><Input value={form.company} onChange={upd("company")} data-testid="customer-company-input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>Type</Label>
              <Select value={form.customer_type} onValueChange={(value) => setForm((f) => ({ ...f, customer_type: value }))}>
                <SelectTrigger data-testid="customer-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="business">Business</SelectItem>
                  <SelectItem value="individual">Individual</SelectItem>
                  <SelectItem value="organization">Organization</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>Status</Label>
              <Select value={form.lifecycle_status} onValueChange={(value) => setForm((f) => ({ ...f, lifecycle_status: value }))}>
                <SelectTrigger data-testid="customer-lifecycle-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="lead">Lead</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Email</Label><Input type="email" value={form.email} onChange={upd("email")} data-testid="customer-email-input" /></div>
            <div className="grid gap-1.5"><Label>Phone</Label><Input value={form.phone} onChange={upd("phone")} data-testid="customer-phone-input" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Address</Label><Input value={form.address_line1} onChange={upd("address_line1")} data-testid="customer-address-input" /></div>
            <div className="grid gap-1.5"><Label>City</Label><Input value={form.city} onChange={upd("city")} /></div>
            <div className="grid gap-1.5"><Label>State</Label><Input value={form.state} onChange={upd("state")} /></div>
            <div className="grid gap-1.5"><Label>Postal code</Label><Input value={form.postal_code} onChange={upd("postal_code")} /></div>
          </div>
          <div className="grid gap-1.5"><Label>Notes</Label><Textarea rows={3} value={form.notes} onChange={upd("notes")} /></div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy} data-testid="customer-submit-button">{busy ? "Saving…" : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DuplicateReviewDialog({ customer, onMerged }) {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["customer-duplicates", customer.id],
    queryFn: async () => (await api.get("/customers/duplicates", { params: { customer_id: customer.id } })).data,
    enabled: open,
  });
  const merge = useMutation({
    mutationFn: async (candidate) => (await api.post("/customers/merge", {
      source_customer_id: candidate.customer.id,
      surviving_customer_id: customer.id,
      confirmation: "MERGE",
    })).data,
    onSuccess: () => {
      toast.success("Customer records merged");
      qc.invalidateQueries({ queryKey: ["customers"] });
      setOpen(false);
      onMerged?.();
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const candidates = data?.items || [];
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" data-testid={`customer-duplicates-${customer.id}`}><GitMerge className="size-4 mr-1" />Duplicates</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[640px]">
        <DialogHeader>
          <DialogTitle>Duplicate review</DialogTitle>
          <DialogDescription>Select a duplicate to merge into {customer.name}. The merged record is archived, not deleted.</DialogDescription>
        </DialogHeader>
        {isLoading ? <div className="text-sm text-muted-foreground">Checking duplicates…</div> : candidates.length === 0 ? (
          <div className="text-sm text-muted-foreground">No duplicate candidates found.</div>
        ) : (
          <div className="space-y-3">
            {candidates.map((candidate) => (
              <div key={candidate.customer.id} className="rounded-md border p-3 flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">{candidate.customer.name}</div>
                  <div className="text-sm text-muted-foreground">{candidate.customer.company || candidate.customer.email || "Customer"}</div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {candidate.match_reasons.map((reason) => <Badge key={reason} variant="outline">{reason}</Badge>)}
                  </div>
                </div>
                <Button size="sm" onClick={() => merge.mutate(candidate)} disabled={merge.isPending} data-testid={`customer-merge-${candidate.customer.id}`}>Merge into survivor</Button>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function CustomersPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("active");
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("customer:write");
  const { data, isLoading, error } = useQuery({
    queryKey: ["customers", q, status],
    queryFn: async () => (await api.get("/customers", { params: { search: q || undefined, status, limit: 100 } })).data,
  });
  const items = data?.items || [];
  const restore = useMutation({
    mutationFn: async (customerId) => (await api.post(`/customers/${customerId}/restore`, {})).data,
    onSuccess: () => {
      toast.success("Customer restored");
      qc.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (error) => toast.error(extractError(error)),
  });

  return (
    <div className="space-y-4" data-testid="customers-page">
      <PageHeader title="Customers" subtitle="Everyone you’ve done work for." actions={canWrite && <NewCustomerDialog onCreated={() => qc.invalidateQueries({ queryKey: ["customers"] })} />} />
      <div className="flex items-center gap-2">
        <div className="relative w-full max-w-md">
          <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, company, or email" className="pl-9" data-testid="customers-search-input" />
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-[160px]" data-testid="customers-status-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="archived">Archived</SelectItem>
            <SelectItem value="all">All</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {isLoading ? <TableSkeleton /> : error ? (
        <EmptyState title="Couldn’t load customers" description="Please try again." />
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
                <TableHead>Status</TableHead>
                <TableHead>Added</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((c) => (
                <TableRow key={c.id} className="hover:bg-muted/40" data-testid={`customer-row-${c.id}`}>
                  <TableCell><Link className="font-medium hover:underline" to={`/customers/${c.id}`}>{c.name}</Link></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{c.company || "—"}</TableCell>
                  <TableCell className="text-sm">{c.email || "—"}</TableCell>
                  <TableCell className="text-sm">{c.phone || "—"}</TableCell>
                  <TableCell className="text-sm">
                    <Badge variant={c.archived ? "secondary" : "outline"}>{c.lifecycle_status || (c.archived ? "archived" : "active")}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{relativeTime(c.created_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      {canWrite && !c.archived && !c.merged_into && <DuplicateReviewDialog customer={c} />}
                      {canWrite && c.archived && !c.merged_into && (
                        <Button variant="outline" size="sm" onClick={() => restore.mutate(c.id)} disabled={restore.isPending} data-testid={`customer-restore-${c.id}`}>
                          <ArchiveRestore className="size-4 mr-1" />Restore
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
