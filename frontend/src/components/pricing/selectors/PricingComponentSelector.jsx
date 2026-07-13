import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

/**
 * EC9 Phase 9D — reusable non-inventory Pricing Component multi-selector.
 * Shared component prepared for later Order Item / calculator integration
 * (Phase 9E/9F) — only mounted in the Pricing Foundation area for now.
 */
export default function PricingComponentSelector({ value = [], onChange, category, testIdPrefix = "component-selector" }) {
  const { data } = useQuery({
    queryKey: ["pricing-components-active"],
    queryFn: async () => (await api.get("/pricing/components", { params: { active: true } })).data,
  });
  const items = (data?.items || []).filter((c) => !category || !c.category_applicability?.length || c.category_applicability.includes(category));

  const toggle = (id) => {
    const next = value.includes(id) ? value.filter((v) => v !== id) : [...value, id];
    onChange?.(next);
  };

  if (items.length === 0) {
    return <p className="text-xs text-muted-foreground">No pricing components yet — create one under Pricing Components.</p>;
  }

  return (
    <div className="grid gap-2" data-testid={`${testIdPrefix}-list`}>
      {items.map((c) => (
        <label key={c.id} className="flex items-center gap-2 text-sm cursor-pointer" data-testid={`${testIdPrefix}-item-${c.id}`}>
          <Checkbox checked={value.includes(c.id)} onCheckedChange={() => toggle(c.id)} />
          <span className="flex-1">{c.name}</span>
          <Badge variant="secondary" className="text-[10px] capitalize">{c.charge_type.replace(/_/g, " ")}</Badge>
        </label>
      ))}
    </div>
  );
}
