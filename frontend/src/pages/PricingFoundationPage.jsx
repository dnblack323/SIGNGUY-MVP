import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Wand2, RotateCcw, Save, CircleCheck, AlertCircle, Info } from "lucide-react";
import CategorySetupWizard from "@/components/pricing/CategorySetupWizard";
import GroupedPricingQuiz from "@/components/pricing/GroupedPricingQuiz";
import { WIZARD_CONFIGS } from "@/components/pricing/wizardConfigs";
import { useAuth } from "@/auth/AuthContext";

const SHOP_FIELDS = [
  ["design_hourly_rate", "Design hourly rate", "$/hr"],
  ["production_hourly_rate", "Production hourly rate", "$/hr"],
  ["install_hourly_rate", "Install hourly rate", "$/hr"],
  ["removal_hourly_rate", "Removal hourly rate", "$/hr"],
  ["travel_hourly_rate", "Travel hourly rate", "$/hr"],
  ["admin_hourly_rate", "Admin / project handling rate", "$/hr"],
  ["consultation_hourly_rate", "Consultation hourly rate", "$/hr"],
  ["site_survey_hourly_rate", "Site survey hourly rate", "$/hr"],
  ["finishing_hourly_rate", "Finishing hourly rate", "$/hr"],
  ["default_overhead_percent", "Default overhead", "%"],
  ["labor_burden_percent", "Labor burden", "%"],
  ["target_profit_margin_percent", "Target profit margin", "%"],
  ["minimum_order_amount", "Minimum order", "$"],
  ["install_minimum_charge", "Install minimum (Pricing Foundation fallback)", "$"],
  ["setup_fee_default", "Setup fee (Pricing Foundation fallback)", "$"],
  ["rush_fee_percent", "Rush fee (Pricing Foundation fallback)", "%"],
  ["deposit_percentage", "Deposit", "%"],
  ["default_markup_multiplier", "Default markup", "×"],
];

function StatusBadge({ cat }) {
  if (cat?.setup_complete) return <Badge className="bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200 hover:bg-emerald-100"><CircleCheck className="size-3 mr-1" />Setup complete</Badge>;
  if (cat?.needs_tenant_setup) return <Badge className="bg-amber-100 text-amber-900 ring-1 ring-amber-200 hover:bg-amber-100"><AlertCircle className="size-3 mr-1" />Needs review</Badge>;
  return <Badge variant="secondary"><Info className="size-3 mr-1" />Using starter defaults</Badge>;
}

