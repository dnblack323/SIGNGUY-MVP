import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { Plus, Search, Users } from "lucide-react";
import { toast } from "sonner";
import { centsToDollarsString } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";

function NewEmployeeDialog({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", phone: "", role_label: "", hourly_rate_cents: 1500, notes: "" });
  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = { ...form, hourly_rate_cents: Math.round(Number(form.hourly_rate_cents) || 0) };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") delete payload[k]; });
      const { data } = await api.post("/employees", payload);
      toast.success("Employee added");
      setOpen(false);
      setForm({ name: "", email: "", phone: "", role_label: "", hourly_rate_cents: 1500, notes: "" });
      onCreated?.(data);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button data-testid="employees-create-button"><Plus className="size-4 mr-1" />New employee</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>New employee</DialogTitle>
          <DialogDescription>Add someone to your team.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5"><Label>Name*</Label><Input required value={form.name} onChange={upd("name")} data-testid="employee-name-input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Email</Label><Input type="email" value={form.email} onChange={upd("email")} data-testid="employee-email-input" /></div>
            <div className="grid gap-1.5"><Label>Phone</Label><Input value={form.phone} onChange={upd("phone")} data-testid="employee-phone-input" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Role / title</Label><Input value={form.role_label} onChange={upd("role_label")} placeholder="e.g. Install Tech" data-testid="employee-role-input" /></div>
            <div className="grid gap-1.5"><Label>Hourly rate (cents)*</Label><Input type="number" min="0" required value={form.hourly_rate_cents} onChange={upd("hourly_rate_cents")} data-testid="employee-rate-input" /></div>
          </div>
          <div className="grid gap-1.5"><Label>Notes</Label><Textarea rows={2} value={form.notes} onChange={upd("notes")} data-testid="employee-notes-input" /></div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy} data-testid="employee-submit-button">{busy ? "Saving…" : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function EmployeesPage() {
  const [q, setQ] = useState("");
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canManage = hasPerm("employee:manage");
  const { data, isLoading, error } = useQuery({
    queryKey: ["employees", q],
    queryFn: async () => (await api.get("/employees", { params: { q: q || undefined } })).data,
  });
  const items = data?.items || [];

  return (
    <div className="space-y-4" data-testid="employees-page">
      <PageHeader title="Employees" subtitle="Your team, one place." actions={canManage && <NewEmployeeDialog onCreated={() => qc.invalidateQueries({ queryKey: ["employees"] })} />} />
      <div className="relative w-full max-w-md">
        <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name or email" className="pl-9" data-testid="employees-search-input" />
      </div>
      {isLoading ? <TableSkeleton /> : error ? (
        <EmptyState title="Couldn’t load employees" description="Please try again." />
      ) : items.length === 0 ? (
        <EmptyState icon={Users} title={q ? "No matches" : "No employees yet"} description={q ? "Try a different search." : "Add your first employee to get started."} action={canManage && !q ? <NewEmployeeDialog onCreated={() => qc.invalidateQueries({ queryKey: ["employees"] })} /> : null} />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="employees-table">
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead>Rate</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((emp) => (
                <TableRow key={emp.id} className="hover:bg-muted/40" data-testid={`employee-row-${emp.id}`}>
                  <TableCell><Link className="font-medium hover:underline" to={`/team/employees/${emp.id}`}>{emp.name}</Link></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{emp.role_label || "—"}</TableCell>
                  <TableCell className="text-sm">{emp.email || emp.phone || "—"}</TableCell>
                  <TableCell className="text-sm tabular-nums">{centsToDollarsString(emp.hourly_rate_cents)}/hr</TableCell>
                  <TableCell><StatusPill kind="employee" value={emp.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
