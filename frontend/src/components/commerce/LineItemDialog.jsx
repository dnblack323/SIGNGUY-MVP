import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
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
import SavedCalculationLibrary from "@/components/pricing/SavedCalculationLibrary";
import { useAuth } from "@/auth/AuthContext";
import { Calculator, FolderOpen, RefreshCw } from "lucide-react";

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
const dimensionUnit = (inputs) => inputs?.dimension_unit || "in";
const normalizeDimension = (value, unit) => (unit === "ft" ? (Number(value) || 0) * 12 : Number(value) || 0);
const fmtMethodMoney = (amount) => {
  if (amount == null || Number.isNaN(Number(amount))) return "Unavailable";
  return centsToDollarsString(Math.round(Number(amount) * 100));
};
const humanize = (value) => String(value || "n/a").replaceAll("_", " ");
const methodRowId = (row) => row?.method_id || row?.method || row?.id || "";
const methodStatusText = (row) => {
  const statuses = Array.isArray(row?.status) ? row.status : (row?.status ? [row.status] : []);
  return statuses.length ? statuses.join(", ") : (row?.available === false ? "unavailable" : "available");
};
const availabilityRows = (availability) => {
  if (Array.isArray(availability)) return availability;
  if (Array.isArray(availability?.methods)) return availability.methods;
  return [];
};

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
  const { hasPerm } = useAuth();
  const queryClient = useQueryClient();
  const canCalculatePricing = typeof hasPerm === "function" ? hasPerm("pricing:calculate") : false;
  const canReadPricing = canCalculatePricing || (typeof hasPerm === "function" ? hasPerm("pricing:read") : false);
  const canWritePricing = typeof hasPerm === "function" ? hasPerm("pricing:write") : canCalculatePricing;
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
  const [calcUpdating, setCalcUpdating] = useState(false);
  const [calcError, setCalcError] = useState("");
  const [comparison, setComparison] = useState(null);
  const [selectedComparisonMethod, setSelectedComparisonMethod] = useState("");
  const calcResultKeyRef = useRef("");

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
  const [showSavedLibrary, setShowSavedLibrary] = useState(false);
  const [saveCalculationName, setSaveCalculationName] = useState("");
  const [saveCalculationNotes, setSaveCalculationNotes] = useState("");
  const [saveCalculationBusy, setSaveCalculationBusy] = useState(false);
  const [savedReuse, setSavedReuse] = useState(null);

  useEffect(() => {
    if (!open) return;
    setTab(entryMode);
    setRecalcPreview(null);
    setRecalcAccepted(false);
    setShowSavedLibrary(false);
    setSaveCalculationName("");
    setSaveCalculationNotes("");
    setSavedReuse(null);
    if (initial) {
      const snapshot = initial.pricing_snapshot || {};
      const initialInputs = initial.category_inputs || {};
      const measurement = snapshot.measurement || {};
      const initialUnit = dimensionUnit(initialInputs);
      const initialIsDimensionless = DIMENSIONLESS_CATEGORIES.includes(initial.category || "");
      const enteredWidth = measurement.entered_width ?? initialInputs.entered_width;
      const enteredHeight = measurement.entered_height ?? initialInputs.entered_height;
      setDescription(initial.description || "");
      setCategory(initial.category || "");
      setProductType(initial.product_type || "");
      setSku(initial.sku || "");
      setUom(initial.unit_of_measure || "each");
      setQuantity(initial.quantity || 1);
      setWidth(!initialIsDimensionless && initialUnit !== "in" && enteredWidth != null ? enteredWidth : (initial.width_inches ?? ""));
      setHeight(!initialIsDimensionless && initialUnit !== "in" && enteredHeight != null ? enteredHeight : (initial.height_inches ?? ""));
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
      setCalcUpdating(false);
      setCalcError("");
      setComparison(null);
      setSelectedComparisonMethod("");
      calcResultKeyRef.current = initial.pricing_status === "calculated" ? JSON.stringify({
        category: initial.category || "",
        width_inches: initialIsDimensionless ? null : (initial.width_inches ?? null),
        height_inches: initialIsDimensionless ? null : (initial.height_inches ?? null),
        quantity: Math.max(1, Number(initial.quantity) || 1),
        design_needed: false,
        install_needed: false,
        category_inputs: initialInputs,
        material_profile_id: initial.material_profile_id || null,
        pricing_component_ids: initial.pricing_component_ids || [],
        saved_item_id: initial.saved_item_id || null,
      }) : "";
      setCalc(initial.pricing_status === "calculated" ? {
        selling_price: snapshot.selected_selling_price_dollars ?? snapshot.calculated_unit_price_dollars ?? ((initial.suggested_price_cents ?? 0) / 100),
        calculated_unit_price_cents: initial.suggested_price_cents,
        pricing_method_used: snapshot.selected_pricing_method || snapshot.pricing_method,
        true_cost: snapshot.true_cost_dollars,
        pricing_method_results: snapshot.pricing_method_results,
        breakdown: snapshot.breakdown,
        detail_sections: snapshot.detail_sections,
        measurement: snapshot.measurement,
        calculation_warnings: initial.calculation_warnings,
        source_labels: initial.source_labels || snapshot.source_labels,
      } : null);
    } else {
      setDescription(""); setCategory(""); setProductType(""); setSku("");
      setUom("each"); setQuantity(1); setWidth(""); setHeight("");
      setUnitPriceCents(0); setManualPriceCents(0); setDiscountCents(0); setTaxCents(0);
      setNotes(""); setProductionRequired(true);
      setProductionOverrideReason(""); setOverrideReason(""); setCalc(null);
      setCalcUpdating(false);
      setCalcError("");
      setComparison(null);
      setSelectedComparisonMethod("");
      calcResultKeyRef.current = "";
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
  const isDimensionless = DIMENSIONLESS_CATEGORIES.includes(category);

  // If the item already has a saved reason, editing the price again does NOT require re-entering it,
  // but backend still requires a reason on change. We show a helper hint.
  const priceChangedFromInitial = mode === "edit" && initial && Number(unitPriceCents) !== Number(initial.unit_price_cents || 0);
  const currentDimensionUnit = dimensionUnit(categoryInputs);
  const calculatorCategoryInputs = () => {
    if (isDimensionless) return categoryInputs;
    return {
      ...(categoryInputs || {}),
      dimension_unit: currentDimensionUnit,
      entered_width: width === "" ? null : Number(width),
      entered_height: height === "" ? null : Number(height),
    };
  };
  const normalizedWidthInches = isDimensionless ? null : normalizeDimension(width, currentDimensionUnit);
  const normalizedHeightInches = isDimensionless ? null : normalizeDimension(height, currentDimensionUnit);
  const hasValidCalculatorDimensions = isDimensionless || (Number(width) > 0 && Number(height) > 0);
  const calculatorPayload = () => ({
    category,
    width_inches: normalizedWidthInches,
    height_inches: normalizedHeightInches,
    quantity: Math.max(1, Number(quantity) || 1),
    design_needed: designNeeded,
    install_needed: installNeeded,
    category_inputs: calculatorCategoryInputs(),
    material_profile_id: materialProfileId,
    pricing_component_ids: pricingComponentIds,
    saved_item_id: savedItemId,
  });
  const currentCalculatorKey = () => (category && hasValidCalculatorDimensions ? JSON.stringify(calculatorPayload()) : "");
  const clearCalculatorResult = ({ clearTransferredPrice = true } = {}) => {
    setCalc(null);
    setComparison(null);
    setSelectedComparisonMethod("");
    setCalcError("");
    setCalcUpdating(false);
    setSavedReuse(null);
    calcResultKeyRef.current = "";
    if (clearTransferredPrice && priceSource === "suggested") {
      setUnitPriceCents(0);
      setPriceInputVersion((v) => v + 1);
    }
  };
  const onPriceAffectingChange = (applyChange) => {
    applyChange();
    clearCalculatorResult();
  };

  async function runCalculator({ silent = false, primaryMethodId = selectedComparisonMethod } = {}) {
    if (!canCalculatePricing) {
      setCalc(null);
      setComparison(null);
      setCalcError("You do not have permission to calculate prices.");
      setCalcUpdating(false);
      if (!silent) toast.error("You do not have permission to calculate prices");
      return;
    }
    if (!category) { toast.error("Choose a category first"); return; }
    if (!hasValidCalculatorDimensions) {
      setCalc(null);
      setComparison(null);
      setCalcError("");
      setCalcUpdating(false);
      calcResultKeyRef.current = "";
      if (!silent) toast.error("Enter valid width and height first");
      return;
    }
    setCalcBusy(true);
    try {
      const body = calculatorPayload();
      const calculationKey = JSON.stringify(body);
      const { data } = await api.post("/pricing/calculate", body);
      const sellingPrice = Number(data.selling_price);
      if (data.selling_price == null || !Number.isFinite(sellingPrice)) {
        setCalc(null);
        setComparison(null);
        setCalcError("The calculator did not return a transferable selling price.");
        calcResultKeyRef.current = "";
        setCalcUpdating(false);
        if (!silent) toast.error("Calculated pricing is unavailable for these inputs");
        return;
      }
      const calculatedLineCents = Math.round(sellingPrice * 100);
      const cents = category === "digital_print"
        ? Math.round(calculatedLineCents / Math.max(1, Number(quantity) || 1))
        : calculatedLineCents;
      let comparisonData = null;
      if (category === "banners") {
        comparisonData = (await api.post("/pricing/method-comparison", {
          ...body,
          use_saved_configuration: true,
          primary_method_id: primaryMethodId || undefined,
        })).data;
      }
      calcResultKeyRef.current = calculationKey;
      setCalc({ ...data, calculated_unit_price_cents: cents, calculated_line_price_cents: calculatedLineCents });
      setComparison(comparisonData);
      setSelectedComparisonMethod(
        comparisonData?.selected_method_id || primaryMethodId || data.selected_method_id || data.canonical_method_id || data.pricing_method_used || "",
      );
      setCalcError("");
      setCalcUpdating(false);
      if (priceSource === "suggested" || (!unitPriceCents && !manualPriceCents)) {
        setPriceSource("suggested");
        setUnitPriceCents(cents);
        setPriceInputVersion((v) => v + 1);
      }
      if (!silent) toast.success(`Calculator suggested ${centsToDollarsString(cents)} / unit`);
    } catch (e) {
      setCalcUpdating(false);
      setCalcError(extractError(e));
      setCalc(null);
      setComparison(null);
      calcResultKeyRef.current = "";
      if (!silent) toast.error(extractError(e));
    } finally {
      setCalcBusy(false);
    }
  }
  const runCalculatorRef = useRef(runCalculator);
  useEffect(() => {
    runCalculatorRef.current = runCalculator;
  });

  useEffect(() => {
    if (!open || tab !== "detailed" || !category) return undefined;
    if (!hasValidCalculatorDimensions) {
      setCalc(null);
      setCalcUpdating(false);
      calcResultKeyRef.current = "";
      return undefined;
    }
    const calculationKey = JSON.stringify(calculatorPayload());
    if (calcResultKeyRef.current && calcResultKeyRef.current !== calculationKey) {
      setCalcUpdating(true);
    }
    const timer = setTimeout(() => runCalculatorRef.current({ silent: true }), 450);
    return () => clearTimeout(timer);
  }, [open, tab, category, width, height, quantity, designNeeded, installNeeded, categoryInputs, materialProfileId, pricingComponentIds, savedItemId, isDimensionless]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!savedReuse) return;
    const key = currentCalculatorKey();
    if (savedReuse.calculationKey !== key) setSavedReuse(null);
  }, [category, width, height, quantity, designNeeded, installNeeded, categoryInputs, materialProfileId, pricingComponentIds, savedItemId]); // eslint-disable-line react-hooks/exhaustive-deps

  function choosePriceSource(next) {
    if (next === "suggested" && (!calc || calc.calculated_unit_price_cents == null || calcResultKeyRef.current !== currentCalculatorKey())) {
      toast.error("Calculate a current suggested price before using it");
      return;
    }
    setPriceSource(next);
    if (next === "suggested" && calc?.calculated_unit_price_cents != null) {
      setUnitPriceCents(calc.calculated_unit_price_cents);
    } else if (next === "manual") {
      setUnitPriceCents(manualPriceCents);
    }
    setPriceInputVersion((v) => v + 1);
  }

  function choosePricingMethod(row) {
    const method = methodRowId(row);
    if (!method || row?.available === false || row?.amount == null) return;
    if (category !== "banners") return;
    setSelectedComparisonMethod(method);
    runCalculator({ primaryMethodId: method });
  }

  async function saveCurrentCalculation() {
    if (!saveCalculationName.trim()) {
      toast.error("Saved calculation name is required");
      return;
    }
    if (!calc || calc.calculated_unit_price_cents == null || calcResultKeyRef.current !== currentCalculatorKey()) {
      toast.error("Calculate a current successful result before saving");
      return;
    }
    setSaveCalculationBusy(true);
    try {
      await api.post("/pricing/saved-calculations", {
        name: saveCalculationName.trim(),
        notes: saveCalculationNotes.trim() || null,
        calculation_inputs: calculatorPayload(),
        selected_method_id: selectedMethod,
        source_context: entityLabel === "Order" ? "order_item" : "quote_item",
      });
      queryClient.invalidateQueries({ queryKey: ["pricing-saved-calculations"] });
      toast.success("Calculation saved");
    } catch (error) {
      toast.error(extractError(error));
    } finally {
      setSaveCalculationBusy(false);
    }
  }

  function loadSavedCalculation(data) {
    const inputs = data.saved_calculation?.calculation_inputs || {};
    const isNextDimensionless = DIMENSIONLESS_CATEGORIES.includes(inputs.category || "");
    const nextCategoryInputs = inputs.category_inputs || {};
    const inputUnit = dimensionUnit(nextCategoryInputs);
    const displayWidth = !isNextDimensionless && inputUnit !== "in" && nextCategoryInputs.entered_width != null ? nextCategoryInputs.entered_width : inputs.width_inches;
    const displayHeight = !isNextDimensionless && inputUnit !== "in" && nextCategoryInputs.entered_height != null ? nextCategoryInputs.entered_height : inputs.height_inches;
    setCategory(inputs.category || "");
    setWidth(isNextDimensionless ? "" : (displayWidth ?? ""));
    setHeight(isNextDimensionless ? "" : (displayHeight ?? ""));
    setQuantity(inputs.quantity || 1);
    setDesignNeeded(!!inputs.design_needed);
    setInstallNeeded(!!inputs.install_needed);
    setCategoryInputs(nextCategoryInputs);
    setMaterialProfileId(inputs.material_profile_id || null);
    setPricingComponentIds(inputs.pricing_component_ids || []);
    setSavedItemId(inputs.saved_item_id || null);
    const sellingPrice = Number(data.current_result?.selling_price);
    const cents = Number.isFinite(sellingPrice) ? Math.round(sellingPrice * 100) : null;
    if (cents == null) {
      setCalc(null);
      setCalcError("Saved calculation could not produce a current transferable price.");
      setPriceSource("manual");
      setSavedReuse(data);
      return;
    }
    setCalc({ ...data.current_result, calculated_unit_price_cents: cents });
    setComparison(data.comparison_result || null);
    setSelectedComparisonMethod(data.comparison_result?.selected_method_id || data.current_result?.selected_method_id || data.current_result?.canonical_method_id || "");
    setPriceSource("suggested");
    setUnitPriceCents(cents);
    setPriceInputVersion((v) => v + 1);
    setCalcError("");
    setCalcUpdating(false);
    const key = JSON.stringify({
      category: inputs.category,
      width_inches: isNextDimensionless ? null : normalizeDimension(displayWidth, inputUnit),
      height_inches: isNextDimensionless ? null : normalizeDimension(displayHeight, inputUnit),
      quantity: inputs.quantity || 1,
      design_needed: !!inputs.design_needed,
      install_needed: !!inputs.install_needed,
      category_inputs: isNextDimensionless ? nextCategoryInputs : {
        ...nextCategoryInputs,
        dimension_unit: inputUnit,
        entered_width: displayWidth === "" ? null : Number(displayWidth),
        entered_height: displayHeight === "" ? null : Number(displayHeight),
      },
      material_profile_id: inputs.material_profile_id || null,
      pricing_component_ids: inputs.pricing_component_ids || [],
      saved_item_id: inputs.saved_item_id || null,
    });
    calcResultKeyRef.current = key;
    setSavedReuse({ ...data, calculationKey: key });
    setShowSavedLibrary(false);
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
    if (priceSource === "suggested") {
      if (!canCalculatePricing) {
        toast.error("You do not have permission to transfer calculated pricing");
        return;
      }
      if (!calc || calc.calculated_unit_price_cents == null || calcResultKeyRef.current !== currentCalculatorKey()) {
        toast.error("Calculate a current suggested price before saving");
        return;
      }
    }

    const payload = {
      description: description.trim(),
      category: category || null,
      product_type: productType || null,
      sku: sku || null,
      unit_of_measure: uom,
      quantity: Math.max(1, Number(quantity) || 1),
      width_inches: normalizedWidthInches,
      height_inches: normalizedHeightInches,
      unit_price_cents: Math.max(0, Number(unitPriceCents) || 0),
      discount_cents: Math.max(0, Number(discountCents) || 0),
      tax_cents: Math.max(0, Number(taxCents) || 0),
      notes: notes || null,
    };
    if (overrideReason.trim()) payload.manual_override_reason = overrideReason.trim();

    if (usingCalculator) {
      payload.category_inputs = calculatorCategoryInputs();
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

  const canRecalculate = mode === "edit" && initial?.category && initial?.pricing_status === "calculated" && onRecalculatePreview;
  const comparisonRows = comparison?.comparison_results || calc?.pricing_method_results || [];
  const selectedRow = comparisonRows.find((row) => row.selected) || comparisonRows.find((row) => methodRowId(row) === selectedComparisonMethod);
  const canonicalMethod = comparison?.canonical_method_id || calc?.canonical_method_id || calc?.pricing_method_used || calc?.selected_pricing_method;
  const selectedMethod = comparison?.selected_method_id || methodRowId(selectedRow) || calc?.selected_method_id || canonicalMethod;
  const otherAvailableRows = comparisonRows.filter((row) => methodRowId(row) !== selectedMethod && row.amount != null && row.available !== false);
  const unavailableRows = [
    ...availabilityRows(calc?.method_availability).filter((row) => !row.available),
    ...availabilityRows(comparison?.availability).filter((row) => !row.available),
  ];
  const warnings = calc?.calculation_warnings || calc?.warnings || [];
  const errors = calc?.errors || [];

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
                <Select value={category} onValueChange={(value) => onPriceAffectingChange(() => setCategory(value))}>
                  <SelectTrigger data-testid="li-category"><SelectValue placeholder="Choose" /></SelectTrigger>
                  <SelectContent>
                    {CATEGORY_OPTIONS.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label>Qty*</Label>
                <Input type="number" min="1" value={quantity} onChange={(e) => onPriceAffectingChange(() => setQuantity(e.target.value))} data-testid="li-quantity" />
              </div>
              <div className="grid gap-1.5">
                <Label>Unit price</Label>
                <MoneyInput value={unitPriceCents} onChange={(v) => { setUnitPriceCents(v); setManualPriceCents(v); setPriceSource("manual"); }} testId="li-unit-price" key={`qk-${priceInputVersion}`} />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label>Optional saved item</Label>
              <SavedItemSelector value={savedItemId} onChange={(id) => onPriceAffectingChange(() => setSavedItemId(id))} category={category || undefined} testIdPrefix="li-quick-saved-item" />
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
                <Select value={category} onValueChange={(v) => onPriceAffectingChange(() => { setCategory(v); setCategoryInputs({}); setMaterialProfileId(null); setPricingComponentIds([]); setSavedItemId(null); })}>
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
            <div className="grid grid-cols-5 gap-2">
              <div className="grid gap-1.5">
                <Label>Qty*</Label>
                <Input type="number" min="1" value={quantity} onChange={(e) => onPriceAffectingChange(() => setQuantity(e.target.value))} data-testid="li-quantity-detailed" />
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
                    <Label>Width ({currentDimensionUnit})</Label>
                    <Input type="number" min="0" value={width} onChange={(e) => onPriceAffectingChange(() => setWidth(e.target.value))} data-testid="li-width" />
                  </div>
                  <div className="grid gap-1.5">
                    <Label>Height ({currentDimensionUnit})</Label>
                    <Input type="number" min="0" value={height} onChange={(e) => onPriceAffectingChange(() => setHeight(e.target.value))} data-testid="li-height" />
                  </div>
                  <div className="grid gap-1.5">
                    <Label>Unit</Label>
                    <Select value={currentDimensionUnit} onValueChange={(val) => onPriceAffectingChange(() => setCategoryInputs((prev) => ({ ...(prev || {}), dimension_unit: val })))}>
                      <SelectTrigger data-testid="li-dimension-unit"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="in">Inches</SelectItem>
                        <SelectItem value="ft">Feet</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </>
              )}
            </div>

            {category && (
              <div className="rounded-lg border p-3 space-y-3 bg-muted/20">
                <div className="text-xs font-medium text-muted-foreground">Calculator inputs</div>
                {!isDimensionless && (
                  <div className="flex items-center gap-6">
                    <label className="flex items-center gap-2 text-sm cursor-pointer"><Switch checked={designNeeded} onCheckedChange={(checked) => onPriceAffectingChange(() => setDesignNeeded(checked))} data-testid="li-design-switch" />Design needed</label>
                    <label className="flex items-center gap-2 text-sm cursor-pointer"><Switch checked={installNeeded} onCheckedChange={(checked) => onPriceAffectingChange(() => setInstallNeeded(checked))} data-testid="li-install-switch" />Install needed</label>
                  </div>
                )}
                <CategorySpecificFields category={category} values={categoryInputs} onChange={(values) => onPriceAffectingChange(() => setCategoryInputs(values))} designNeeded={designNeeded} installNeeded={installNeeded} />
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5">
                    <Label className="text-xs">Canonical material (optional)</Label>
                    <MaterialProfilePicker value={materialProfileId} onChange={(id) => onPriceAffectingChange(() => setMaterialProfileId(id))} category={category} testIdPrefix="li-material-profile" />
                  </div>
                  <div className="grid gap-1.5">
                    <Label className="text-xs">Saved item (optional)</Label>
                    <SavedItemSelector value={savedItemId} onChange={(id) => onPriceAffectingChange(() => setSavedItemId(id))} category={category} testIdPrefix="li-saved-item" />
                  </div>
                </div>
                <div className="grid gap-1.5">
                  <Label className="text-xs">Pricing components (optional)</Label>
                  <PricingComponentSelector value={pricingComponentIds} onChange={(ids) => onPriceAffectingChange(() => setPricingComponentIds(ids))} category={category} testIdPrefix="li-components" />
                </div>
                <Button type="button" variant="outline" onClick={() => runCalculator()} disabled={calcBusy || !canCalculatePricing} data-testid="li-calculator">
                  <Calculator className="size-4 mr-1" />{calcBusy ? "Calculating…" : "Calculate"}
                </Button>
                <div className="grid gap-2 md:grid-cols-[minmax(140px,1fr)_minmax(140px,1fr)_auto_auto] md:items-end" data-testid="li-save-calculation-panel">
                  <div className="grid gap-1.5">
                    <Label className="text-xs">Saved calculation name</Label>
                    <Input value={saveCalculationName} onChange={(e) => setSaveCalculationName(e.target.value)} placeholder="Reusable price setup" data-testid="li-save-calculation-name" />
                  </div>
                  <div className="grid gap-1.5">
                    <Label className="text-xs">Notes</Label>
                    <Input value={saveCalculationNotes} onChange={(e) => setSaveCalculationNotes(e.target.value)} placeholder="Optional" data-testid="li-save-calculation-notes" />
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={saveCurrentCalculation}
                    disabled={!canWritePricing || saveCalculationBusy || !saveCalculationName.trim() || !calc || calc.calculated_unit_price_cents == null || calcResultKeyRef.current !== currentCalculatorKey()}
                    data-testid="li-save-calculation-button"
                  >
                    Save Calculation
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setShowSavedLibrary((value) => !value)} data-testid="li-open-saved-library">
                    <FolderOpen className="size-4 mr-1" />Saved Library
                  </Button>
                </div>
                {showSavedLibrary && (
                  <SavedCalculationLibrary
                    compact
                    canRead={canReadPricing}
                    canWrite={canWritePricing}
                    canCalculate={canCalculatePricing}
                    onUseCalculation={loadSavedCalculation}
                  />
                )}
                {!canCalculatePricing && (
                  <div className="text-xs text-destructive" data-testid="li-pricing-permission-blocked">
                    You do not have permission to calculate prices.
                  </div>
                )}
                {!hasValidCalculatorDimensions && (
                  <div className="text-xs text-muted-foreground" data-testid="li-calc-empty-state">
                    Enter valid width and height to price this item.
                  </div>
                )}
                {calcError && (
                  <div className="text-xs text-destructive" data-testid="li-calc-error">{calcError}</div>
                )}
              </div>
            )}

            {calc && calc.calculated_unit_price_cents != null && (
              <div className="rounded-md border bg-muted/40 p-3 text-xs space-y-2" data-testid="li-calc-result">
                {calcUpdating && (
                  <Badge variant="secondary" data-testid="li-calc-updating">
                    Updating calculated price...
                  </Badge>
                )}
                <div data-testid="li-authoritative-selling-price">
                  Authoritative selling price: <span className="font-semibold tabular-nums">{centsToDollarsString(calc.calculated_unit_price_cents)}</span> / unit
                </div>
                <div data-testid="li-canonical-method">
                  Canonical method: <span className="font-medium">{humanize(canonicalMethod)}</span>
                </div>
                <div data-testid="li-selected-method">
                  Selected method: <span className="font-medium">{humanize(selectedMethod)}</span>
                </div>
                {calc.true_cost != null && <div>True cost: <span className="font-semibold tabular-nums">{centsToDollarsString(Math.round(Number(calc.true_cost || 0) * 100))}</span> / unit</div>}
                {warnings.length > 0 && (
                  <ul className="list-disc pl-4 text-amber-700" data-testid="li-calc-warnings">
                    {warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                )}
                {errors.length > 0 && (
                  <ul className="list-disc pl-4 text-destructive" data-testid="li-calc-errors">
                    {errors.map((err, i) => <li key={i}>{err}</li>)}
                  </ul>
                )}
                {comparisonRows.length > 0 && (
                  <div className="rounded border bg-background divide-y" data-testid="li-method-comparison">
                    {comparisonRows.map((row) => {
                      const id = methodRowId(row);
                      const selected = id === selectedMethod;
                      const canSelect = category === "banners" && row.available !== false && row.amount != null;
                      return (
                        <button
                          key={id}
                          type="button"
                          className={`w-full flex items-center justify-between px-2 py-1.5 text-left ${canSelect ? "hover:bg-muted" : "cursor-default"} ${selected ? "bg-primary/5" : ""}`}
                          onClick={() => choosePricingMethod(row)}
                          disabled={!canSelect}
                          data-testid={`li-method-${id}`}
                        >
                          <span>
                            <span className="font-medium">{row.display_name || row.label || humanize(id)}</span>
                            <span className="ml-2 text-muted-foreground">{methodStatusText(row)}</span>
                          </span>
                          <span className="font-semibold tabular-nums">{fmtMethodMoney(row.amount)}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
                {otherAvailableRows.length > 0 && (
                  <div className="text-muted-foreground" data-testid="li-other-method-results">
                    Other available results: {otherAvailableRows.map((row) => `${row.display_name || row.label || humanize(methodRowId(row))} ${fmtMethodMoney(row.amount)}`).join("; ")}
                  </div>
                )}
                {unavailableRows.length > 0 && (
                  <div className="rounded border bg-background p-2 text-muted-foreground" data-testid="li-unavailable-methods">
                    <div className="font-medium text-foreground">Unavailable or unsupported methods</div>
                    {unavailableRows.slice(0, 8).map((row, index) => (
                      <div key={`${methodRowId(row)}-${index}`}>{humanize(methodRowId(row))}: {row.reason || row.explanation || "unavailable"}</div>
                    ))}
                  </div>
                )}
                {(calc.detail_sections?.length > 0 || calc.breakdown?.length > 0) && (
                  <div className="rounded border bg-background p-2 space-y-2" data-testid="li-pricing-details">
                    {calc.breakdown?.length > 0 && (
                      <div>
                        <div className="font-medium">Breakdown</div>
                        {calc.breakdown.slice(0, 8).map((row, index) => (
                          <div key={`${row.label}-${index}`} className="flex justify-between gap-2">
                            <span>{row.label}</span>
                            <span>{fmtMethodMoney(row.amount)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {(calc.detail_sections || []).slice(0, 4).map((section) => (
                      <div key={section.section}>
                        <div className="font-medium">{humanize(section.section)}</div>
                        {(section.lines || []).slice(0, 6).map((line, index) => (
                          <div key={`${line.key || line.label}-${index}`} className="flex justify-between gap-2">
                            <span>{line.label || humanize(line.key)}</span>
                            <span>{String(line.value ?? line.amount ?? "")}</span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
                {savedReuse && (
                  <div className="rounded border bg-background p-2" data-testid="li-saved-current-price-panel">
                    Saved Price: <strong>{centsToDollarsString(Math.round(Number(savedReuse.saved_price || 0) * 100))}</strong> · Current Price: <strong>{centsToDollarsString(calc.calculated_unit_price_cents)}</strong>
                    {savedReuse.price_changed && <Badge className="ml-2" variant="secondary" data-testid="li-saved-current-price-diff">Current price differs</Badge>}
                  </div>
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
