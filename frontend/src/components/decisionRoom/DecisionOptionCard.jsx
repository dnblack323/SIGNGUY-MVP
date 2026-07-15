import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusPill } from "@/components/common/StatusPill";
import DecisionOptionPricingSection from "@/components/decisionRoom/DecisionOptionPricingSection";
import DecisionOptionMediaSection from "@/components/decisionRoom/DecisionOptionMediaSection";
import { BADGE_TYPES, BADGE_LABELS } from "@/lib/decisionRoom";
import { ArrowDown, ArrowUp, Copy, Archive, ArchiveRestore } from "lucide-react";

function linesToList(text) {
  return text.split("\n").map((s) => s.trim()).filter(Boolean);
}

/**
 * EC10 Phase 10D — one customer-facing comparison card, in staff-authoring
 * form. `onChange(patch)` PATCHes just the changed fields (backend merges
 * and recomputes `selected_display_price_cents`/badge-exclusivity itself —
 * this component never computes or enforces those locally).
 */
export default function DecisionOptionCard({
  option, disabled, onChange, onDuplicate, onArchiveToggle, onMoveUp, onMoveDown,
  onAttachSnapshot, onDetachSnapshot, onAttachField, onDetachField, canMoveUp, canMoveDown, testIdPrefix,
}) {
  return (
    <div
      className={`rounded-xl border bg-card p-4 grid gap-3 ${option.active === false ? "opacity-60" : ""}`}
      data-testid={testIdPrefix}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusPill kind="decision_badge" value={option.badge_type} />
          {option.active === false && <span className="text-xs text-muted-foreground">Archived</span>}
        </div>
        {!disabled && (
          <div className="flex items-center gap-1">
            <Button size="icon" variant="ghost" onClick={onMoveUp} disabled={!canMoveUp} data-testid={`${testIdPrefix}-move-up-button`}><ArrowUp className="size-4" /></Button>
            <Button size="icon" variant="ghost" onClick={onMoveDown} disabled={!canMoveDown} data-testid={`${testIdPrefix}-move-down-button`}><ArrowDown className="size-4" /></Button>
            <Button size="icon" variant="ghost" onClick={onDuplicate} data-testid={`${testIdPrefix}-duplicate-button`}><Copy className="size-4" /></Button>
            <Button size="icon" variant="ghost" onClick={onArchiveToggle} data-testid={`${testIdPrefix}-archive-toggle-button`}>
              {option.active === false ? <ArchiveRestore className="size-4" /> : <Archive className="size-4" />}
            </Button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5">
          <Label className="text-xs">Customer label</Label>
          <Input disabled={disabled} value={option.customer_label || ""} onChange={(e) => onChange({ customer_label: e.target.value })} data-testid={`${testIdPrefix}-customer-label-input`} />
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Internal name</Label>
          <Input disabled={disabled} value={option.internal_name || ""} onChange={(e) => onChange({ internal_name: e.target.value })} data-testid={`${testIdPrefix}-internal-name-input`} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5">
          <Label className="text-xs">Badge</Label>
          <Select disabled={disabled} value={option.badge_type} onValueChange={(v) => onChange({ badge_type: v })}>
            <SelectTrigger data-testid={`${testIdPrefix}-badge-select`}><SelectValue /></SelectTrigger>
            <SelectContent>{BADGE_TYPES.map((b) => <SelectItem key={b} value={b}>{BADGE_LABELS[b]}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        {option.badge_type === "custom" && (
          <div className="grid gap-1.5">
            <Label className="text-xs">Custom badge text</Label>
            <Input disabled={disabled} value={option.custom_badge_text || ""} onChange={(e) => onChange({ custom_badge_text: e.target.value })} data-testid={`${testIdPrefix}-custom-badge-input`} />
          </div>
        )}
      </div>

      <div className="grid gap-1.5">
        <Label className="text-xs">Headline</Label>
        <Input disabled={disabled} value={option.headline || ""} onChange={(e) => onChange({ headline: e.target.value })} data-testid={`${testIdPrefix}-headline-input`} />
      </div>
      <div className="grid gap-1.5">
        <Label className="text-xs">Customer-safe description</Label>
        <Textarea disabled={disabled} rows={2} value={option.customer_safe_description || ""} onChange={(e) => onChange({ customer_safe_description: e.target.value })} data-testid={`${testIdPrefix}-description-input`} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5">
          <Label className="text-xs">Included features (one per line)</Label>
          <Textarea disabled={disabled} rows={3} value={(option.included_features || []).join("\n")} onChange={(e) => onChange({ included_features: linesToList(e.target.value) })} data-testid={`${testIdPrefix}-included-features-input`} />
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Excluded features (one per line)</Label>
          <Textarea disabled={disabled} rows={3} value={(option.excluded_features || []).join("\n")} onChange={(e) => onChange({ excluded_features: linesToList(e.target.value) })} data-testid={`${testIdPrefix}-excluded-features-input`} />
        </div>
      </div>

      <div className="grid gap-1.5">
        <Label className="text-xs">Expected timing</Label>
        <Input disabled={disabled} value={option.expected_timing || ""} onChange={(e) => onChange({ expected_timing: e.target.value })} placeholder="e.g. Ready in 3-5 business days" data-testid={`${testIdPrefix}-timing-input`} />
      </div>

      <DecisionOptionPricingSection option={option} onChange={onChange} onAttachSnapshot={onAttachSnapshot} onDetachSnapshot={onDetachSnapshot} testIdPrefix={testIdPrefix} />
      <DecisionOptionMediaSection option={option} onFilesChange={(ids) => onChange({ file_ids: ids })} onAttachField={onAttachField} onDetachField={onDetachField} testIdPrefix={testIdPrefix} />

      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5">
          <Label className="text-xs">Internal notes (staff only)</Label>
          <Textarea disabled={disabled} rows={2} value={option.internal_notes || ""} onChange={(e) => onChange({ internal_notes: e.target.value })} data-testid={`${testIdPrefix}-internal-notes-input`} />
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Customer-safe notes</Label>
          <Textarea disabled={disabled} rows={2} value={option.customer_safe_notes || ""} onChange={(e) => onChange({ customer_safe_notes: e.target.value })} data-testid={`${testIdPrefix}-customer-notes-input`} />
        </div>
      </div>
    </div>
  );
}
