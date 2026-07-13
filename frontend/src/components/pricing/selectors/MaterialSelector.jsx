import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Plus } from "lucide-react";

const MATERIAL_CATEGORIES = ["vinyl", "laminate", "application_tape", "printable_media", "substrate",
  "banner", "ink", "hardware", "apparel", "heat_transfer", "packaging", "equipment", "supplies", "other"];

/**
 * EC9 Phase 9D — reusable canonical Material selector (with an inline "Add
 * New Material" shortcut). Shared component prepared for later Order Item /
 * category-calculator integration (Phase 9E/9F) — only mounted in the
 * Pricing Foundation area for now.
 */
export default function MaterialSelector({ value, onChange, category, testIdPrefix = "material-selector" }) {
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ name: "", category: category || "other", current_cost_cents: "" });

  const { data } = useQuery({
    queryKey: ["materials-active", category || "all"],
    queryFn: async () => (await api.get("/materials", { params: { active: true, ...(category ? { category } : {}) } })).data,
  });
  const items = data?.items || [];

  const createMaterial = useMutation({
    mutationFn: async () => (await api.post("/materials", {
      name: form.name, category: form.category,
      current_cost_cents: Math.round(Number(form.current_cost_cents || 0) * 100),
    })).data,
    onSuccess: (mat) => {
      toast.success(`Material "${mat.name}" created`);
      qc.invalidateQueries({ queryKey: ["materials-active"] });
      onChange?.(mat.id, mat);
      setAddOpen(false);
      setForm({ name: "", category: category || "other", current_cost_cents: "" });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  return (
    <div className="flex items-center gap-2">
      <Select value={value || ""} onValueChange={(v) => onChange?.(v, items.find((m) => m.id === v))}>
        <SelectTrigger data-testid={`${testIdPrefix}-select`}><SelectValue placeholder="Select a material…" /></SelectTrigger>
        <SelectContent>
          {items.map((m) => <SelectItem key={m.id} value={m.id}>{m.name} ({m.category})</SelectItem>)}
        </SelectContent>
      </Select>
      <Button type="button" variant="outline" size="icon" onClick={() => setAddOpen(true)} data-testid={`${testIdPrefix}-add-new-button`}>
        <Plus className="size-4" />
      </Button>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-sm" data-testid={`${testIdPrefix}-add-new-dialog`}>
          <DialogHeader><DialogTitle>Add New Material</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid gap-1.5">
              <Label>Name</Label>
              <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid={`${testIdPrefix}-add-name`} />
            </div>
            <div className="grid gap-1.5">
              <Label>Category</Label>
              <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}>
                <SelectTrigger data-testid={`${testIdPrefix}-add-category`}><SelectValue /></SelectTrigger>
                <SelectContent>{MATERIAL_CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c.replace("_", " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>Current cost ($)</Label>
              <Input type="number" step="0.01" min="0" value={form.current_cost_cents} onChange={(e) => setForm((f) => ({ ...f, current_cost_cents: e.target.value }))} data-testid={`${testIdPrefix}-add-cost`} />
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => createMaterial.mutate()} disabled={!form.name || createMaterial.isPending} data-testid={`${testIdPrefix}-add-save-button`}>Create material</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
