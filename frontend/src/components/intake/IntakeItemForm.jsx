import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import SavedItemSelector from "@/components/pricing/selectors/SavedItemSelector";
import MaterialProfileSelector from "@/components/pricing/selectors/MaterialProfileSelector";
import FileAttachmentPicker from "@/components/intake/FileAttachmentPicker";
import StatusPill from "@/components/common/StatusPill";
import { INTAKE_CATEGORIES } from "@/lib/intake";

/**
 * EC10 Phase 10B — one Quick/Detailed intake item. Purely controlled — no
 * API calls here. Quick mode shows only the primary fields (§4); Detailed
 * mode reveals measurements, canonical Material references, and proof/
 * approval/installation flags (§5). Never renders a price field — pricing
 * remains owned by EC9 and (once the item is persisted) the Phase 10B
 * pricing-workflow-state fields, edited separately from the detail page.
 */
export default function IntakeItemForm({ item, onChange, detailed = false, testIdPrefix = "intake-item" }) {
  const set = (patch) => onChange({ ...item, ...patch });

  return (
    <div className="grid gap-3 rounded-lg border p-3" data-testid={testIdPrefix}>
      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5">
          <Label>Item name</Label>
          <Input value={item.item_name || ""} onChange={(e) => set({ item_name: e.target.value })} data-testid={`${testIdPrefix}-name-input`} />
        </div>
        <div className="grid gap-1.5">
          <Label>Category</Label>
          <Select value={item.category || "__none__"} onValueChange={(v) => set({ category: v === "__none__" ? "" : v })}>
            <SelectTrigger data-testid={`${testIdPrefix}-category-select`}><SelectValue placeholder="Choose category" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">Choose category</SelectItem>
              {INTAKE_CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c.replace(/_/g, " ")}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid gap-1.5">
        <Label>Description</Label>
        <Textarea rows={2} value={item.description || ""} onChange={(e) => set({ description: e.target.value })} data-testid={`${testIdPrefix}-description-input`} />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="grid gap-1.5">
          <Label>Quantity</Label>
          <Input type="number" min={1} value={item.quantity ?? 1} onChange={(e) => set({ quantity: Math.max(1, parseInt(e.target.value || "1", 10)) })} data-testid={`${testIdPrefix}-quantity-input`} />
        </div>
        <div className="grid gap-1.5 col-span-2">
          <Label>Saved / common item</Label>
          <SavedItemSelector
            value={item.saved_item_id}
            category={item.category || undefined}
            onChange={(id) => set({ saved_item_id: id })}
            testIdPrefix={`${testIdPrefix}-saved-item`}
          />
        </div>
      </div>

      {item.pricing_status && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Pricing state:</span>
          <StatusPill kind="intake_pricing" value={item.pricing_status} />
        </div>
      )}

      {detailed && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>Width (in)</Label>
              <Input type="number" value={item.measurements?.width_inches ?? ""} onChange={(e) => set({ measurements: { ...item.measurements, width_inches: e.target.value ? Number(e.target.value) : undefined } })} data-testid={`${testIdPrefix}-width-input`} />
            </div>
            <div className="grid gap-1.5">
              <Label>Height (in)</Label>
              <Input type="number" value={item.measurements?.height_inches ?? ""} onChange={(e) => set({ measurements: { ...item.measurements, height_inches: e.target.value ? Number(e.target.value) : undefined } })} data-testid={`${testIdPrefix}-height-input`} />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Canonical material</Label>
            <MaterialProfileSelector value={item.material_profile_id} category={item.category || undefined} onChange={(id) => set({ material_profile_id: id })} testIdPrefix={`${testIdPrefix}-material`} />
          </div>
          <div className="grid gap-1.5">
            <Label>Requested completion date</Label>
            <Input type="date" value={item.requested_due_date || ""} onChange={(e) => set({ requested_due_date: e.target.value })} data-testid={`${testIdPrefix}-due-date-input`} />
          </div>
          <div className="grid gap-1.5">
            <Label>Customer notes</Label>
            <Textarea rows={2} value={item.customer_notes || ""} onChange={(e) => set({ customer_notes: e.target.value })} data-testid={`${testIdPrefix}-customer-notes-input`} />
          </div>
          <div className="grid gap-1.5">
            <Label>Internal notes</Label>
            <Textarea rows={2} value={item.internal_notes || ""} onChange={(e) => set({ internal_notes: e.target.value })} data-testid={`${testIdPrefix}-internal-notes-input`} />
          </div>
          <div className="grid gap-1.5">
            <Label>Files</Label>
            <FileAttachmentPicker fileIds={item.file_ids || []} onChange={(ids) => set({ file_ids: ids })} testIdPrefix={`${testIdPrefix}-files`} />
          </div>
        </>
      )}

      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={!!item.installation_required} onCheckedChange={(v) => set({ installation_required: !!v })} data-testid={`${testIdPrefix}-installation-checkbox`} />
          Installation required
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={!!item.proof_required} onCheckedChange={(v) => set({ proof_required: !!v })} data-testid={`${testIdPrefix}-proof-checkbox`} />
          Proof required
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={!!item.approval_required} onCheckedChange={(v) => set({ approval_required: !!v })} data-testid={`${testIdPrefix}-approval-checkbox`} />
          Approval required
        </label>
      </div>
    </div>
  );
}
