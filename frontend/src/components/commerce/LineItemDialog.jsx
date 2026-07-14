import { useEffect, useMemo, useState } from "react";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import MoneyInput from "@/components/forms/MoneyInput";
import { centsToDollarsString } from "@/lib/format";
import { CategorySpecificFields } from "@/components/pricing/CategorySpecificFields";
import SavedItemSelector from "@/components/pricing/selectors/SavedItemSelector";
import PricingComponentSelector from "@/components/pricing/selectors/PricingComponentSelector";
import MaterialProfilePicker from "@/components/pricing/selectors/MaterialProfileSelector";
import { Calculator, RefreshCw } from "lucide-react";

/**
 * EC3/EC9 Phase 9F — Shared commerce line item editor. Used by Quote line
 * items AND Order items. Detailed entry embeds the SAME category calculator
 * building blocks as the standalone Pricing Calculator (CategorySpecificFields,
 * SavedItemSelector, PricingComponentSelector, a canonical-material picker) —
 * never a duplicate of the full Pricing Foundation UI.
 *
 * Props:
 *  - open, onOpenChange
 *  - mode: "add" | "edit"
 *  - entryMode: "quick" | "detailed" (initial tab)
 *  - initial: existing item to edit (optional)
 *  - onSubmit: async (payload) => item (backend response)
 *  - onRecalculatePreview: async (categoryInputs) => {old,new} (edit mode only, draft docs only)
 *  - entityLabel: "Quote" | "Order"
 *  - allowProductionRequired: bool (only meaningful for Order items)
 */

const CATEGORY_OPTIONS = [
  { id: "banners", name: "Banners" },
  { id: "rigid_signs", name: "Rigid Signs" },
  { id: "cut_vinyl", name: "Cut Vinyl" },
  { id: "digital_print", name: "Digital Print" },
  { id: "vehicle_graphics", name: "Vehicle Graphics" },
  { id: "apparel", name: "Apparel" },
  { id: "services", name: "Services (no production)" },
  { id: "promotional", name: "Promotional (no production)" },
  { id: "custom", name: "Custom" },
];
const DIMENSIONLESS_CATEGORIES = ["apparel", "promotional", "vehicle_graphics", "services", "custom"];
const UOM_OPTIONS = ["each", "sqft", "linear_ft", "hour"];
const NON_PRODUCTION = new Set(["services", "promotional"]);

