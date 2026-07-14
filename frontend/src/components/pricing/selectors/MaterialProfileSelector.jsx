import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

/**
 * EC9 Phase 9F/9G — reusable canonical Material Pricing Profile selector.
 * Extracted from `LineItemDialog.jsx` (Phase 9F) so the standalone Pricing
 * Calculator can reuse the EXACT same selector/data-contract instead of a
 * duplicate (Phase 9G §2). Resolves to a `MaterialPricingProfile.id`, which
 * is what the pricing resolver (`services/order_pricing.py`) expects as
 * `material_profile_id` — never a raw canonical `Material.id`.
 */
export default function MaterialProfileSelector({ value, onChange, category, testIdPrefix = "material-profile-selector" }) {
  const { data: profiles } = useQuery({
    queryKey: ["material-profiles-active-all"],
    queryFn: async () => (await api.get("/pricing/material-profiles", { params: { active: true } })).data,
  });
  const { data: materials } = useQuery({
    queryKey: ["materials-active-all"],
    queryFn: async () => (await api.get("/materials", { params: { active: true } })).data,
  });
  const matById = useMemo(() => new Map((materials?.items || []).map((m) => [m.id, m])), [materials]);
  const items = (profiles?.items || []).filter((p) => !category || !p.category_applicability?.length || p.category_applicability.includes(category));

  return (
    <Select value={value || "__none__"} onValueChange={(v) => onChange?.(v === "__none__" ? null : v)}>
      <SelectTrigger data-testid={`${testIdPrefix}-select`}><SelectValue placeholder="No canonical material" /></SelectTrigger>
      <SelectContent>
        <SelectItem value="__none__">No canonical material</SelectItem>
        {items.map((p) => (
          <SelectItem key={p.id} value={p.id}>
            {matById.get(p.material_id)?.name || p.material_id} — ${p.suggested_sell_rate ?? p.normalized_cost_basis ?? 0}/{p.pricing_unit}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
