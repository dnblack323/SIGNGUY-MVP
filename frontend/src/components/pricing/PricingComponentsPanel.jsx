import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";
import { toast } from "sonner";
import { Plus, ArchiveRestore, Archive } from "lucide-react";

const CHARGE_TYPES = ["setup_fee", "design_fee", "file_cleanup", "permit_fee", "outsourced_service",
  "pass_through", "install_minimum", "rush_charge", "personalization_fee", "decoration_fee", "relaunch_fee", "other"];

const emptyForm = { key: "", name: "", charge_type: "setup_fee", amount: "", percent: "", notes: "" };

/** EC9 Phase 9D — non-inventory Pricing Components (fees/charges) manager. */
export default function PricingComponentsPanel() {
  const qc = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState(null); // null=closed, {} = new, {...} = edit
  const [form, setForm] = useState(emptyForm);

  const { data, isLoading } = useQuery({
    queryKey: ["pricing-components-panel", showArchived],
    queryFn: async () => (await api.get("/pricing/components", { params: { active: !showArchived } })).data,
  });

  const openNew = () => { setForm(emptyForm); setEditing({}); };
  const openEdit = (c) => { setForm({ key: c.key, name: c.name, charge_type: c.charge_type, amount: c.amount ?? "", percent: c.percent ?? "", notes: c.notes || "" }); setEditing(c); };

  const save = useMutation({
    mutationFn: async () => {
      const payload = { name: form.name, charge_type: form.charge_type,
        amount: form.amount === "" ? null : Number(form.amount), percent: form.percent === "" ? null : Number(form.percent), notes: form.notes || null };
      if (editing?.id) return (await api.patch(`/pricing/components/${editing.id}`, payload)).data;
      return (await api.post("/pricing/components", { ...payload, key: form.key })).data;
    },
    onSuccess: () => { toast.success("Pricing component saved"); qc.invalidateQueries({ queryKey: ["pricing-components-panel"] }); qc.invalidateQueries({ queryKey: ["pricing-components-active"] }); setEditing(null); },
    onError: (e) => toast.error(extractError(e)),
  });

  const archiveToggle = useMutation({
    mutationFn: async ({ id, active }) => (await api.patch(`/pricing/components/${id}`, { active })).data,
    onSuccess: () => { toast.success("Updated"); qc.invalidateQueries({ queryKey: ["pricing-components-panel"] }); },
    onError: (e) => toast.error(extractError(e)),
  });

  const items = data?.items || [];

  return (
    <Card data-testid="pricing-components-panel">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-base">Pricing Components (fees & charges)</CardTitle>
          <div className="flex items-center gap-2">
            <Button size="sm" variant={showArchived ? "secondary" : "outline"} onClick={() => setShowArchived((v) => !v)} data-testid="components-toggle-archived">
              {showArchived ? "Showing archived" : "Show archived"}
            </Button>
            <Button size="sm" onClick={openNew} data-testid="components-add-new-button"><Plus className="size-4 mr-1" />Add Component</Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="text-sm text-muted-foreground">Loading…</div> : (
          <Table>
            <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Type</TableHead><TableHead>Amount</TableHead><TableHead>%</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
            <TableBody>
              {items.map((c) => (
                <TableRow key={c.id} data-testid={`component-row-${c.id}`}>
                  <TableCell>{c.name}{!c.active && <Badge variant="secondary" className="ml-2 text-[10px]">Archived</Badge>}</TableCell>
                  <TableCell><Badge variant="secondary" className="capitalize">{c.charge_type.replace(/_/g, " ")}</Badge></TableCell>
                  <TableCell className="tabular-nums">{c.amount != null ? `$${c.amount.toFixed(2)}` : "—"}</TableCell>
                  <TableCell className="tabular-nums">{c.percent != null ? `${c.percent}%` : "—"}</TableCell>
                  <TableCell className="text-right space-x-1">
                    <Button size="sm" variant="outline" onClick={() => openEdit(c)} data-testid={`component-edit-${c.id}`}>Edit</Button>
                    <Button size="sm" variant="ghost" onClick={() => archiveToggle.mutate({ id: c.id, active: !c.active })} data-testid={`component-archive-toggle-${c.id}`}>
                      {c.active ? <Archive className="size-3.5" /> : <ArchiveRestore className="size-3.5" />}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-6">No pricing components yet.</TableCell></TableRow>}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-md" data-testid="component-form-dialog">
          <DialogHeader><DialogTitle>{editing?.id ? "Edit" : "New"} Pricing Component</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {!editing?.id && (
              <div className="grid gap-1.5"><Label className="text-xs">Key (unique)</Label><Input value={form.key} onChange={(e) => setForm((f) => ({ ...f, key: e.target.value }))} data-testid="component-form-key" /></div>
            )}
            <div className="grid gap-1.5"><Label className="text-xs">Name</Label><Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="component-form-name" /></div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Charge type</Label>
              <Select value={form.charge_type} onValueChange={(v) => setForm((f) => ({ ...f, charge_type: v }))}>
                <SelectTrigger data-testid="component-form-charge-type"><SelectValue /></SelectTrigger>
                <SelectContent>{CHARGE_TYPES.map((t) => <SelectItem key={t} value={t}>{t.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5"><Label className="text-xs">Flat amount ($)</Label><Input type="number" step="0.01" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} data-testid="component-form-amount" /></div>
              <div className="grid gap-1.5"><Label className="text-xs">Percent (%)</Label><Input type="number" step="0.1" value={form.percent} onChange={(e) => setForm((f) => ({ ...f, percent: e.target.value }))} data-testid="component-form-percent" /></div>
            </div>
            <div className="grid gap-1.5"><Label className="text-xs">Notes</Label><Input value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} data-testid="component-form-notes" /></div>
          </div>
          <DialogFooter><Button onClick={() => save.mutate()} disabled={!form.name || (!editing?.id && !form.key) || save.isPending} data-testid="component-form-save-button">Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
