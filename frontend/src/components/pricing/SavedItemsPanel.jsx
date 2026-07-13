import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import PricingComponentSelector from "@/components/pricing/selectors/PricingComponentSelector";
import { toast } from "sonner";
import { Plus, ArchiveRestore, Archive, Copy, X } from "lucide-react";

const PRICING_METHODS = ["tier_pricing", "per_piece", "flat_fee", "manual"];

function emptyForm(category) {
  return { name: "", category: category || "banners", material_refs: [], pricing_component_refs: [],
    quantity_tiers: [], default_pricing_method: "manual", default_notes: "", quick_select: false, active: true };
}

function QuantityTiersEditor({ tiers, onChange }) {
  const update = (i, key, v) => onChange(tiers.map((t, idx) => idx === i ? { ...t, [key]: v } : t));
  const remove = (i) => onChange(tiers.filter((_, idx) => idx !== i));
  const add = () => onChange([...tiers, { quantity: "", price: "" }]);
  return (
    <div className="space-y-2">
      {tiers.map((t, i) => (
        <div key={i} className="flex items-center gap-2" data-testid={`saved-item-tier-row-${i}`}>
          <Input type="number" placeholder="Qty" className="w-28" value={t.quantity} onChange={(e) => update(i, "quantity", e.target.value)} data-testid={`saved-item-tier-qty-${i}`} />
          <Input type="number" step="0.01" placeholder="Price $" className="w-28" value={t.price} onChange={(e) => update(i, "price", e.target.value)} data-testid={`saved-item-tier-price-${i}`} />
          <Button type="button" size="icon" variant="ghost" onClick={() => remove(i)} data-testid={`saved-item-tier-remove-${i}`}><X className="size-3.5" /></Button>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" onClick={add} data-testid="saved-item-tier-add-button"><Plus className="size-3.5 mr-1" />Add tier</Button>
    </div>
  );
}

/** EC9 Phase 9D — reusable Saved/Common Items library (Promotional Items, banners, etc.). */
export default function SavedItemsPanel({ categoryMeta }) {
  const qc = useQueryClient();
  const [category, setCategory] = useState("__all__");
  const [quickOnly, setQuickOnly] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [variationOf, setVariationOf] = useState(null);
  const [variationName, setVariationName] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["saved-items-panel", category, quickOnly, showArchived],
    queryFn: async () => (await api.get("/pricing/saved-items", {
      params: { active: !showArchived, ...(category !== "__all__" ? { category } : {}), ...(quickOnly ? { quick_select: true } : {}) },
    })).data,
  });
  const { data: matData } = useQuery({ queryKey: ["materials-active", "all"], queryFn: async () => (await api.get("/materials", { params: { active: true } })).data });
  const materials = matData?.items || [];

  const invalidate = () => qc.invalidateQueries({ queryKey: ["saved-items-panel"] });

  const openNew = () => { setForm(emptyForm(category !== "__all__" ? category : "banners")); setEditing({}); };
  const openEdit = (item) => {
    setForm({ name: item.name, category: item.category, material_refs: item.material_refs || [], pricing_component_refs: item.pricing_component_refs || [],
      quantity_tiers: item.quantity_tiers || [], default_pricing_method: item.default_pricing_method || "manual",
      default_notes: item.default_notes || "", quick_select: !!item.quick_select, active: item.active });
    setEditing(item);
  };

  const buildPayload = () => ({
    name: form.name, category: form.category, material_refs: form.material_refs, pricing_component_refs: form.pricing_component_refs,
    quantity_tiers: form.quantity_tiers.filter((t) => t.quantity !== "" && t.price !== "").map((t) => ({ quantity: Number(t.quantity), price: Number(t.price) })),
    default_pricing_method: form.default_pricing_method, default_notes: form.default_notes || null, quick_select: form.quick_select, active: form.active,
  });

  const save = useMutation({
    mutationFn: async () => {
      if (editing?.id) return (await api.patch(`/pricing/saved-items/${editing.id}`, buildPayload())).data; // Update existing (explicit)
      return (await api.post("/pricing/saved-items", buildPayload())).data; // Save as new
    },
    onSuccess: () => { toast.success(editing?.id ? "Saved item updated" : "Saved item created"); invalidate(); setEditing(null); },
    onError: (e) => toast.error(extractError(e)),
  });

  const archiveToggle = useMutation({
    mutationFn: async ({ id, active }) => (await api.patch(`/pricing/saved-items/${id}`, { active })).data,
    onSuccess: () => { toast.success("Updated"); invalidate(); },
    onError: (e) => toast.error(extractError(e)),
  });

  const saveVariation = useMutation({
    mutationFn: async () => (await api.post(`/pricing/saved-items/${variationOf.id}/save-as-variation`, { name: variationName })).data,
    onSuccess: () => { toast.success("Variation saved — original unchanged"); invalidate(); setVariationOf(null); setVariationName(""); },
    onError: (e) => toast.error(extractError(e)),
  });

  const items = data?.items || [];
  const categoryLabel = (id) => categoryMeta?.[id]?.name || id;

  return (
    <Card data-testid="saved-items-panel">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-base">Saved / Common Items</CardTitle>
          <div className="flex items-center gap-2 flex-wrap">
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="w-40" data-testid="saved-items-category-filter"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="__all__">All categories</SelectItem>{Object.entries(categoryMeta || {}).map(([id, m]) => <SelectItem key={id} value={id}>{m.name || id}</SelectItem>)}</SelectContent>
            </Select>
            <label className="flex items-center gap-1.5 text-xs cursor-pointer"><Switch checked={quickOnly} onCheckedChange={setQuickOnly} data-testid="saved-items-quick-only-toggle" />Quick-select only</label>
            <Button size="sm" variant={showArchived ? "secondary" : "outline"} onClick={() => setShowArchived((v) => !v)} data-testid="saved-items-toggle-archived">{showArchived ? "Showing archived" : "Show archived"}</Button>
            <Button size="sm" onClick={openNew} data-testid="saved-items-add-new-button"><Plus className="size-4 mr-1" />New Saved Item</Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="text-sm text-muted-foreground">Loading…</div> : (
          <Table>
            <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Category</TableHead><TableHead>Tiers</TableHead><TableHead>Quick-select</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
            <TableBody>
              {items.map((it) => (
                <TableRow key={it.id} data-testid={`saved-item-row-${it.id}`}>
                  <TableCell>{it.name}{!it.active && <Badge variant="secondary" className="ml-2 text-[10px]">Archived</Badge>}{it.variation_of_id && <Badge variant="outline" className="ml-2 text-[10px]">Variation</Badge>}</TableCell>
                  <TableCell>{categoryLabel(it.category)}</TableCell>
                  <TableCell className="tabular-nums text-xs text-muted-foreground">{it.quantity_tiers?.length ? `${it.quantity_tiers.length} tier(s)` : "—"}</TableCell>
                  <TableCell>{it.quick_select ? <Badge className="bg-amber-100 text-amber-900">★ Quick-select</Badge> : "—"}</TableCell>
                  <TableCell className="text-right space-x-1">
                    <Button size="sm" variant="outline" onClick={() => openEdit(it)} data-testid={`saved-item-edit-${it.id}`}>Edit</Button>
                    <Button size="sm" variant="outline" onClick={() => { setVariationOf(it); setVariationName(`${it.name} (variation)`); }} data-testid={`saved-item-variation-${it.id}`}><Copy className="size-3.5" /></Button>
                    <Button size="sm" variant="ghost" onClick={() => archiveToggle.mutate({ id: it.id, active: !it.active })} data-testid={`saved-item-archive-toggle-${it.id}`}>
                      {it.active ? <Archive className="size-3.5" /> : <ArchiveRestore className="size-3.5" />}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-6">No saved items yet.</TableCell></TableRow>}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto" data-testid="saved-item-form-dialog">
          <DialogHeader><DialogTitle>{editing?.id ? "Update existing saved item" : "Save as new item"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5"><Label className="text-xs">Name</Label><Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="saved-item-form-name" /></div>
              <div className="grid gap-1.5">
                <Label className="text-xs">Category</Label>
                <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}>
                  <SelectTrigger data-testid="saved-item-form-category"><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(categoryMeta || {}).map(([id, m]) => <SelectItem key={id} value={id}>{m.name || id}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Pricing method</Label>
              <Select value={form.default_pricing_method} onValueChange={(v) => setForm((f) => ({ ...f, default_pricing_method: v }))}>
                <SelectTrigger data-testid="saved-item-form-pricing-method"><SelectValue /></SelectTrigger>
                <SelectContent>{PRICING_METHODS.map((m) => <SelectItem key={m} value={m}>{m.replace("_", " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            {form.default_pricing_method === "tier_pricing" && (
              <div className="grid gap-1.5"><Label className="text-xs">Quantity tiers (exact-match only — no invented pricing)</Label><QuantityTiersEditor tiers={form.quantity_tiers} onChange={(t) => setForm((f) => ({ ...f, quantity_tiers: t }))} /></div>
            )}
            <div className="grid gap-1.5">
              <Label className="text-xs">Canonical materials used</Label>
              <div className="flex flex-wrap gap-3 max-h-28 overflow-y-auto rounded border p-2">
                {materials.map((m) => (
                  <label key={m.id} className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <input type="checkbox" checked={form.material_refs.includes(m.id)}
                      onChange={(e) => setForm((f) => ({ ...f, material_refs: e.target.checked ? [...f.material_refs, m.id] : f.material_refs.filter((id) => id !== m.id) }))}
                      data-testid={`saved-item-material-${m.id}`} />
                    {m.name}
                  </label>
                ))}
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Pricing components (fees)</Label>
              <PricingComponentSelector value={form.pricing_component_refs} onChange={(v) => setForm((f) => ({ ...f, pricing_component_refs: v }))} category={form.category} testIdPrefix="saved-item-component" />
            </div>
            <div className="grid gap-1.5"><Label className="text-xs">Notes</Label><Textarea rows={2} value={form.default_notes} onChange={(e) => setForm((f) => ({ ...f, default_notes: e.target.value }))} data-testid="saved-item-form-notes" /></div>
            <label className="flex items-center gap-2 text-sm cursor-pointer"><Switch checked={form.quick_select} onCheckedChange={(v) => setForm((f) => ({ ...f, quick_select: v }))} data-testid="saved-item-form-quick-select" />Mark as quick-select / common item</label>
          </div>
          <DialogFooter><Button onClick={() => save.mutate()} disabled={!form.name || save.isPending} data-testid="saved-item-form-save-button">{editing?.id ? "Update existing item" : "Save as new item"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!variationOf} onOpenChange={(o) => !o && setVariationOf(null)}>
        <DialogContent className="max-w-sm" data-testid="saved-item-variation-dialog">
          <DialogHeader><DialogTitle>Save as variation of "{variationOf?.name}"</DialogTitle></DialogHeader>
          <p className="text-xs text-muted-foreground">The original item is never changed — this creates a new, independent copy.</p>
          <div className="grid gap-1.5"><Label className="text-xs">New variation name</Label><Input value={variationName} onChange={(e) => setVariationName(e.target.value)} data-testid="saved-item-variation-name" /></div>
          <DialogFooter><Button onClick={() => saveVariation.mutate()} disabled={!variationName || saveVariation.isPending} data-testid="saved-item-variation-save-button">Save variation</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