function CategoryCard({ id, cat, meta, onSetup, onReset }) {
  const rateLine = cat?.base_sell_rate_per_sqft ? `$${cat.base_sell_rate_per_sqft}/sqft` : (cat?.default_markup_multiplier ? `${cat.default_markup_multiplier}× markup` : "—");
  return (
    <Card className="flex flex-col" data-testid={`category-card-${id}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{meta?.name || id}</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">{meta?.description}</p>
          </div>
          <StatusBadge cat={cat} />
        </div>
      </CardHeader>
      <CardContent className="flex-1 space-y-1 text-sm">
        <div className="flex items-center justify-between"><span className="text-muted-foreground">Method</span><span className="capitalize">{String(cat?.pricing_method || "—").replace("_", " ")}</span></div>
        <div className="flex items-center justify-between"><span className="text-muted-foreground">Rate/markup</span><span className="tabular-nums">{rateLine}</span></div>
        <div className="flex items-center justify-between"><span className="text-muted-foreground">Min charge</span><span className="tabular-nums">{cat?.minimum_charge != null ? `$${cat.minimum_charge}` : "—"}</span></div>
      </CardContent>
      <div className="px-6 pb-4 flex items-center gap-2">
        <Button size="sm" variant="outline" onClick={onSetup} data-testid={`category-setup-${id}`}><Wand2 className="size-4 mr-1" />{cat?.setup_complete ? "Edit setup" : "Set up category"}</Button>
        <Button size="sm" variant="ghost" onClick={onReset} data-testid={`category-reset-${id}`}><RotateCcw className="size-4 mr-1" />Reset</Button>
      </div>
    </Card>
  );
}

export default function PricingFoundationPage() {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("pricing:write");

  const { data: settings, isLoading } = useQuery({
    queryKey: ["pricing-settings"],
    queryFn: async () => (await api.get("/pricing/settings")).data,
  });

  const [shopForm, setShopForm] = useState({});
  const [wizardCat, setWizardCat] = useState(null);
  const [quizOpen, setQuizOpen] = useState(false);

  const currentShop = useMemo(() => ({ ...(settings?.shop_defaults || {}), ...shopForm }), [settings, shopForm]);

  const saveShop = useMutation({
    mutationFn: async () => (await api.patch("/pricing/settings/shop-defaults", shopForm)).data,
    onSuccess: () => { toast.success("Shop defaults saved"); qc.invalidateQueries({ queryKey: ["pricing-settings"] }); setShopForm({}); },
    onError: (e) => toast.error(extractError(e)),
  });
  const resetCategory = useMutation({
    mutationFn: async (cid) => (await api.post(`/pricing/settings/categories/${cid}/reset`)).data,
    onSuccess: () => { toast.success("Category reset to starter defaults"); qc.invalidateQueries({ queryKey: ["pricing-settings"] }); },
    onError: (e) => toast.error(extractError(e)),
  });

  if (isLoading || !settings) return <div className="text-sm text-muted-foreground">Loading…</div>;

  return (
    <div className="space-y-6" data-testid="pricing-foundation-page">
      <PageHeader
        title="Pricing Foundation"
        subtitle="Shop defaults + per-category setup. Run the wizards to tailor these values to your shop."
        actions={canWrite ? (
          <Button variant="outline" onClick={() => setQuizOpen(true)} data-testid="open-grouped-quiz-button">
            <Wand2 className="size-4 mr-1" />Quick Setup (Grouped Quiz)
          </Button>
        ) : null}
      />

      <div className="rounded-lg border bg-accent/40 p-4 flex gap-3 items-start" data-testid="starter-notice">
        <Info className="size-4 mt-0.5 text-muted-foreground shrink-0" />
        <div className="text-sm text-muted-foreground">
          You’re starting with SignGuy AI recommended shop defaults (version <span className="mono">{settings.starter_default_version}</span>). Run the setup wizards below to tailor these values to your shop. Every change is per-tenant — the starter template stays untouched.
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle>Shop defaults</CardTitle>
            {canWrite && Object.keys(shopForm).length > 0 && (
              <Button size="sm" onClick={() => saveShop.mutate()} disabled={saveShop.isPending} data-testid="shop-defaults-save-button">
                <Save className="size-4 mr-1" />Save shop defaults
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {SHOP_FIELDS.map(([key, label, unit]) => (
            <div key={key} className="grid gap-1.5">
              <Label className="text-xs">{label} <span className="text-muted-foreground">({unit})</span></Label>
              <Input
                type="number" step="0.01" inputMode="decimal"
                value={currentShop[key] ?? ""} disabled={!canWrite}
                onChange={(e) => setShopForm((f) => ({ ...f, [key]: e.target.value === "" ? null : Number(e.target.value) }))}
                data-testid={`shop-defaults-${key}`}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold">Categories</h2>
          <p className="text-xs text-muted-foreground">One card per pricing category.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.keys(settings.category_defaults || {}).map((id) => (
            <CategoryCard
              key={id} id={id}
              cat={settings.category_defaults[id]}
              meta={settings.category_meta?.[id]}
              onSetup={() => canWrite && setWizardCat(id)}
              onReset={() => canWrite && confirm(`Reset '${id}' to starter defaults?`) && resetCategory.mutate(id)}
            />
          ))}
        </div>
      </div>

      {wizardCat && WIZARD_CONFIGS[wizardCat] && (
        <CategorySetupWizard
          open={!!wizardCat}
          onOpenChange={(o) => !o && setWizardCat(null)}
          categoryId={wizardCat}
          categoryConfig={WIZARD_CONFIGS[wizardCat]}
          currentSettings={settings}
          onApplied={() => qc.invalidateQueries({ queryKey: ["pricing-settings"] })}
        />
      )}

      <GroupedPricingQuiz
        open={quizOpen}
        onOpenChange={setQuizOpen}
        categoryOptions={Object.keys(settings.category_defaults || {}).map((id) => [id, settings.category_meta?.[id]?.name || id])}
      />
    </div>
  );
}