export default function LineItemDialog({
  open,
  onOpenChange,
  mode = "add",
  entryMode = "quick",
  initial = null,
  onSubmit,
  onRecalculatePreview,
  entityLabel = "Line",
  allowProductionRequired = false,
}) {
  const [tab, setTab] = useState(entryMode);

  // form state
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [productType, setProductType] = useState("");
  const [sku, setSku] = useState("");
  const [uom, setUom] = useState("each");
  const [quantity, setQuantity] = useState(1);
  const [width, setWidth] = useState("");
  const [height, setHeight] = useState("");
  const [unitPriceCents, setUnitPriceCents] = useState(0);
  const [discountCents, setDiscountCents] = useState(0);
  const [taxCents, setTaxCents] = useState(0);
  const [notes, setNotes] = useState("");
  const [productionRequired, setProductionRequired] = useState(true);
  const [productionOverrideReason, setProductionOverrideReason] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [calc, setCalc] = useState(null);   // last calculator result (full backend response)
  const [calcBusy, setCalcBusy] = useState(false);

  // EC9 Phase 9F — calculator/reference state
  const [designNeeded, setDesignNeeded] = useState(false);
  const [installNeeded, setInstallNeeded] = useState(false);
  const [categoryInputs, setCategoryInputs] = useState({});
  const [materialProfileId, setMaterialProfileId] = useState(null);
  const [pricingComponentIds, setPricingComponentIds] = useState([]);
  const [savedItemId, setSavedItemId] = useState(null);
  const [priceSource, setPriceSource] = useState("manual"); // "suggested" | "manual"
  const [manualPriceCents, setManualPriceCents] = useState(0);
  const [recalcPreview, setRecalcPreview] = useState(null); // {old,new} or null
  const [recalcAccepted, setRecalcAccepted] = useState(false);
  const [recalcBusy, setRecalcBusy] = useState(false);
  const [priceInputVersion, setPriceInputVersion] = useState(0); // bumped on programmatic price pushes so MoneyInput re-syncs

  useEffect(() => {
    if (!open) return;
    setTab(entryMode);
    setRecalcPreview(null);
    setRecalcAccepted(false);
    if (initial) {
      setDescription(initial.description || "");
      setCategory(initial.category || "");
      setProductType(initial.product_type || "");
      setSku(initial.sku || "");
      setUom(initial.unit_of_measure || "each");
      setQuantity(initial.quantity || 1);
      setWidth(initial.width_inches ?? "");
      setHeight(initial.height_inches ?? "");
      setUnitPriceCents(initial.unit_price_cents || 0);
      setManualPriceCents(initial.manual_price_cents ?? initial.unit_price_cents ?? 0);
      setDiscountCents(initial.discount_cents || 0);
      setTaxCents(initial.tax_cents || 0);
      setNotes(initial.notes || "");
      setProductionRequired(initial.production_required ?? true);
      setProductionOverrideReason(initial.production_required_override_reason || "");
      setOverrideReason(initial.manual_override_reason || "");
      setCategoryInputs(initial.category_inputs || {});
      setMaterialProfileId(initial.material_profile_id || null);
      setPricingComponentIds(initial.pricing_component_ids || []);
      setSavedItemId(initial.saved_item_id || null);
      setPriceSource(initial.selected_price_source || "manual");
      setPriceInputVersion((v) => v + 1);
      setCalc(initial.pricing_status === "calculated" ? {
        selling_price: (initial.suggested_price_cents ?? 0) / 100,
        calculated_unit_price_cents: initial.suggested_price_cents,
        pricing_method_used: initial.pricing_snapshot?.pricing_method,
        breakdown: initial.pricing_snapshot?.breakdown,
        calculation_warnings: initial.calculation_warnings,
        source_labels: initial.source_labels,
      } : null);
    } else {
      setDescription(""); setCategory(""); setProductType(""); setSku("");
      setUom("each"); setQuantity(1); setWidth(""); setHeight("");
      setUnitPriceCents(0); setManualPriceCents(0); setDiscountCents(0); setTaxCents(0);
      setNotes(""); setProductionRequired(true);
      setProductionOverrideReason(""); setOverrideReason(""); setCalc(null);
      setDesignNeeded(false); setInstallNeeded(false); setCategoryInputs({});
      setMaterialProfileId(null); setPricingComponentIds([]); setSavedItemId(null);
      setPriceSource("manual");
      setPriceInputVersion((v) => v + 1);
    }
  }, [open, initial, entryMode]);

  // Frontend estimate (backend will re-derive on save)
  const estimatedLineTotalCents = useMemo(() => {
    const sub = Math.max(0, Number(quantity) || 0) * Math.max(0, Number(unitPriceCents) || 0);
    const total = sub - (Number(discountCents) || 0) + (Number(taxCents) || 0);
    return total < 0 ? 0 : total;
  }, [quantity, unitPriceCents, discountCents, taxCents]);

  // If the item already has a saved reason, editing the price again does NOT require re-entering it,
  // but backend still requires a reason on change. We show a helper hint.
  const priceChangedFromInitial = mode === "edit" && initial && Number(unitPriceCents) !== Number(initial.unit_price_cents || 0);

  async function runCalculator() {
    if (!category) { toast.error("Choose a category first"); return; }
    setCalcBusy(true);
    try {
      const body = {
        category,
        width_inches: width === "" ? null : Number(width),
        height_inches: height === "" ? null : Number(height),
        quantity: Math.max(1, Number(quantity) || 1),
        design_needed: designNeeded,
        install_needed: installNeeded,
        category_inputs: categoryInputs,
        material_profile_id: materialProfileId,
        pricing_component_ids: pricingComponentIds,
        saved_item_id: savedItemId,
      };
      const { data } = await api.post("/pricing/calculate", body);
      const cents = Math.round(Number(data.selling_price || 0) * 100);
      setCalc({ ...data, calculated_unit_price_cents: cents });
      if (priceSource === "suggested") { setUnitPriceCents(cents); setPriceInputVersion((v) => v + 1); }
      toast.success(`Calculator suggested ${centsToDollarsString(cents)} / unit`);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setCalcBusy(false);
    }
  }

  function choosePriceSource(next) {
    setPriceSource(next);
    if (next === "suggested" && calc?.calculated_unit_price_cents != null) {
      setUnitPriceCents(calc.calculated_unit_price_cents);
    } else if (next === "manual") {
      setUnitPriceCents(manualPriceCents);
    }
    setPriceInputVersion((v) => v + 1);
  }

  async function runRecalculatePreview() {
    if (!onRecalculatePreview) return;
    setRecalcBusy(true);
    try {
      const preview = await onRecalculatePreview(categoryInputs);
      setRecalcPreview(preview);
      setRecalcAccepted(false);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setRecalcBusy(false);
    }
  }

  function acceptRecalculation() {
    if (!recalcPreview) return;
    setUnitPriceCents(recalcPreview.new.unit_price_cents);
    setPriceSource(recalcPreview.new.selected_price_source);
    setCalc((c) => ({ ...c, calculated_unit_price_cents: recalcPreview.new.suggested_price_cents }));
    setRecalcAccepted(true);
    setPriceInputVersion((v) => v + 1);
    toast.success("Recalculation accepted — save to apply");
  }

  function rejectRecalculation() {
    setRecalcPreview(null);
    setRecalcAccepted(false);
  }

  async function submit() {
    if (!description.trim()) { toast.error("Description is required"); return; }

    const usingCalculator = Boolean(category) && (
      Object.keys(categoryInputs || {}).length > 0 || Boolean(materialProfileId) ||
      pricingComponentIds.length > 0 || Boolean(savedItemId) || priceSource === "suggested"
    );

    // Manual override reason required whenever the SELECTED final price
    // changes AND the source is "manual" (suggested acceptances never need one).
    const finalManualPrice = priceSource === "manual" ? Number(unitPriceCents) || 0 : null;
    const priceChanged = mode === "add" ? priceSource === "manual" : priceChangedFromInitial;
    if (priceSource === "manual" && priceChanged && !overrideReason.trim() && !initial?.manual_override_reason) {
      toast.error("Override reason is required for a manual price");
      return;
    }

    const payload = {
      description: description.trim(),
      category: category || null,
      product_type: productType || null,
      sku: sku || null,
      unit_of_measure: uom,
      quantity: Math.max(1, Number(quantity) || 1),
      width_inches: width === "" ? null : Number(width),
      height_inches: height === "" ? null : Number(height),
      unit_price_cents: Math.max(0, Number(unitPriceCents) || 0),
      discount_cents: Math.max(0, Number(discountCents) || 0),
      tax_cents: Math.max(0, Number(taxCents) || 0),
      notes: notes || null,
    };
    if (overrideReason.trim()) payload.manual_override_reason = overrideReason.trim();

    if (usingCalculator) {
      payload.category_inputs = categoryInputs;
      payload.material_profile_id = materialProfileId;
      payload.pricing_component_ids = pricingComponentIds;
      payload.saved_item_id = savedItemId;
      payload.selected_price_source = priceSource;
      if (finalManualPrice != null) payload.manual_price_cents = finalManualPrice;
    }
    if (recalcAccepted) payload.recalculate = true;

    if (allowProductionRequired) {
      if (mode === "add") {
        payload.production_required = productionRequired;
      } else if (initial && Boolean(initial.production_required) !== Boolean(productionRequired)) {
        payload.production_required = productionRequired;
        if (!productionOverrideReason.trim()) {
          toast.error("Production-required override reason is required");
          return;
        }
        payload.production_required_override_reason = productionOverrideReason.trim();
      }
    }

    setBusy(true);
    try {
      await onSubmit(payload);
      onOpenChange(false);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setBusy(false);
    }
  }

  // If category is a non-production one, auto-suggest productionRequired=false in add mode
  useEffect(() => {
    if (mode !== "add" || !allowProductionRequired || !category) return;
    setProductionRequired(!NON_PRODUCTION.has(category));
  }, [category, mode, allowProductionRequired]);

  const isDimensionless = DIMENSIONLESS_CATEGORIES.includes(category);
  const canRecalculate = mode === "edit" && initial?.category && initial?.pricing_status === "calculated" && onRecalculatePreview;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[760px] max-h-[90vh] overflow-y-auto" data-testid="line-item-dialog">
        <DialogHeader>
          <DialogTitle>{mode === "add" ? `Add ${entityLabel} item` : `Edit ${entityLabel} item`}</DialogTitle>
          <DialogDescription>
            Totals and calculator suggestions are always derived by the server. Manual overrides require a reason.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={tab} onValueChange={setTab} data-testid="line-item-mode-tabs">
          <TabsList>
            <TabsTrigger value="quick" data-testid="mode-quick">Quick entry</TabsTrigger>
            <TabsTrigger value="detailed" data-testid="mode-detailed">Detailed</TabsTrigger>
          </TabsList>

          <TabsContent value="quick" className="grid gap-3 pt-2">
            <div className="grid gap-1.5">
              <Label>Description*</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} data-testid="li-description" />
            </div>
            <div className="grid grid-cols-[1fr_100px_160px] gap-2">
              <div className="grid gap-1.5">
                <Label>Category</Label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger data-testid="li-category"><SelectValue placeholder="Choose" /></SelectTrigger>
                  <SelectContent>
                    {CATEGORY_OPTIONS.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label>Qty*</Label>
                <Input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} data-testid="li-quantity" />
              </div>
              <div className="grid gap-1.5">
                <Label>Unit price</Label>
                <MoneyInput value={unitPriceCents} onChange={(v) => { setUnitPriceCents(v); setManualPriceCents(v); setPriceSource("manual"); }} testId="li-unit-price" key={`qk-${priceInputVersion}`} />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label>Optional saved item</Label>
              <SavedItemSelector value={savedItemId} onChange={(id) => setSavedItemId(id)} category={category || undefined} testIdPrefix="li-quick-saved-item" />
            </div>
          </TabsContent>

          <TabsContent value="detailed" className="grid gap-3 pt-2">
            <div className="grid gap-1.5">
              <Label>Description*</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} data-testid="li-description-detailed" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="grid gap-1.5">
                <Label>Category</Label>
                <Select value={category} onValueChange={(v) => { setCategory(v); setCategoryInputs({}); setCalc(null); }}>
                  <SelectTrigger data-testid="li-category-detailed"><SelectValue placeholder="Choose" /></SelectTrigger>
                  <SelectContent>
                    {CATEGORY_OPTIONS.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label>Product type</Label>
                <Input value={productType} onChange={(e) => setProductType(e.target.value)} data-testid="li-product-type" />
              </div>
              <div className="grid gap-1.5">
                <Label>SKU</Label>
                <Input value={sku} onChange={(e) => setSku(e.target.value)} data-testid="li-sku" />
              </div>
            </div>
            <div className="grid grid-cols-4 gap-2">
              <div className="grid gap-1.5">
                <Label>Qty*</Label>
                <Input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} data-testid="li-quantity-detailed" />
              </div>
              <div className="grid gap-1.5">
                <Label>UoM</Label>
                <Select value={uom} onValueChange={setUom}>
                  <SelectTrigger data-testid="li-uom"><SelectValue /></SelectTrigger>
                  <SelectContent>{UOM_OPTIONS.map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              {!isDimensionless && (
                <>
                  <div className="grid gap-1.5">
                    <Label>Width (in)</Label>
                    <Input type="number" min="0" value={width} onChange={(e) => setWidth(e.target.value)} data-testid="li-width" />
                  </div>
                  <div className="grid gap-1.5">
                    <Label>Height (in)</Label>
                    <Input type="number" min="0" value={height} onChange={(e) => setHeight(e.target.value)} data-testid="li-height" />
                  </div>
                </>
              )}
            </div>

            {category && (
              <div className="rounded-lg border p-3 space-y-3 bg-muted/20">
                <div className="text-xs font-medium text-muted-foreground">Calculator inputs</div>
                {!isDimensionless && (
                  <div className="flex items-center gap-6">
                    <label className="flex items-center gap-2 text-sm cursor-pointer"><Switch checked={designNeeded} onCheckedChange={setDesignNeeded} data-testid="li-design-switch" />Design needed</label>
                    <label className="flex items-center gap-2 text-sm cursor-pointer"><Switch checked={installNeeded} onCheckedChange={setInstallNeeded} data-testid="li-install-switch" />Install needed</label>
                  </div>
                )}
                <CategorySpecificFields category={category} values={categoryInputs} onChange={setCategoryInputs} designNeeded={designNeeded} installNeeded={installNeeded} />
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5">
                    <Label className="text-xs">Canonical material (optional)</Label>
                    <MaterialProfilePicker value={materialProfileId} onChange={setMaterialProfileId} category={category} testIdPrefix="li-material-profile" />
                  </div>
                  <div className="grid gap-1.5">
                    <Label className="text-xs">Saved item (optional)</Label>
                    <SavedItemSelector value={savedItemId} onChange={(id) => setSavedItemId(id)} category={category} testIdPrefix="li-saved-item" />
                  </div>
                </div>
                <div className="grid gap-1.5">
                  <Label className="text-xs">Pricing components (optional)</Label>
                  <PricingComponentSelector value={pricingComponentIds} onChange={setPricingComponentIds} category={category} testIdPrefix="li-components" />
                </div>
                <Button type="button" variant="outline" onClick={runCalculator} disabled={calcBusy} data-testid="li-calculator">
                  <Calculator className="size-4 mr-1" />{calcBusy ? "Calculating…" : "Calculate"}
                </Button>
              </div>
            )}

            {calc && calc.calculated_unit_price_cents != null && (
              <div className="rounded-md border bg-muted/40 p-3 text-xs space-y-2" data-testid="li-calc-result">
                <div>Suggested price: <span className="font-semibold tabular-nums">{centsToDollarsString(calc.calculated_unit_price_cents)}</span> / unit ({calc.pricing_method_used || "n/a"})</div>
                {calc.calculation_warnings?.length > 0 && (
                  <ul className="list-disc pl-4 text-amber-700" data-testid="li-calc-warnings">
                    {calc.calculation_warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                )}
                <div className="flex items-center gap-4 pt-1">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" checked={priceSource === "suggested"} onChange={() => choosePriceSource("suggested")} data-testid="li-price-source-suggested" />
                    Use suggested ({centsToDollarsString(calc.calculated_unit_price_cents)})
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" checked={priceSource === "manual"} onChange={() => choosePriceSource("manual")} data-testid="li-price-source-manual" />
                    Use manual price
                  </label>
                </div>
              </div>
            )}

            <div className="flex items-end justify-between gap-2 flex-wrap">
              <div className="grid gap-1.5 flex-1 min-w-[200px]">
                <Label>Unit price {priceSource === "manual" ? "(manual)" : "(suggested — read-only)"}</Label>
                <MoneyInput
                  key={`dt-${priceInputVersion}`}
                  value={unitPriceCents}
                  onChange={(v) => { setUnitPriceCents(v); setManualPriceCents(v); }}
                  disabled={priceSource === "suggested"}
                  testId="li-unit-price-detailed"
                />
              </div>
              <div className="grid gap-1.5 flex-1 min-w-[160px]">
                <Label>Discount</Label>
                <MoneyInput value={discountCents} onChange={setDiscountCents} testId="li-discount" />
              </div>
              <div className="grid gap-1.5 flex-1 min-w-[160px]">
                <Label>Tax</Label>
                <MoneyInput value={taxCents} onChange={setTaxCents} testId="li-tax" />
              </div>
            </div>

            {(priceSource === "manual" && (mode === "add" || priceChangedFromInitial)) && (
              <div className="grid gap-1.5">
                <Label>Manual override reason*</Label>
                <Input
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="e.g. customer negotiated 10% discount"
                  data-testid="li-override-reason"
                />
              </div>
            )}

            {canRecalculate && (
              <div className="rounded-lg border p-3 space-y-2" data-testid="li-recalculate-panel">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-muted-foreground">Recalculate with current Pricing Foundation defaults</span>
                  <Button type="button" variant="outline" size="sm" onClick={runRecalculatePreview} disabled={recalcBusy} data-testid="li-recalculate-button">
                    <RefreshCw className="size-3.5 mr-1" />{recalcBusy ? "Checking…" : "Recalculate"}
                  </Button>
                </div>
                {recalcPreview && !recalcAccepted && (
                  <div className="rounded-md border bg-amber-50 p-2 text-xs space-y-2" data-testid="li-recalculate-diff">
                    <div>Old: <span className="font-semibold tabular-nums">{centsToDollarsString(recalcPreview.old.unit_price_cents)}</span> → New: <span className="font-semibold tabular-nums">{centsToDollarsString(recalcPreview.new.unit_price_cents)}</span></div>
                    <div className="flex gap-2">
                      <Button type="button" size="sm" onClick={acceptRecalculation} data-testid="li-recalculate-accept">Accept</Button>
                      <Button type="button" size="sm" variant="ghost" onClick={rejectRecalculation} data-testid="li-recalculate-reject">Reject</Button>
                    </div>
                  </div>
                )}
                {recalcAccepted && <Badge variant="secondary" data-testid="li-recalculate-accepted-badge">Recalculation accepted — will apply on save</Badge>}
              </div>
            )}

            {allowProductionRequired && (
              <div className="rounded-md border p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="cursor-pointer">Requires production</Label>
                  <Switch checked={productionRequired} onCheckedChange={setProductionRequired} data-testid="li-production-required" />
                </div>
                {mode === "edit" && initial && Boolean(initial.production_required) !== Boolean(productionRequired) && (
                  <div className="grid gap-1.5">
                    <Label className="text-xs text-muted-foreground">Override reason*</Label>
                    <Input
                      value={productionOverrideReason}
                      onChange={(e) => setProductionOverrideReason(e.target.value)}
                      placeholder="e.g. outsourced to partner"
                      data-testid="li-production-override-reason"
                    />
                  </div>
                )}
                <div className="text-xs text-muted-foreground">
                  Work orders snapshot only items requiring production.
                </div>
              </div>
            )}
            <div className="grid gap-1.5">
              <Label>Notes</Label>
              <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="li-notes" />
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex items-center justify-between text-sm border-t pt-3">
          <span className="text-muted-foreground">Frontend estimate (server will re-derive):</span>
          <span className="font-semibold tabular-nums" data-testid="li-estimate">{centsToDollarsString(estimatedLineTotalCents)}</span>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} type="button">Cancel</Button>
          <Button onClick={submit} disabled={busy} data-testid="li-submit">
            {busy ? "Saving…" : mode === "add" ? "Add item" : "Save changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
