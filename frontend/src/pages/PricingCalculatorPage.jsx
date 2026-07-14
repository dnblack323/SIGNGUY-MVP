import { useMemo, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import MoneyInput from "@/components/forms/MoneyInput";
import SavedItemSelector from "@/components/pricing/selectors/SavedItemSelector";
import { CategorySpecificFields } from "@/components/pricing/CategorySpecificFields";
import { Calculator, Loader2, Save, Copy, RefreshCw } from "lucide-react";

const FLAT_SQFT_CATEGORIES = ["banners", "rigid_signs", "digital_print", "cut_vinyl"];
const DIMENSIONLESS_CATEGORIES = ["apparel", "promotional", "vehicle_graphics", "services", "custom"];
const CATEGORY_SPECIFIC_CATEGORIES = ["banners", "rigid_signs", "digital_print", "cut_vinyl", "apparel", "promotional", "vehicle_graphics", "services", "custom"];
const ITEM_LABEL_CATEGORIES = ["promotional", "services", "custom"];

const fmtUSD = (n) => Number(n || 0).toLocaleString("en-US", { style: "currency", currency: "USD" });
const fmtPct = (n) => `${Number(n || 0).toFixed(2)}%`;

export default function PricingCalculatorPage() {
  const { data: settings } = useQuery({ queryKey: ["pricing-settings"], queryFn: async () => (await api.get("/pricing/settings")).data });

  const [form, setForm] = useState({
    category: "banners",
    width_inches: 48,
    height_inches: 96,
    quantity: 1,
    material_key: "",
    design_needed: false,
    install_needed: false,
    manual_selling_price: null,
    category_inputs: {},
  });

  const materialOptions = useMemo(() => {
    if (!settings) return [];
    return Object.entries(settings.materials || {})
      .filter(([, m]) => m.category === form.category)
      .map(([key, m]) => ({ key, label: `${m.name} — $${m.cost_per_sqft}/sqft cost` }));
  }, [settings, form.category]);

  const [result, setResult] = useState(null);
  const [savedItem, setSavedItem] = useState(null); // full item object once picked, else null = one-time/custom
  const [saveDialog, setSaveDialog] = useState(null); // "new" | "variation" | null
  const [saveName, setSaveName] = useState("");
  const [quickSelect, setQuickSelect] = useState(false);
  const [tierPreview, setTierPreview] = useState(null);
  const [useSavedDefaults, setUseSavedDefaults] = useState(true);

  const calc = useMutation({
    mutationFn: async () => (await api.post("/pricing/calculate", {
      category: form.category,
      width_inches: Number(form.width_inches) || 0,
      height_inches: Number(form.height_inches) || 0,
      quantity: Number(form.quantity) || 1,
      material_key: form.material_key || null,
      design_needed: form.design_needed,
      install_needed: form.install_needed,
      manual_selling_price: form.manual_selling_price != null ? Number(form.manual_selling_price) : null,
      category_inputs: CATEGORY_SPECIFIC_CATEGORIES.includes(form.category) ? form.category_inputs : {},
      saved_item_id: form.category === "promotional" ? (savedItem?.id || null) : null,
    })).data,
    onSuccess: async (data) => {
      setResult(data);
      if (savedItem?.default_pricing_method === "tier_pricing") {
        const r = await api.get(`/pricing/saved-items/${savedItem.id}/tier-price`, { params: { quantity: Number(form.quantity) || 1 } });
        setTierPreview(r.data);
      } else {
        setTierPreview(null);
      }
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const savedItemConfig = () => ({
    category: form.category, width_inches: Number(form.width_inches) || 0, height_inches: Number(form.height_inches) || 0,
    quantity: Number(form.quantity) || 1, material_key: form.material_key || null,
    design_needed: form.design_needed, install_needed: form.install_needed, category_inputs: form.category_inputs,
  });

  const saveAsNew = useMutation({
    mutationFn: async () => (await api.post("/pricing/saved-items", {
      name: saveName, category: form.category, saved_config: savedItemConfig(), quick_select: quickSelect,
    })).data,
    onSuccess: (item) => { toast.success(`Saved as new item "${item.name}"`); setSavedItem(item); setSaveDialog(null); setSaveName(""); },
    onError: (e) => toast.error(extractError(e)),
  });

  const updateExisting = useMutation({
    mutationFn: async () => (await api.patch(`/pricing/saved-items/${savedItem.id}`, { saved_config: savedItemConfig() })).data,
    onSuccess: (item) => { toast.success(`Updated "${item.name}" with the current configuration`); setSavedItem(item); },
    onError: (e) => toast.error(extractError(e)),
  });

  const saveAsVariation = useMutation({
    mutationFn: async () => (await api.post(`/pricing/saved-items/${savedItem.id}/save-as-variation`, { name: saveName, saved_config: savedItemConfig() })).data,
    onSuccess: (item) => { toast.success(`Saved variation "${item.name}" — original unchanged`); setSavedItem(item); setSaveDialog(null); setSaveName(""); },
    onError: (e) => toast.error(extractError(e)),
  });

  const applySavedItem = (id, item) => {
    setSavedItem(item);
    const shouldLoadDefaults = form.category !== "promotional" || useSavedDefaults;
    if (shouldLoadDefaults && item?.saved_config && Object.keys(item.saved_config).length) {
      setForm((f) => ({ ...f, ...item.saved_config }));
    }
  };

  const upd = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="space-y-4" data-testid="pricing-calculator-page">
      <PageHeader title="Pricing Calculator" subtitle="Estimate a price using your tenant’s current pricing settings." />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Inputs</CardTitle></CardHeader>
          <CardContent className="grid gap-3">
            <div className="grid gap-1.5">
              <Label>Saved / common item <span className="text-muted-foreground font-normal">(optional — pick one, or leave as a one-time custom item)</span></Label>
              <SavedItemSelector value={savedItem?.id} onChange={applySavedItem} category={form.category} testIdPrefix="calc-saved-item" />
              {savedItem && <Badge variant="secondary" className="w-fit text-[10px]">Loaded from "{savedItem.name}" — values below stay fully editable</Badge>}
              {form.category === "promotional" && (
                <label className="flex items-center gap-2 text-xs cursor-pointer text-muted-foreground">
                  <Switch checked={useSavedDefaults} onCheckedChange={setUseSavedDefaults} data-testid="calc-promo-use-saved-defaults-switch" />
                  Use saved item defaults when a saved item is picked
                </label>
              )}
            </div>
            <div className="grid gap-1.5">
              <Label>Category</Label>
              <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v, material_key: "", category_inputs: {} }))}>
                <SelectTrigger data-testid="calc-category-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(settings?.category_meta || {}).map(([id, m]) => <SelectItem key={id} value={id}>{m.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {DIMENSIONLESS_CATEGORIES.includes(form.category) ? (
              <div className="grid gap-1.5"><Label>Quantity</Label><Input type="number" min="1" value={form.quantity} onChange={(e) => upd("quantity")(e.target.value)} data-testid="calc-quantity-input" /></div>
            ) : (
              <div className="grid grid-cols-3 gap-3">
                <div className="grid gap-1.5"><Label>Width (in)</Label><Input type="number" value={form.width_inches} onChange={(e) => upd("width_inches")(e.target.value)} data-testid="calc-width-input" /></div>
                <div className="grid gap-1.5"><Label>Height (in)</Label><Input type="number" value={form.height_inches} onChange={(e) => upd("height_inches")(e.target.value)} data-testid="calc-height-input" /></div>
                <div className="grid gap-1.5"><Label>Quantity</Label><Input type="number" min="1" value={form.quantity} onChange={(e) => upd("quantity")(e.target.value)} data-testid="calc-quantity-input" /></div>
              </div>
            )}
            {materialOptions.length > 0 && !DIMENSIONLESS_CATEGORIES.includes(form.category) && (
              <div className="grid gap-1.5">
                <Label>Material (optional)</Label>
                <Select value={form.material_key || "__default__"} onValueChange={(v) => upd("material_key")(v === "__default__" ? "" : v)}>
                  <SelectTrigger data-testid="calc-material-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__default__">Use category default</SelectItem>
                    {materialOptions.map((m) => <SelectItem key={m.key} value={m.key}>{m.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
            {!DIMENSIONLESS_CATEGORIES.includes(form.category) && (
              <div className="flex items-center gap-6 pt-1">
                <label className="flex items-center gap-2 text-sm cursor-pointer"><Switch checked={form.design_needed} onCheckedChange={upd("design_needed")} data-testid="calc-design-switch" />Design needed</label>
                <label className="flex items-center gap-2 text-sm cursor-pointer"><Switch checked={form.install_needed} onCheckedChange={upd("install_needed")} data-testid="calc-install-switch" />Install needed</label>
              </div>
            )}
            {CATEGORY_SPECIFIC_CATEGORIES.includes(form.category) && (
              <CategorySpecificFields
                category={form.category}
                values={form.category_inputs}
                onChange={(next) => setForm((f) => ({ ...f, category_inputs: next }))}
                designNeeded={form.design_needed}
                installNeeded={form.install_needed}
              />
            )}
            <div className="grid gap-1.5">
              <Label>Manual selling price override (optional)</Label>
              <MoneyInput value={form.manual_selling_price ? Math.round(form.manual_selling_price * 100) : 0} onChange={(cents) => upd("manual_selling_price")(cents ? cents / 100 : null)} testId="calc-manual-override" />
            </div>
            <Button onClick={() => calc.mutate()} disabled={calc.isPending} data-testid="calc-run-button">
              {calc.isPending && <Loader2 className="size-4 mr-2 animate-spin" />}<Calculator className="size-4 mr-1" />Calculate
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Result</CardTitle></CardHeader>
          <CardContent>
            {!result ? (
              <div className="text-sm text-muted-foreground">Fill in inputs and click Calculate.</div>
            ) : (
              <div className="space-y-4" data-testid="calc-result">
                {result.requires_manual_price && (
                  <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800" data-testid="calc-requires-manual-price-warning">
                    No configured tier price for quantity {result.quantity} — this is not a guessed price. Enter a manual selling price override below.
                  </div>
                )}
                {(result.calculation_warnings || []).length > 0 && (
                  <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800 space-y-1" data-testid="calc-warnings-banner">
                    {result.calculation_warnings.map((w, i) => <div key={i}>{w}</div>)}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border p-3">
                    <div className="text-xs text-muted-foreground">Selling price</div>
                    <div className="text-2xl font-semibold tabular-nums" data-testid="calc-selling-price">{result.selling_price != null ? fmtUSD(result.selling_price) : "—"}</div>
                  </div>
                  <div className="rounded-lg border p-3">
                    <div className="text-xs text-muted-foreground">Profit margin</div>
                    <div className="text-2xl font-semibold tabular-nums" data-testid="calc-margin">{result.profit_margin_percent != null ? fmtPct(result.profit_margin_percent) : "—"}</div>
                    <div className="text-xs text-muted-foreground mt-1">{result.profit_amount != null ? fmtUSD(result.profit_amount) : "—"} profit</div>
                  </div>
                </div>

                <div className="rounded-lg border">
                  <div className="px-3 py-2 border-b flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Cost breakdown</span>
                    <span className="capitalize text-muted-foreground">Method: {String(result.pricing_method_used).replace(/_/g, " ")}</span>
                  </div>
                  <ul className="divide-y">
                    {result.breakdown.map((row, i) => (
                      <li key={i} className="flex items-center justify-between px-3 py-2 text-sm">
                        <span className="text-muted-foreground">{row.label}</span>
                        <span className="tabular-nums">{fmtUSD(row.amount)}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground">
                  {!DIMENSIONLESS_CATEGORIES.includes(result.category) && (
                    <div>Area (total): <span className="tabular-nums text-foreground">{result.area_sqft_total} sqft</span></div>
                  )}
                  <div>Quantity: <span className="tabular-nums text-foreground">{result.quantity}</span></div>
                  <div>{ITEM_LABEL_CATEGORIES.includes(result.category) ? "Item" : "Material"}: <span className="mono text-foreground">{result.material_key || "—"}</span></div>
                  <div>Category: <span className="capitalize text-foreground">{result.category.replace("_"," ")}</span></div>
                </div>

                {tierPreview && (
                  <div className="rounded-lg border p-3 text-xs" data-testid="calc-tier-preview">
                    {tierPreview.matched
                      ? <span>Exact tier match for qty {tierPreview.quantity}: <strong className="tabular-nums">${tierPreview.price.toFixed(2)}</strong> (from "{savedItem.name}")</span>
                      : <span className="text-amber-700">No configured tier for qty {tierPreview.quantity} on "{savedItem.name}" — use manual pricing instead of guessing.</span>}
                  </div>
                )}

                <div className="rounded-lg border p-3 space-y-2">
                  <div className="text-xs font-medium">Reusable item</div>
                  {!savedItem ? (
                    <Button size="sm" variant="outline" onClick={() => setSaveDialog("new")} data-testid="calc-save-as-new-button"><Save className="size-3.5 mr-1" />Save this as a reusable item</Button>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => updateExisting.mutate()} disabled={updateExisting.isPending} data-testid="calc-update-existing-button"><RefreshCw className="size-3.5 mr-1" />Update "{savedItem.name}"</Button>
                      <Button size="sm" variant="outline" onClick={() => { setSaveDialog("variation"); setSaveName(`${savedItem.name} (variation)`); }} data-testid="calc-save-variation-button"><Copy className="size-3.5 mr-1" />Save as variation</Button>
                      <Button size="sm" variant="ghost" onClick={() => setSaveDialog("new")} data-testid="calc-save-as-new-from-loaded-button"><Save className="size-3.5 mr-1" />Save as new item</Button>
                    </div>
                  )}
                  <p className="text-[11px] text-muted-foreground">Leave unsaved to use this as a one-time custom item — nothing is saved unless you choose to.</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={!!saveDialog} onOpenChange={(o) => !o && setSaveDialog(null)}>
        <DialogContent className="max-w-sm" data-testid="calc-save-dialog">
          <DialogHeader><DialogTitle>{saveDialog === "variation" ? "Save as variation" : "Save as new reusable item"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid gap-1.5"><Label className="text-xs">Item name</Label><Input value={saveName} onChange={(e) => setSaveName(e.target.value)} data-testid="calc-save-name-input" /></div>
            {saveDialog === "new" && (
              <label className="flex items-center gap-2 text-sm cursor-pointer"><Switch checked={quickSelect} onCheckedChange={setQuickSelect} data-testid="calc-save-quick-select-switch" />Mark as quick-select / common item</label>
            )}
          </div>
          <DialogFooter>
            <Button onClick={() => (saveDialog === "variation" ? saveAsVariation.mutate() : saveAsNew.mutate())} disabled={!saveName || saveAsNew.isPending || saveAsVariation.isPending} data-testid="calc-save-confirm-button">
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
