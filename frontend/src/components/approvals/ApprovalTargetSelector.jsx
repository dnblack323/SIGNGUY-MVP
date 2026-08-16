import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";

import api from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const APPROVAL_TARGET_TYPES = [
  { value: "customer", label: "Customer" },
  { value: "quote", label: "Quote" },
  { value: "quote_line_item", label: "Quote line item" },
  { value: "order", label: "Order" },
  { value: "order_item", label: "Order item" },
];

export function approvalTargetTypeLabel(type) {
  return APPROVAL_TARGET_TYPES.find((t) => t.value === type)?.label || type || "Target";
}

export default function ApprovalTargetSelector({
  targetType,
  selectedTarget,
  onSelect,
  disabled = false,
  enabled = true,
  testIdPrefix = "approval-target",
}) {
  const [search, setSearch] = useState("");

  const targets = useQuery({
    queryKey: ["approval-center-targets", targetType, search],
    queryFn: async () => (await api.get("/approval-center/targets", {
      params: { target_type: targetType, search: search || undefined, limit: 20 },
    })).data,
    enabled: enabled && !disabled && Boolean(targetType),
  });

  const targetItems = targets.data?.items || [];

  return (
    <div className="grid gap-2">
      <div className="grid gap-1.5">
        <Label className="text-xs">Search target</Label>
        <div className="relative">
          <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
          <Input
            className="pl-8"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={`Search ${approvalTargetTypeLabel(targetType).toLowerCase()}s`}
            disabled={disabled}
            data-testid={`${testIdPrefix}-search`}
          />
        </div>
      </div>
      <div className="rounded-md border divide-y max-h-52 overflow-auto" data-testid={`${testIdPrefix}-results`}>
        {selectedTarget && (
          <div className="flex items-center justify-between gap-3 p-3 bg-primary/5">
            <div>
              <div className="text-sm font-medium">{selectedTarget.label || selectedTarget.title || selectedTarget.id}</div>
              <div className="text-xs text-muted-foreground">
                {selectedTarget.subtitle || selectedTarget.customer_name || `Selected ${approvalTargetTypeLabel(selectedTarget.target_type || targetType)}`}
              </div>
            </div>
            <Badge variant="outline">Selected</Badge>
          </div>
        )}
        {targetItems.length === 0 && !selectedTarget ? (
          <div className="p-3 text-sm text-muted-foreground">No matching targets.</div>
        ) : targetItems.map((target) => (
          <button
            key={`${target.target_type}:${target.id}`}
            type="button"
            className="w-full text-left p-3 hover:bg-muted focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => onSelect(target)}
            disabled={disabled}
            data-testid={`${testIdPrefix}-${target.target_type}-${target.id}`}
          >
            <div className="text-sm font-medium">{target.label}</div>
            <div className="text-xs text-muted-foreground">{target.subtitle || target.customer_name || target.id}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
