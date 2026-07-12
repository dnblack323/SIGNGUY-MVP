import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { toast } from "sonner";
import { useAuth } from "@/auth/AuthContext";
import { Plus, ShieldAlert, Wrench } from "lucide-react";

const CATEGORIES = ["printer", "laminator", "plotter", "cutter", "heat_press", "embroidery_machine", "lift", "vehicle", "specialty_tool", "other"];
const STATUSES = ["active", "inactive", "maintenance", "retired", "archived"];
const ACCESS_POLICIES = [
  { value: "no_required", label: "No certification required" },
  { value: "recommended", label: "Recommended (never blocks)" },
  { value: "required_override_allowed", label: "Required — override allowed" },
  { value: "required_no_override", label: "Required — no override (hard block)" },
];

function NewEquipmentDialog({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", category: "other", access_policy: "no_required", safety_sensitive: false, location: "", status: "active" });
  const [busy, setBusy] = useState(false);
  const upd = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/equipment", form);
      toast.success("Equipment added");
      setOpen(false);
      setForm({ name: "", category: "other", access_policy: "no_required", safety_sensitive: false, location: "", status: "active" });
      onCreated?.(data);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button data-testid="equipment-create-button"><Plus className="size-4 mr-1" />New equipment</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>New Equipment</DialogTitle>
          <DialogDescription>Assets that can gate Training, Certification and Work Order assignment.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5"><Label>Name*</Label><Input required value={form.name} onChange={(e) => upd("name")(e.target.value)} data-testid="equipment-name-input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Category</Label>
              <Select value={form.category} onValueChange={upd("category")}>
                <SelectTrigger data-testid="equipment-category-select"><SelectValue /></SelectTrigger>
                <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c} className="capitalize">{c.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5"><Label>Location</Label><Input value={form.location} onChange={(e) => upd("location")(e.target.value)} data-testid="equipment-location-input" /></div>
          </div>
          <div className="grid gap-1.5">
            <Label>Certification / access policy</Label>
            <Select value={form.access_policy} onValueChange={upd("access_policy")}>
              <SelectTrigger data-testid="equipment-access-policy-select"><SelectValue /></SelectTrigger>
              <SelectContent>{ACCESS_POLICIES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">This is the sole rule used to block or warn on Work Order assignment.</p>
          </div>
          <div className="flex items-center justify-between rounded-md border px-3 py-2">
            <Label className="flex items-center gap-1.5"><ShieldAlert className="size-3.5" />Safety-sensitive</Label>
            <Switch checked={form.safety_sensitive} onCheckedChange={upd("safety_sensitive")} data-testid="equipment-safety-switch" />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy || !form.name.trim()} data-testid="equipment-submit-button">{busy ? "Saving…" : "Create"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function EquipmentPage() {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canManage = hasPerm("equipment:manage");
  const [status, setStatus] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["equipment", status],
    queryFn: async () => (await api.get("/equipment", { params: { status: status || undefined } })).data,
  });
  const items = data?.items || [];

  return (
    <div className="space-y-4" data-testid="equipment-page">
      <PageHeader
        title="Equipment"
        subtitle="Machines and safety-sensitive assets that gate Training and Work Order assignment."
        actions={canManage && <NewEquipmentDialog onCreated={() => qc.invalidateQueries({ queryKey: ["equipment"] })} />}
      />
      <div className="grid gap-1.5 max-w-[220px]">
        <Select value={status || "__all__"} onValueChange={(v) => setStatus(v === "__all__" ? "" : v)}>
          <SelectTrigger data-testid="equipment-status-filter"><SelectValue placeholder="All statuses" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All statuses</SelectItem>
            {STATUSES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      {isLoading ? <TableSkeleton /> : error ? (
        <EmptyState title="Couldn't load Equipment" description="Please try again." />
      ) : items.length === 0 ? (
        <EmptyState icon={Wrench} title="No Equipment yet" description="Add your first machine or safety-sensitive asset to get started." action={canManage ? <NewEquipmentDialog onCreated={() => qc.invalidateQueries({ queryKey: ["equipment"] })} /> : null} />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="equipment-table">
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead><TableHead>Category</TableHead><TableHead>Access policy</TableHead>
                <TableHead>Safety</TableHead><TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((eq) => (
                <TableRow key={eq.id} className="hover:bg-muted/40" data-testid={`equipment-row-${eq.id}`}>
                  <TableCell><Link className="font-medium hover:underline" to={`/team/equipment/${eq.id}`}>{eq.name}</Link></TableCell>
                  <TableCell className="text-sm text-muted-foreground capitalize">{eq.category.replace(/_/g, " ")}</TableCell>
                  <TableCell><StatusPill kind="access_policy" value={eq.access_policy} /></TableCell>
                  <TableCell>{eq.safety_sensitive ? <ShieldAlert className="size-4 text-amber-600" data-testid={`equipment-safety-icon-${eq.id}`} /> : <span className="text-muted-foreground text-sm">—</span>}</TableCell>
                  <TableCell><StatusPill kind="equipment_status" value={eq.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
