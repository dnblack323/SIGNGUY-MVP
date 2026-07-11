import { useEffect, useMemo, useState } from "react";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import MoneyInput from "@/components/forms/MoneyInput";
import { centsToDollarsString } from "@/lib/format";
import { Calculator } from "lucide-react";

/**
 * EC3 — Shared commerce line item editor. Used by Quote line items AND Order items.
 *
 * Props:
 *  - open, onOpenChange
 *  - mode: "add" | "edit"
 *  - entryMode: "quick" | "detailed" (initial tab)
 *  - initial: existing item to edit (optional)
 *  - onSubmit: async (payload) => item (backend response)
 *  - entityLabel: "Quote" | "Order"
 *  - allowProductionRequired: bool (only meaningful for Order items)
 *  - existingOverrideReason: whether the current item already has a saved reason
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

const UOM_OPTIONS = ["each", "sqft", "linear_ft", "hour"];

const NON_PRODUCTION = new Set(["services", "promotional"]);

export default function LineItemDialog({
  open,
  onOpenChange,
  mode = "add",
  entryMode = "quick",
  initial = null,
  onSubmit,
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
  const [calc, setCalc] = useState(null);   // last calculator result
  const [calcBusy, setCalcBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTab(entryMode);
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
      setDiscountCents(initial.discount_cents || 0);
      setTaxCents(initial.tax_cents || 0);
      setNotes(initial.notes || "");
      setProductionRequired(initial.production_required ?? true);
      setProductionOverrideReason(initial.production_required_override_reason || "");
      setOverrideReason(initial.manual_override_reason || "");
    } else {
      setDescription(""); setCategory(""); setProductType(""); setSku("");
      setUom("each"); setQuantity(1); setWidth(""); setHeight("");
      setUnitPriceCents(0); setDiscountCents(0); setTaxCents(0);
      setNotes(""); setProductionRequired(true);
      setProductionOverrideReason(""); setOverrideReason(""); setCalc(null);
    }
  }, [open, initial, entryMode]);

  // Frontend estimate (backend will re-derive on save)
  const estimatedLineTotalCents = useMemo(() => {
    const sub = Math.max(0, Number(quantity) || 0) * Math.max(0, Number(unitPriceCents) || 0);
    const total = sub - (Number(discountCents) || 0) + (Number(taxCents) || 0);
    return total < 0 ? 0 : total;
  }, [quantity, unitPriceCents, discountCents, taxCents]);

  // Detect if user is overriding a calculator-derived unit price
  const isOverridingCalc = useMemo(() => {
    if (!calc) return false;
    if (!calc.calculated_unit_price_cents) return false;
    return Number(unitPriceCents) !== Number(calc.calculated_unit_price_cents);
  }, [calc, unitPriceCents]);

  // If the item already has a saved reason, editing the price again does NOT require re-entering it,
  // but backend still requires a reason on change. We show a helper hint.
  const priceChangedFromInitial = mode === "edit" && initial && Number(unitPriceCents) !== Number(initial.unit_price_cents || 0);

  async function runCalculator() {
    if (!category) { toast.error("Choose a category first"); return; }
    setCalcBusy(true);
    try {
      const body = {
        category,
        width_inches: Number(width) || null,
        height_inches: Number(height) || null,
        quantity: Math.max(1, Number(quantity) || 1),
      };
      const { data } = await api.post("/pricing/calculate", body);
      const cents = Math.round(Number(data.selling_price || 0) * 100);
      setCalc({ ...data, calculated_unit_price_cents: cents });
      setUnitPriceCents(cents);
      toast.success(`Calculator suggested ${centsToDollarsString(cents)} / unit`);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setCalcBusy(false);
    }
  }

  async function submit() {
    if (!description.trim()) { toast.error("Description is required"); return; }

    // Manual override reason must be supplied whenever the user is overriding
    // a calculator suggestion OR editing an existing item's unit price.
    const priceChanged = mode === "add"
      ? (isOverridingCalc && unitPriceCents !== calc?.calculated_unit_price_cents)
      : priceChangedFromInitial;
    if (priceChanged && !overrideReason.trim() && !initial?.manual_override_reason) {
      toast.error("Override reason is required when changing the calculated/existing unit price");
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

    if (allowProductionRequired) {
      // For NEW order items: send explicit production_required if user changed it (else backend defaults from category).
      // For EDITS: only send when it actually changed, with reason.
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[720px]" data-testid="line-item-dialog">
        <DialogHeader>
          <DialogTitle>{mode === "add" ? `Add ${entityLabel} item` : `Edit ${entityLabel} item`}</DialogTitle>
          <DialogDescription>
            Totals are calculated by the server after save. Manual overrides require a reason.
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
                <MoneyInput value={unitPriceCents} onChange={setUnitPriceCents} testId="li-unit-price" />
              </div>
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
                <Select value={category} onValueChange={setCategory}>
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
              <div className="grid gap-1.5">
                <Label>Width (in)</Label>
                <Input type="number" min="0" value={width} onChange={(e) => setWidth(e.target.value)} data-testid="li-width" />
              </div>
              <div className="grid gap-1.5">
                <Label>Height (in)</Label>
                <Input type="number" min="0" value={height} onChange={(e) => setHeight(e.target.value)} data-testid="li-height" />
              </div>
            </div>
            <div className="flex items-end justify-between gap-2 flex-wrap">
              <div className="grid gap-1.5 flex-1 min-w-[200px]">
                <Label>Unit price</Label>
                <MoneyInput value={unitPriceCents} onChange={setUnitPriceCents} testId="li-unit-price-detailed" />
              </div>
              <div className="grid gap-1.5 flex-1 min-w-[160px]">
                <Label>Discount</Label>
                <MoneyInput value={discountCents} onChange={setDiscountCents} testId="li-discount" />
              </div>
              <div className="grid gap-1.5 flex-1 min-w-[160px]">
                <Label>Tax</Label>
                <MoneyInput value={taxCents} onChange={setTaxCents} testId="li-tax" />
              </div>
              <Button type="button" variant="outline" onClick={runCalculator} disabled={calcBusy || !category} data-testid="li-calculator">
                <Calculator className="size-4 mr-1" />{calcBusy ? "Calculating…" : "Use calculator"}
              </Button>
            </div>
            {calc && calc.calculated_unit_price_cents ? (
              <div className="rounded-md border bg-muted/40 p-2 text-xs" data-testid="li-calc-result">
                Calculator suggested <span className="font-semibold tabular-nums">{centsToDollarsString(calc.calculated_unit_price_cents)}</span>{" "}
                per unit ({calc.pricing_method_used || "n/a"}).
                {isOverridingCalc && <span className="ml-1 text-amber-600 font-medium">You have overridden this.</span>}
              </div>
            ) : null}
            {(isOverridingCalc || priceChangedFromInitial) && (
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
