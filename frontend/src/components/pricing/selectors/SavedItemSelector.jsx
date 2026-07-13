import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus } from "lucide-react";

/**
 * EC9 Phase 9D — reusable Saved/Common Item selector. Returns the FULL saved
 * item object via `onChange(itemId, item)` so callers (calculator today;
 * Order Item entry in Phase 9F) can decide whether to prefill from it
 * ("use saved defaults yes/no" contract) — never auto-applies anything.
 * `onAddNew` opens the caller's own "Add New" shortcut (e.g. calculator's
 * save-as-new flow) since creation always happens from a priced context.
 */
export default function SavedItemSelector({ value, onChange, category, quickSelectOnly = false, onAddNew, testIdPrefix = "saved-item-selector" }) {
  const { data } = useQuery({
    queryKey: ["pricing-saved-items-active", category || "all", quickSelectOnly],
    queryFn: async () => (await api.get("/pricing/saved-items", {
      params: { active: true, ...(category ? { category } : {}), ...(quickSelectOnly ? { quick_select: true } : {}) },
    })).data,
  });
  const items = data?.items || [];

  return (
    <div className="flex items-center gap-2">
      <Select value={value || "__none__"} onValueChange={(v) => onChange?.(v === "__none__" ? null : v, items.find((i) => i.id === v) || null)}>
        <SelectTrigger data-testid={`${testIdPrefix}-select`}><SelectValue placeholder="One-time / custom item" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="__none__">One-time / custom item (no saved item)</SelectItem>
          {items.map((i) => (
            <SelectItem key={i.id} value={i.id}>
              {i.name}{i.quick_select ? " ★" : ""}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {onAddNew && (
        <Button type="button" variant="outline" size="icon" onClick={onAddNew} data-testid={`${testIdPrefix}-add-new-button`}>
          <Plus className="size-4" />
        </Button>
      )}
      {quickSelectOnly && items.some((i) => i.quick_select) && <Badge variant="secondary" className="text-[10px]">Quick-select</Badge>}
    </div>
  );
}
