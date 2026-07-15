import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { centsToDollarsString, parseDollarsToCents } from "@/lib/format";
import { PRICE_DISPLAY_MODES, PRICE_DISPLAY_LABELS } from "@/lib/decisionRoom";
import { Link2, Unlink } from "lucide-react";

/**
 * EC10 Phase 10D — pricing reference section of a Decision Option editor.
 * Never calculates anything: `manual_price_cents` is a human-typed value,
 * `suggested_price_cents` is only ever a frozen copy from an EC9
 * `PricingSnapshotRecord` (attached by id, never recalculated here), and
 * `selected_display_price_cents` is computed and returned by the backend.
 */
export default function DecisionOptionPricingSection({ option, onChange, onAttachSnapshot, onDetachSnapshot, testIdPrefix }) {
  return (
    <div className="grid gap-2 rounded-lg border border-dashed p-3" data-testid={`${testIdPrefix}-pricing`}>
      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5">
          <Label className="text-xs">Price display</Label>
          <Select value={option.price_display_mode} onValueChange={(v) => onChange({ price_display_mode: v })}>
            <SelectTrigger data-testid={`${testIdPrefix}-price-display-mode-select`}><SelectValue /></SelectTrigger>
            <SelectContent>{PRICE_DISPLAY_MODES.map((m) => <SelectItem key={m} value={m}>{PRICE_DISPLAY_LABELS[m]}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Selected price source</Label>
          <Select value={option.selected_price_source} onValueChange={(v) => onChange({ selected_price_source: v })}>
            <SelectTrigger data-testid={`${testIdPrefix}-price-source-select`}><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="manual">Manual price</SelectItem>
              <SelectItem value="snapshot" disabled={!option.pricing_snapshot_id}>Pricing snapshot</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 items-end">
        <div className="grid gap-1.5">
          <Label className="text-xs">Manual price</Label>
          <Input
            value={option.manual_price_cents != null ? centsToDollarsString(option.manual_price_cents).replace("$", "") : ""}
            onChange={(e) => onChange({ manual_price_cents: e.target.value === "" ? null : parseDollarsToCents(e.target.value) })}
            placeholder="0.00" data-testid={`${testIdPrefix}-manual-price-input`}
          />
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Pricing snapshot</Label>
          {option.pricing_snapshot_id ? (
            <div className="flex items-center gap-2">
              <span className="text-xs rounded bg-muted px-2 py-1 truncate" data-testid={`${testIdPrefix}-pricing-snapshot-id`}>
                {option.pricing_snapshot_id} · {option.suggested_price_cents != null ? centsToDollarsString(option.suggested_price_cents) : "—"}
              </span>
              <Button type="button" size="icon" variant="ghost" onClick={onDetachSnapshot} data-testid={`${testIdPrefix}-detach-snapshot-button`}><Unlink className="size-4" /></Button>
            </div>
          ) : (
            <AttachSnapshotInput onAttach={onAttachSnapshot} testIdPrefix={testIdPrefix} />
          )}
        </div>
      </div>
      <div className="text-xs text-muted-foreground">
        Displayed price (backend-computed): <span className="font-medium tabular-nums" data-testid={`${testIdPrefix}-displayed-price`}>
          {option.selected_display_price_cents != null ? centsToDollarsString(option.selected_display_price_cents) : "Not set"}
        </span>
      </div>
    </div>
  );
}

function AttachSnapshotInput({ onAttach, testIdPrefix }) {
  const [val, setVal] = useState("");
  return (
    <div className="flex items-center gap-2">
      <Input value={val} onChange={(e) => setVal(e.target.value)} placeholder="Pricing snapshot id" className="text-xs" data-testid={`${testIdPrefix}-pricing-snapshot-input`} />
      <Button type="button" size="icon" variant="outline" disabled={!val.trim()} onClick={() => { onAttach(val.trim()); setVal(""); }} data-testid={`${testIdPrefix}-attach-snapshot-button`}>
        <Link2 className="size-4" />
      </Button>
    </div>
  );
}
