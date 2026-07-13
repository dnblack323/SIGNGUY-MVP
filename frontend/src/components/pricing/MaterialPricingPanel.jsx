import { useMemo, useState } from "react";
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
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Plus, Pencil, ArchiveRestore, Archive } from "lucide-react";

const PRICING_UNITS = ["per_sqft", "per_unit", "per_linear_ft", "per_garment", "other"];
const MATERIAL_CATEGORIES = ["vinyl", "laminate", "application_tape", "printable_media", "substrate",
  "banner", "ink", "hardware", "apparel", "heat_transfer", "packaging", "equipment", "supplies", "other"];

function ProfileForm({ profile, categoryOptions, onSave, saving }) {
  const [f, setF] = useState(() => ({
    pricing_unit: profile?.pricing_unit || "per_sqft",
    normalized_cost_basis: profile?.normalized_cost_basis ?? "",
    waste_percent: profile?.waste_percent ?? 0,
    default_markup_multiplier: profile?.default_markup_multiplier ?? "",
    default_margin_percent: profile?.default_margin_percent ?? "",
    suggested_sell_rate: profile?.suggested_sell_rate ?? "",
    minimum_sell_amount: profile?.minimum_sell_amount ?? "",
    category_applicability: profile?.category_applicability || [],
    pricing_notes: profile?.pricing_notes || "",
    active: profile?.active ?? true,
  }));
  const num = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5">
          <Label className="text-xs">Pricing unit</Label>
          <Select value={f.pricing_unit} onValueChange={num("pricing_unit")}>
            <SelectTrigger data-testid="profile-pricing-unit"><SelectValue /></SelectTrigger>
            <SelectContent>{PRICING_UNITS.map((u) => <SelectItem key={u} value={u}>{u.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Normalized cost basis ($)</Label>
          <Input type="number" step="0.01" value={f.normalized_cost_basis} onChange={(e) => num("normalized_cost_basis")(e.target.value)} data-testid="profile-cost-basis" />
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Waste %</Label>
          <Input type="number" step="0.1" value={f.waste_percent} onChange={(e) => num("waste_percent")(e.target.value)} data-testid="profile-waste-percent" />
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Markup multiplier</Label>
          <Input type="number" step="0.01" value={f.default_markup_multiplier} onChange={(e) => num("default_markup_multiplier")(e.target.value)} data-testid="profile-markup" />
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Target margin %</Label>
          <Input type="number" step="0.1" value={f.default_margin_percent} onChange={(e) => num("default_margin_percent")(e.target.value)} data-testid="profile-margin" />
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Suggested sell rate ($)</Label>
          <Input type="number" step="0.01" value={f.suggested_sell_rate} onChange={(e) => num("suggested_sell_rate")(e.target.value)} data-testid="profile-sell-rate" />
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Minimum sell amount ($)</Label>
          <Input type="number" step="0.01" value={f.minimum_sell_amount} onChange={(e) => num("minimum_sell_amount")(e.target.value)} data-testid="profile-min-sell" />
        </div>
      </div>
      <div className="grid gap-1.5">
        <Label className="text-xs">Applies to categories</Label>
        <div className="flex flex-wrap gap-3">
          {Object.entries(categoryOptions || {}).map(([id, m]) => (
            <label key={id} className="flex items-center gap-1.5 text-xs cursor-pointer">
              <input type="checkbox" checked={f.category_applicability.includes(id)}
                onChange={(e) => setF((s) => ({ ...s, category_applicability: e.target.checked ? [...s.category_applicability, id] : s.category_applicability.filter((c) => c !== id) }))}
                data-testid={`profile-category-${id}`} />
              {m.name || id}
            </label>
          ))}
        </div>
      </div>
      <div className="grid gap-1.5">
        <Label className="text-xs">Pricing notes</Label>
        <Textarea rows={2} value={f.pricing_notes} onChange={(e) => num("pricing_notes")(e.target.value)} data-testid="profile-notes" />
      </div>
      <DialogFooter>
        <Button onClick={() => onSave(f)} disabled={saving} data-testid="profile-save-button">Save pricing profile</Button>
      </DialogFooter>
    </div>
  );
}

/** EC9 Phase 9D — browse canonical Materials + view/edit their linked Material Pricing Profile. */
export default function MaterialPricingPanel({ categoryMeta }) {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [profileMaterial, setProfileMaterial] = useState(null); // material row being edited
  const [newMat, setNewMat] = useState({ name: "", category: "other", current_cost_cents: "" });

  const { data: matData, isLoading } = useQuery({
    queryKey: ["materials-panel", q, showArchived],
    queryFn: async () => (await api.get("/materials", { params: { active: !showArchived, ...(q ? { q } : {}) } })).data,
  });
  const { data: profileData } = useQuery({
    queryKey: ["material-profiles-panel"],
    queryFn: async () => (await api.get("/pricing/material-profiles")).data,
  });
  const profileByMaterial = useMemo(() => {
    const map = {};
    for (const p of profileData?.items || []) map[p.material_id] = p;
    return map;
  }, [profileData]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["materials-panel"] });
    qc.invalidateQueries({ queryKey: ["material-profiles-panel"] });
  };

  const createMaterial = useMutation({
    mutationFn: async () => (await api.post("/materials", {
      name: newMat.name, category: newMat.category, current_cost_cents: Math.round(Number(newMat.current_cost_cents || 0) * 100),
    })).data,
    onSuccess: () => { toast.success("Material created"); invalidate(); setAddOpen(false); setNewMat({ name: "", category: "other", current_cost_cents: "" }); },
    onError: (e) => toast.error(extractError(e)),
  });

  const archiveToggle = useMutation({
    mutationFn: async ({ id, archive }) => (await api.post(`/materials/${id}/${archive ? "archive" : "restore"}`)).data,
    onSuccess: () => { toast.success("Updated"); invalidate(); },
    onError: (e) => toast.error(extractError(e)),
  });

  const saveProfile = useMutation({
    mutationFn: async (fields) => {
      const payload = { ...fields, normalized_cost_basis: fields.normalized_cost_basis === "" ? null : Number(fields.normalized_cost_basis),
        default_markup_multiplier: fields.default_markup_multiplier === "" ? null : Number(fields.default_markup_multiplier),
        default_margin_percent: fields.default_margin_percent === "" ? null : Number(fields.default_margin_percent),
        suggested_sell_rate: fields.suggested_sell_rate === "" ? null : Number(fields.suggested_sell_rate),
        minimum_sell_amount: fields.minimum_sell_amount === "" ? null : Number(fields.minimum_sell_amount),
        waste_percent: Number(fields.waste_percent || 0) };
      const existing = profileByMaterial[profileMaterial.id];
      if (existing) return (await api.patch(`/pricing/material-profiles/${existing.id}`, payload)).data;
      return (await api.post(`/pricing/material-profiles/materials/${profileMaterial.id}`, payload)).data;
    },
    onSuccess: () => { toast.success("Pricing profile saved"); invalidate(); setProfileMaterial(null); },
    onError: (e) => toast.error(extractError(e)),
  });

  const items = matData?.items || [];

  return (
    <Card data-testid="material-pricing-panel">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-base">Canonical Materials & Pricing Profiles</CardTitle>
          <div className="flex items-center gap-2">
            <Button size="sm" variant={showArchived ? "secondary" : "outline"} onClick={() => setShowArchived((v) => !v)} data-testid="materials-toggle-archived">
              {showArchived ? "Showing archived" : "Show archived"}
            </Button>
            <Button size="sm" onClick={() => setAddOpen(true)} data-testid="materials-add-new-button"><Plus className="size-4 mr-1" />Add Material</Button>
          </div>
        </div>
        <Input placeholder="Search materials by name or SKU…" value={q} onChange={(e) => setQ(e.target.value)} className="mt-2" data-testid="materials-search-input" />
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="text-sm text-muted-foreground">Loading…</div> : (
          <Table>
            <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Category</TableHead><TableHead>Cost</TableHead><TableHead>Pricing profile</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
            <TableBody>
              {items.map((m) => {
                const profile = profileByMaterial[m.id];
                return (
                  <TableRow key={m.id} data-testid={`material-row-${m.id}`}>
                    <TableCell>{m.name}{!m.active && <Badge variant="secondary" className="ml-2 text-[10px]">Archived</Badge>}</TableCell>
                    <TableCell className="capitalize">{m.category}</TableCell>
                    <TableCell className="tabular-nums">${(m.current_cost_cents / 100).toFixed(2)}</TableCell>
                    <TableCell>{profile ? <Badge className="bg-emerald-100 text-emerald-800">Set up{profile.active ? "" : " (inactive)"}</Badge> : <Badge variant="secondary">Not set up</Badge>}</TableCell>
                    <TableCell className="text-right space-x-1">
                      <Button size="sm" variant="outline" onClick={() => setProfileMaterial(m)} disabled={!m.active} data-testid={`material-profile-edit-${m.id}`}>
                        <Pencil className="size-3.5 mr-1" />{profile ? "Edit profile" : "Create profile"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => archiveToggle.mutate({ id: m.id, archive: m.active })} data-testid={`material-archive-toggle-${m.id}`}>
                        {m.active ? <Archive className="size-3.5" /> : <ArchiveRestore className="size-3.5" />}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
              {items.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-6">No materials found.</TableCell></TableRow>}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-sm" data-testid="materials-add-dialog">
          <DialogHeader><DialogTitle>Add New Material</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid gap-1.5"><Label>Name</Label><Input value={newMat.name} onChange={(e) => setNewMat((f) => ({ ...f, name: e.target.value }))} data-testid="materials-add-name" /></div>
            <div className="grid gap-1.5">
              <Label>Category</Label>
              <Select value={newMat.category} onValueChange={(v) => setNewMat((f) => ({ ...f, category: v }))}>
                <SelectTrigger data-testid="materials-add-category"><SelectValue /></SelectTrigger>
                <SelectContent>{MATERIAL_CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c.replace("_", " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5"><Label>Current cost ($)</Label><Input type="number" step="0.01" value={newMat.current_cost_cents} onChange={(e) => setNewMat((f) => ({ ...f, current_cost_cents: e.target.value }))} data-testid="materials-add-cost" /></div>
          </div>
          <DialogFooter><Button onClick={() => createMaterial.mutate()} disabled={!newMat.name || createMaterial.isPending} data-testid="materials-add-save-button">Create material</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!profileMaterial} onOpenChange={(o) => !o && setProfileMaterial(null)}>
        <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto" data-testid="material-profile-dialog">
          <DialogHeader><DialogTitle>Pricing profile — {profileMaterial?.name}</DialogTitle></DialogHeader>
          {profileMaterial && (
            <ProfileForm profile={profileByMaterial[profileMaterial.id]} categoryOptions={categoryMeta} saving={saveProfile.isPending}
              onSave={(f) => saveProfile.mutate(f)} />
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
}
