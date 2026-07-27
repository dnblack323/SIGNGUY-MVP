import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, Loader2, RefreshCw, SlidersHorizontal } from "lucide-react";
import api, { extractError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import PageHeader from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import MoneyInput from "@/components/forms/MoneyInput";
import SavedItemSelector from "@/components/pricing/selectors/SavedItemSelector";
import MaterialProfileSelector from "@/components/pricing/selectors/MaterialProfileSelector";
import PricingComponentSelector from "@/components/pricing/selectors/PricingComponentSelector";
import { CategorySpecificFields } from "@/components/pricing/CategorySpecificFields";

const DIMENSIONLESS_CATEGORIES = ["apparel", "promotional", "vehicle_graphics", "services", "custom"];
const CATEGORY_SPECIFIC_CATEGORIES = ["banners", "rigid_signs", "digital_print", "cut_vinyl", "apparel", "promotional", "vehicle_graphics", "services", "custom"];
const BANNER_METHOD_IDS = ["square_foot_plus_addons", "cost_plus", "target_margin", "materials_labor_overhead", "minimum_charge"];

const FALLBACK_CATEGORY_META = {
  banners: { name: "Banners" },
  rigid_signs: { name: "Rigid Signs" },
  cut_vinyl: { name: "Cut Vinyl" },
  digital_print: { name: "Digital Print" },
  vehicle_graphics: { name: "Vehicle Graphics" },
  apparel: { name: "Apparel" },
  promotional: { name: "Promotional" },
  services: { name: "Services" },
  custom: { name: "Custom" },
};

const DEFAULT_FORM = {
  category: "banners",
  width_inches: 96,
  height_inches: 36,
  quantity: 1,
  material_key: "",
  design_needed: false,
  install_needed: false,
  manual_selling_price: null,
  category_inputs: { dimension_unit: "in" },
};

const fmtUSD = (n) => (n == null ? "Unavailable" : Number(n || 0).toLocaleString("en-US", { style: "currency", currency: "USD" }));
const fmtPct = (n) => (n == null ? "Unavailable" : `${Number(n || 0).toFixed(2)}%`);
const humanize = (value) => String(value || "").replace(/_/g, " ");
const dimensionUnit = (inputs) => inputs?.dimension_unit || "in";
const normalizeDimension = (value, unit) => (unit === "ft" ? (Number(value) || 0) * 12 : Number(value) || 0);
const inputValue = (value) => (value == null ? "" : value);

function sectionValue(line) {
  if (line?.amount != null) return fmtUSD(line.amount);
  if (line?.value != null) {
    if (typeof line.value === "object") return JSON.stringify(line.value);
    return String(line.value);
  }
  if (line?.message) return line.message;
  return "";
}

function methodRowId(row) {
  return row?.method_id || row?.method;
}

function methodStatusText(row) {
  if (Array.isArray(row?.status)) return row.status.join(", ");
  if (row?.status) return String(row.status);
  return "status unavailable";
}

function PricingSummaryTile({ label, value, hint, testId }) {
  return (
    <div className="rounded-lg border bg-background p-3 min-h-[96px]">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold tabular-nums" data-testid={testId}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

function CategoryTabs({ categories, activeCategory, onSelect }) {
  return (
    <div className="border-b overflow-x-auto" data-testid="pricing-calculator-tabs">
      <div className="flex min-w-max gap-1">
        {categories.map(([id, meta]) => (
          <button
            key={id}
            type="button"
            onClick={() => onSelect(id)}
            className={`px-3 py-2 text-sm border-b-2 transition-colors ${activeCategory === id ? "border-primary text-foreground font-medium" : "border-transparent text-muted-foreground hover:text-foreground"}`}
            data-testid={`pricing-tab-${id}`}
          >
            {meta.name || humanize(id)}
          </button>
        ))}
      </div>
    </div>
  );
}

function WorkspaceRibbon({ activeView, setActiveView, onCalculate, calculating, canWrite, onPreviewSimple, previewing }) {
  return (
    <div className="rounded-lg border bg-muted/30 px-3 py-2" data-testid="pricing-calculator-ribbon">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={onCalculate} disabled={calculating} data-testid="calc-run-button">
          {calculating ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Calculator className="mr-2 size-4" />}
          Calculate
        </Button>
        <Button
          size="sm"
          variant={activeView === "calculator" ? "secondary" : "ghost"}
          onClick={() => setActiveView("calculator")}
          data-testid="calc-view-calculator"
        >
          Calculator
        </Button>
        <Button
          size="sm"
          variant={activeView === "methods" ? "secondary" : "ghost"}
          onClick={() => setActiveView("methods")}
          data-testid="calc-view-methods"
        >
          <SlidersHorizontal className="mr-2 size-4" />
          Method Setup
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={onPreviewSimple}
          disabled={previewing}
          data-testid="calc-simple-preview-button"
        >
          {previewing ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
          Preview Simple Setup
        </Button>
        {!canWrite && <Badge variant="secondary" data-testid="calc-read-only-badge">Read-only setup</Badge>}
      </div>
    </div>
  );
}

export default function PricingCalculatorPage() {
  const { hasPerm } = useAuth();
  const queryClient = useQueryClient();
  const canCalculate = hasPerm("pricing:calculate");
  const canReadPricing = hasPerm("pricing:read") || canCalculate;
  const canWritePricing = hasPerm("pricing:write");

  const [activeView, setActiveView] = useState("calculator");
  const [form, setForm] = useState(DEFAULT_FORM);
  const [result, setResult] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [error, setError] = useState("");
  const [savedItem, setSavedItem] = useState(null);
  const [useSavedDefaults, setUseSavedDefaults] = useState(true);
  const [tierPreview, setTierPreview] = useState(null);
  const [materialProfileId, setMaterialProfileId] = useState(null);
  const [pricingComponentIds, setPricingComponentIds] = useState([]);
  const [resultUpdating, setResultUpdating] = useState(false);
  const [selectedComparisonMethod, setSelectedComparisonMethod] = useState("");
  const [advancedSelection, setAdvancedSelection] = useState(BANNER_METHOD_IDS.slice(0, 2));
  const [advancedPrimary, setAdvancedPrimary] = useState(BANNER_METHOD_IDS[0]);
  const resultKeyRef = useRef("");

  const settingsQuery = useQuery({
    queryKey: ["pricing-settings"],
    queryFn: async () => (await api.get("/pricing/settings")).data,
    enabled: canReadPricing,
  });

  const categories = useMemo(() => {
    const meta = settingsQuery.data?.category_meta || FALLBACK_CATEGORY_META;
    return Object.entries(meta).filter(([id]) => CATEGORY_SPECIFIC_CATEGORIES.includes(id));
  }, [settingsQuery.data]);

  const categoryMeta = settingsQuery.data?.category_meta || FALLBACK_CATEGORY_META;

  const materialOptions = useMemo(() => {
    const materials = settingsQuery.data?.materials || {};
    return Object.entries(materials)
      .filter(([, m]) => m.category === form.category)
      .map(([key, m]) => ({ key, label: `${m.name} - $${m.cost_per_sqft}/sqft cost` }));
  }, [settingsQuery.data, form.category]);

  const methodConfigQuery = useQuery({
    queryKey: ["pricing-method-configuration", form.category],
    queryFn: async () => {
      try {
        return (await api.get(`/pricing/settings/categories/${form.category}/method-configuration`)).data;
      } catch (err) {
        if (err?.response?.status === 404) return null;
        throw err;
      }
    },
    enabled: canReadPricing,
  });

  const availabilityQuery = useQuery({
    queryKey: ["pricing-method-availability", form.category, form.category_inputs, savedItem?.id],
    queryFn: async () => (await api.post(`/pricing/settings/categories/${form.category}/method-availability`, {
      category_inputs: calculatorCategoryInputs(),
      saved_item_id: savedItem?.id || null,
    })).data,
    enabled: canReadPricing,
  });

  const simplePreview = useMutation({
    mutationFn: async () => (await api.post(`/pricing/settings/categories/${form.category}/simple-setup/preview`)).data,
  });

  const applySimple = useMutation({
    mutationFn: async () => (await api.post(`/pricing/settings/categories/${form.category}/simple-setup/apply`, {
      expected_configuration_version: simplePreview.data?.current_configuration_version || methodConfigQuery.data?.configuration_version || null,
      replace_advanced: false,
    })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pricing-method-configuration"] }),
  });

  const saveAdvanced = useMutation({
    mutationFn: async () => (await api.put(`/pricing/settings/categories/${form.category}/advanced-setup`, {
      enabled_method_ids: advancedSelection,
      primary_method_id: advancedPrimary,
      comparison_order: advancedSelection,
      compare_automatically: true,
      method_configuration_refs: {},
      expected_configuration_version: methodConfigQuery.data?.configuration_version || null,
    })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pricing-method-configuration"] }),
  });

  useEffect(() => {
    const config = methodConfigQuery.data;
    if (config?.enabled_method_ids?.length) {
      setAdvancedSelection(config.enabled_method_ids);
      setAdvancedPrimary(config.primary_method_id || config.enabled_method_ids[0]);
    } else if (availabilityQuery.data?.available_method_ids?.length) {
      const recommended = availabilityQuery.data.available_method_ids.slice(0, 2);
      setAdvancedSelection(recommended);
      setAdvancedPrimary(recommended[0] || "");
    }
  }, [methodConfigQuery.data, availabilityQuery.data]);

  function calculatorCategoryInputs() {
    if (!CATEGORY_SPECIFIC_CATEGORIES.includes(form.category)) return {};
    if (DIMENSIONLESS_CATEGORIES.includes(form.category)) return form.category_inputs;
    const unit = dimensionUnit(form.category_inputs);
    return {
      ...form.category_inputs,
      dimension_unit: unit,
      entered_width: Number(form.width_inches) || 0,
      entered_height: Number(form.height_inches) || 0,
    };
  }

  function calculatorPayload(overrides = {}) {
    const next = { ...form, ...overrides };
    const unit = dimensionUnit(next.category_inputs);
    return {
      category: next.category,
      width_inches: DIMENSIONLESS_CATEGORIES.includes(next.category) ? null : normalizeDimension(next.width_inches, unit),
      height_inches: DIMENSIONLESS_CATEGORIES.includes(next.category) ? null : normalizeDimension(next.height_inches, unit),
      quantity: Number(next.quantity) || 1,
      material_key: next.material_key || null,
      design_needed: !!next.design_needed,
      install_needed: !!next.install_needed,
      manual_selling_price: next.manual_selling_price != null ? Number(next.manual_selling_price) : null,
      category_inputs: calculatorCategoryInputs(),
      material_profile_id: materialProfileId || null,
      pricing_component_ids: pricingComponentIds,
      saved_item_id: savedItem?.id || null,
    };
  }

  const calc = useMutation({
    mutationFn: async ({ silent = false, calculationKey, primaryMethodId } = {}) => {
      const payload = calculatorPayload();
      const pricingResult = (await api.post("/pricing/calculate", payload)).data;
      let comparisonResult = null;
      if (payload.category === "banners") {
        try {
          comparisonResult = (await api.post("/pricing/method-comparison", {
            ...payload,
            use_saved_configuration: true,
            primary_method_id: primaryMethodId || selectedComparisonMethod || undefined,
          })).data;
        } catch (err) {
          if (!silent) throw err;
        }
      }
      return { pricingResult, comparisonResult, calculationKey, silent };
    },
    onSuccess: async ({ pricingResult, comparisonResult, calculationKey }) => {
      resultKeyRef.current = calculationKey || JSON.stringify(calculatorPayload());
      setResult(pricingResult);
      setComparison(comparisonResult);
      setSelectedComparisonMethod(comparisonResult?.selected_method_id || "");
      setResultUpdating(false);
      setError("");
      if (savedItem?.default_pricing_method === "tier_pricing") {
        const tier = await api.get(`/pricing/saved-items/${savedItem.id}/tier-price`, { params: { quantity: Number(form.quantity) || 1 } });
        setTierPreview(tier.data);
      } else {
        setTierPreview(null);
      }
    },
    onError: (err) => {
      setResultUpdating(false);
      setError(extractError(err));
    },
  });

  const calcMutateRef = useRef(calc.mutate);
  useEffect(() => {
    calcMutateRef.current = calc.mutate;
  });

  useEffect(() => {
    if (!canCalculate || !form.category) return undefined;
    const hasValidDimensions = DIMENSIONLESS_CATEGORIES.includes(form.category) || (Number(form.width_inches) > 0 && Number(form.height_inches) > 0);
    if (!hasValidDimensions) {
      setResult(null);
      setComparison(null);
      setResultUpdating(false);
      resultKeyRef.current = "";
      return undefined;
    }
    const calculationKey = JSON.stringify(calculatorPayload());
    if (resultKeyRef.current && resultKeyRef.current !== calculationKey) {
      setResultUpdating(true);
    }
    const timer = setTimeout(() => calcMutateRef.current({ silent: true, calculationKey }), 450);
    return () => clearTimeout(timer);
  }, [form, materialProfileId, pricingComponentIds, savedItem?.id, canCalculate]); // eslint-disable-line react-hooks/exhaustive-deps

  function updateForm(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function setCategory(category) {
    setForm((current) => ({
      ...DEFAULT_FORM,
      category,
      quantity: current.quantity || DEFAULT_FORM.quantity,
      width_inches: DIMENSIONLESS_CATEGORIES.includes(category) ? DEFAULT_FORM.width_inches : current.width_inches || DEFAULT_FORM.width_inches,
      height_inches: DIMENSIONLESS_CATEGORIES.includes(category) ? DEFAULT_FORM.height_inches : current.height_inches || DEFAULT_FORM.height_inches,
    }));
    setSavedItem(null);
    setMaterialProfileId(null);
    setPricingComponentIds([]);
    setResult(null);
    setComparison(null);
    setError("");
    setSelectedComparisonMethod("");
  }

  function updateCategoryInput(key, value) {
    setForm((current) => ({ ...current, category_inputs: { ...(current.category_inputs || {}), [key]: value } }));
  }

  function applySavedItem(id, item) {
    setSavedItem(item);
    const shouldLoadDefaults = form.category !== "promotional" || useSavedDefaults;
    if (shouldLoadDefaults && item?.saved_config && Object.keys(item.saved_config).length) {
      setForm((current) => ({ ...current, ...item.saved_config }));
    }
  }

  function runCalculation() {
    if (!canCalculate) return;
    const hasValidDimensions = DIMENSIONLESS_CATEGORIES.includes(form.category) || (Number(form.width_inches) > 0 && Number(form.height_inches) > 0);
    if (!hasValidDimensions) {
      setResult(null);
      setComparison(null);
      setError("Enter valid dimensions before calculating.");
      return;
    }
    calc.mutate({ silent: false, calculationKey: JSON.stringify(calculatorPayload()) });
  }

  function selectBannerComparisonMethod(methodId) {
    setSelectedComparisonMethod(methodId);
    if (form.category === "banners") {
      calc.mutate({ silent: false, calculationKey: JSON.stringify(calculatorPayload()), primaryMethodId: methodId });
    }
  }

  function toggleAdvancedMethod(methodId) {
    setAdvancedSelection((current) => {
      const next = current.includes(methodId) ? current.filter((id) => id !== methodId) : [...current, methodId].slice(0, 3);
      if (!next.includes(advancedPrimary)) setAdvancedPrimary(next[0] || "");
      return next;
    });
  }

  const comparisonRows = comparison?.comparison_results || result?.pricing_method_results || [];
  const selectedRow = comparisonRows.find((row) => row.selected) || comparisonRows.find((row) => methodRowId(row) === selectedComparisonMethod);
  const canonicalMethod = comparison?.canonical_method_id || result?.canonical_method_id || result?.pricing_method_used || result?.selected_pricing_method;
  const selectedComparison = comparison?.selected_method_id || methodRowId(selectedRow) || canonicalMethod;
  const availableOtherRows = comparisonRows.filter((row) => methodRowId(row) !== selectedComparison && row.amount != null);
  const unavailableRows = [
    ...(result?.method_availability || []).filter((row) => !row.available),
    ...((comparison?.availability?.methods || []).filter((row) => !row.available)),
  ];
  const warnings = result?.calculation_warnings || result?.warnings || [];
  const errors = result?.errors || [];

  if (!canCalculate) {
    return (
      <div className="space-y-4" data-testid="pricing-calculator-page">
        <PageHeader title="Pricing Calculators" subtitle="Dedicated pricing workspace" />
        <Card data-testid="pricing-calculator-permission-denied">
          <CardContent className="py-8 text-sm text-muted-foreground">
            You do not have permission to calculate prices. Required permission: pricing:calculate.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="pricing-calculator-page">
      <PageHeader
        title="Pricing Calculators"
        subtitle="Dedicated calculator workspace for Banner and normalized EC9 categories."
        actions={<Badge variant="secondary">EC9 Phase 9I-E</Badge>}
      />

      <CategoryTabs categories={categories} activeCategory={form.category} onSelect={setCategory} />

      <WorkspaceRibbon
        activeView={activeView}
        setActiveView={setActiveView}
        onCalculate={runCalculation}
        calculating={calc.isPending}
        canWrite={canWritePricing}
        onPreviewSimple={() => simplePreview.mutate()}
        previewing={simplePreview.isPending}
      />

      {activeView === "calculator" ? (
        <div className="grid grid-cols-1 xl:grid-cols-[420px_minmax(0,1fr)] gap-4" data-testid="pricing-calculator-workspace">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Calculator Inputs</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-1.5">
                <Label htmlFor="calc-category-native">Category</Label>
                <select
                  id="calc-category-native"
                  value={form.category}
                  onChange={(event) => setCategory(event.target.value)}
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                  data-testid="calc-category-select"
                >
                  {categories.map(([id, meta]) => <option key={id} value={id}>{meta.name || humanize(id)}</option>)}
                </select>
              </div>

              <div className="grid gap-1.5">
                <Label>Saved/common item</Label>
                <SavedItemSelector value={savedItem?.id} onChange={applySavedItem} category={form.category} testIdPrefix="calc-saved-item" />
                {form.category === "promotional" && (
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Switch checked={useSavedDefaults} onCheckedChange={setUseSavedDefaults} data-testid="calc-promo-use-saved-defaults-switch" />
                    Use saved item defaults when selected
                  </label>
                )}
              </div>

              {DIMENSIONLESS_CATEGORIES.includes(form.category) ? (
                <div className="grid gap-1.5">
                  <Label>Quantity</Label>
                  <Input type="number" min="1" value={form.quantity} onChange={(event) => updateForm("quantity", event.target.value)} data-testid="calc-quantity-input" />
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5">
                    <Label>Width ({dimensionUnit(form.category_inputs)})</Label>
                    <Input type="number" min="0" value={form.width_inches} onChange={(event) => updateForm("width_inches", event.target.value)} data-testid="calc-width-input" />
                  </div>
                  <div className="grid gap-1.5">
                    <Label>Height ({dimensionUnit(form.category_inputs)})</Label>
                    <Input type="number" min="0" value={form.height_inches} onChange={(event) => updateForm("height_inches", event.target.value)} data-testid="calc-height-input" />
                  </div>
                  <div className="grid gap-1.5">
                    <Label>Unit</Label>
                    <select
                      value={dimensionUnit(form.category_inputs)}
                      onChange={(event) => updateCategoryInput("dimension_unit", event.target.value)}
                      className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                      data-testid="calc-dimension-unit-select"
                    >
                      <option value="in">Inches</option>
                      <option value="ft">Feet</option>
                    </select>
                  </div>
                  <div className="grid gap-1.5">
                    <Label>Quantity</Label>
                    <Input type="number" min="1" value={form.quantity} onChange={(event) => updateForm("quantity", event.target.value)} data-testid="calc-quantity-input" />
                  </div>
                </div>
              )}

              {materialOptions.length > 0 && !DIMENSIONLESS_CATEGORIES.includes(form.category) && (
                <div className="grid gap-1.5">
                  <Label>Material</Label>
                  <select
                    value={form.material_key || ""}
                    onChange={(event) => updateForm("material_key", event.target.value)}
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                    data-testid="calc-material-select"
                  >
                    <option value="">Use category default</option>
                    {materialOptions.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                  </select>
                </div>
              )}

              {!DIMENSIONLESS_CATEGORIES.includes(form.category) && (
                <div className="flex flex-wrap items-center gap-5">
                  <label className="flex items-center gap-2 text-sm"><Switch checked={form.design_needed} onCheckedChange={(value) => updateForm("design_needed", value)} data-testid="calc-design-switch" />Design</label>
                  <label className="flex items-center gap-2 text-sm"><Switch checked={form.install_needed} onCheckedChange={(value) => updateForm("install_needed", value)} data-testid="calc-install-switch" />Install</label>
                </div>
              )}

              <CategorySpecificFields
                category={form.category}
                values={form.category_inputs}
                onChange={(next) => setForm((current) => ({ ...current, category_inputs: next }))}
                designNeeded={form.design_needed}
                installNeeded={form.install_needed}
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="grid gap-1.5">
                  <Label className="text-xs">Canonical material</Label>
                  <MaterialProfileSelector value={materialProfileId} onChange={setMaterialProfileId} category={form.category} testIdPrefix="calc-material-profile" />
                </div>
                <div className="grid gap-1.5">
                  <Label className="text-xs">Pricing components</Label>
                  <PricingComponentSelector value={pricingComponentIds} onChange={setPricingComponentIds} category={form.category} testIdPrefix="calc-components" />
                </div>
              </div>

              <div className="grid gap-1.5">
                <Label>Manual selling price override</Label>
                <MoneyInput value={form.manual_selling_price ? Math.round(form.manual_selling_price * 100) : 0} onChange={(cents) => updateForm("manual_selling_price", cents ? cents / 100 : null)} testId="calc-manual-override" />
              </div>
            </CardContent>
          </Card>

          <div className="space-y-4">
            {(calc.isPending || resultUpdating) && (
              <div className="rounded-lg border bg-muted/40 px-3 py-2 text-sm" data-testid="calc-loading-state">
                {calc.isPending ? "Calculating current price..." : "Inputs changed. Updating result..."}
              </div>
            )}

            {error && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive" data-testid="calc-error-state">
                {error}
              </div>
            )}

            {!result ? (
              <Card>
                <CardContent className="py-10 text-sm text-muted-foreground" data-testid="calc-empty-state">
                  {settingsQuery.isLoading ? "Loading pricing settings..." : "Enter inputs and calculate to see authoritative pricing, method output, details, warnings, and unavailable methods."}
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4" data-testid="calc-result">
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
                  <PricingSummaryTile label="Authoritative selling price" value={fmtUSD(result.selling_price)} hint={`Calculator method: ${humanize(result.pricing_method_used || result.selected_pricing_method)}`} testId="calc-authoritative-selling-price" />
                  <PricingSummaryTile label="Canonical method" value={humanize(canonicalMethod)} hint="Existing calculator authority" testId="calc-canonical-method" />
                  <PricingSummaryTile label="Selected comparison method" value={humanize(selectedComparison)} hint={selectedRow?.amount != null ? fmtUSD(selectedRow.amount) : "No available amount"} testId="calc-selected-comparison-method" />
                  <PricingSummaryTile label="Profit margin" value={fmtPct(result.profit_margin_percent)} hint={result.profit_amount != null ? `${fmtUSD(result.profit_amount)} profit` : "Profit unavailable"} testId="calc-profit-margin" />
                </div>

                {warnings.length > 0 && (
                  <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800 space-y-1" data-testid="calc-warnings-banner">
                    {warnings.map((warning, index) => <div key={`${warning}-${index}`}>{warning}</div>)}
                  </div>
                )}
                {errors.length > 0 && (
                  <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive space-y-1" data-testid="calc-result-errors">
                    {errors.map((item, index) => <div key={`${item}-${index}`}>{item}</div>)}
                  </div>
                )}
                {tierPreview && (
                  <div className="rounded-lg border p-3 text-xs" data-testid="calc-tier-preview">
                    {tierPreview.matched
                      ? <span>Exact tier match for qty {tierPreview.quantity}: <strong className="tabular-nums">{fmtUSD(tierPreview.price)}</strong></span>
                      : <span className="text-amber-700">No configured tier for qty {tierPreview.quantity}. No replacement price was guessed.</span>}
                  </div>
                )}

                <Card>
                  <CardHeader><CardTitle className="text-base">Method Results</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid gap-2" data-testid="calc-method-results">
                      {comparisonRows.map((row) => {
                        const id = methodRowId(row);
                        const isBanner = form.category === "banners";
                        const selected = id === selectedComparison;
                        return (
                          <button
                            key={id}
                            type="button"
                            onClick={() => isBanner && selectBannerComparisonMethod(id)}
                            disabled={!isBanner}
                            className={`rounded-lg border p-3 text-left ${selected ? "border-primary bg-primary/5" : "bg-background"} ${isBanner ? "hover:bg-muted/50" : ""}`}
                            data-testid={`calc-method-${id}`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div>
                                <div className="font-medium">{row.display_name || row.label || humanize(id)}</div>
                                <div className="text-xs text-muted-foreground">{methodStatusText(row)}</div>
                              </div>
                              <div className="text-lg font-semibold tabular-nums">{fmtUSD(row.amount)}</div>
                            </div>
                          </button>
                        );
                      })}
                    </div>

                    {availableOtherRows.length > 0 && (
                      <div className="text-xs text-muted-foreground" data-testid="calc-other-method-results">
                        Other available results: {availableOtherRows.map((row) => `${row.display_name || row.label || humanize(methodRowId(row))} ${fmtUSD(row.amount)}`).join("; ")}
                      </div>
                    )}

                    {unavailableRows.length > 0 && (
                      <div className="rounded-lg border bg-muted/30 p-3 text-xs" data-testid="calc-unavailable-methods">
                        <div className="font-medium text-foreground">Unavailable or unsupported methods</div>
                        <div className="mt-1 grid gap-1 text-muted-foreground">
                          {unavailableRows.slice(0, 8).map((row) => (
                            <div key={`${row.method_id}-${row.reason || "unavailable"}`}>
                              {humanize(row.method_id)}: {row.reason || row.explanation || "unavailable"}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle className="text-base">Category Details</CardTitle></CardHeader>
                  <CardContent className="space-y-3" data-testid="calc-detail-sections">
                    {result.breakdown?.length > 0 && (
                      <div className="rounded-lg border">
                        <div className="border-b px-3 py-2 text-xs text-muted-foreground">Cost breakdown</div>
                        <div className="divide-y">
                          {result.breakdown.map((row, index) => (
                            <div key={`${row.label}-${index}`} className="flex items-center justify-between px-3 py-2 text-sm">
                              <span>{row.label}</span>
                              <span className="tabular-nums">{fmtUSD(row.amount)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {(result.detail_sections || []).map((section) => (
                      <details key={section.section} className="rounded-lg border p-3" open={section.section === "authoritative_result"}>
                        <summary className="cursor-pointer text-sm font-medium capitalize">{humanize(section.section)}</summary>
                        <div className="mt-2 grid gap-1 text-xs">
                          {(section.lines || []).map((line, index) => (
                            <div key={`${section.section}-${index}`} className="grid grid-cols-[minmax(120px,1fr)_minmax(120px,1fr)] gap-3 border-t py-1">
                              <span className="text-muted-foreground">{line.label || line.key || line.item || line.message || "Detail"}</span>
                              <span className="tabular-nums">{sectionValue(line)}</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    ))}
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="pricing-method-setup-panel">
          <Card>
            <CardHeader><CardTitle className="text-base">Current Method Setup</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div><span className="text-muted-foreground">Category:</span> {categoryMeta[form.category]?.name || humanize(form.category)}</div>
              <div><span className="text-muted-foreground">Configuration:</span> {methodConfigQuery.data ? `${methodConfigQuery.data.configuration_mode} v${methodConfigQuery.data.configuration_version}` : "Recommended defaults only"}</div>
              <div><span className="text-muted-foreground">Primary method:</span> {humanize(methodConfigQuery.data?.primary_method_id || availabilityQuery.data?.recommended_primary_method_id || "not configured")}</div>
              <div className="rounded-lg border bg-muted/30 p-3" data-testid="calc-method-availability">
                <div className="font-medium">Available methods</div>
                <div className="mt-2 grid gap-2">
                  {(availabilityQuery.data?.methods || []).map((row) => (
                    <label key={row.method_id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={advancedSelection.includes(row.method_id)}
                        disabled={!row.available || !canWritePricing}
                        onChange={() => toggleAdvancedMethod(row.method_id)}
                        data-testid={`calc-advanced-method-${row.method_id}`}
                      />
                      <span>{row.method?.display_name || row.display_name || humanize(row.method_id)}</span>
                      {!row.available && <span className="text-xs text-muted-foreground">({row.reason || "unavailable"})</span>}
                    </label>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Simple / Advanced Controls</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg border p-3 text-sm" data-testid="calc-simple-preview">
                <div className="font-medium">Simple setup preview</div>
                {simplePreview.data ? (
                  <div className="mt-2 text-xs text-muted-foreground">
                    Recommended methods: {(simplePreview.data.enabled_method_ids || simplePreview.data.recommended_method_ids || []).map(humanize).join(", ") || "none"}
                  </div>
                ) : (
                  <div className="mt-2 text-xs text-muted-foreground">Preview recommendations before applying them.</div>
                )}
                <div className="mt-3 flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => simplePreview.mutate()} disabled={simplePreview.isPending} data-testid="calc-simple-preview-inline-button">Preview</Button>
                  <Button size="sm" onClick={() => applySimple.mutate()} disabled={!canWritePricing || applySimple.isPending} data-testid="calc-simple-apply-button">Apply Simple Setup</Button>
                </div>
              </div>

              <div className="rounded-lg border p-3 text-sm" data-testid="calc-advanced-setup">
                <div className="font-medium">Advanced setup</div>
                <div className="mt-2 grid gap-2 text-xs">
                  <Label>Primary method</Label>
                  <select
                    value={advancedPrimary}
                    onChange={(event) => setAdvancedPrimary(event.target.value)}
                    disabled={!canWritePricing}
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                    data-testid="calc-advanced-primary-select"
                  >
                    {advancedSelection.map((id) => <option key={id} value={id}>{humanize(id)}</option>)}
                  </select>
                </div>
                <Button
                  className="mt-3"
                  size="sm"
                  onClick={() => saveAdvanced.mutate()}
                  disabled={!canWritePricing || !advancedSelection.length || !advancedPrimary || saveAdvanced.isPending}
                  data-testid="calc-advanced-save-button"
                >
                  Save Advanced Setup
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
