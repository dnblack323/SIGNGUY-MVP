import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";

export default function RequirementsDialog({ workOrderId, currentEquipmentIds, currentRole, open, onOpenChange }) {
  const qc = useQueryClient();
  const { data: equipment } = useQuery({
    queryKey: ["equipment-for-wo"],
    queryFn: async () => (await api.get("/equipment")).data.items,
    enabled: open,
    retry: false,
  });
  const [selected, setSelected] = useState(currentEquipmentIds || []);
  const [role, setRole] = useState(currentRole || "");
  useEffect(() => { if (open) { setSelected(currentEquipmentIds || []); setRole(currentRole || ""); } }, [open, currentEquipmentIds, currentRole]);

  const save = useMutation({
    mutationFn: async () => (await api.patch(`/work-orders/${workOrderId}`, {
      required_equipment_ids: selected, required_role: role || null,
    })).data,
    onSuccess: () => {
      toast.success("Requirements updated");
      qc.invalidateQueries({ queryKey: ["work-order", workOrderId] });
      onOpenChange(false);
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const items = equipment || [];
  const sel = new Set(selected);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="wo-requirements-dialog">
        <DialogHeader>
          <DialogTitle>Assignment requirements</DialogTitle>
          <DialogDescription>Equipment/role needed to be eligible for this Work Order. Enforcement is backend-authoritative.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-1.5">
          <Label>Required Equipment</Label>
          <div className="rounded-md border max-h-40 overflow-auto divide-y" data-testid="wo-requirements-equipment-list">
            {items.length === 0 && <div className="p-3 text-xs text-muted-foreground italic">No Equipment registered yet.</div>}
            {items.map((eq) => (
              <label key={eq.id} className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50 cursor-pointer" data-testid={`wo-requirements-equipment-row-${eq.id}`}>
                <Checkbox
                  checked={sel.has(eq.id)}
                  onCheckedChange={(v) => {
                    const next = new Set(sel);
                    if (v) next.add(eq.id); else next.delete(eq.id);
                    setSelected(Array.from(next));
                  }}
                  data-testid={`wo-requirements-equipment-checkbox-${eq.id}`}
                />
                <span>{eq.name}</span>
                <span className="text-xs text-muted-foreground ml-auto capitalize">{eq.access_policy.replace(/_/g, " ")}</span>
              </label>
            ))}
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label>Required role (advisory only — never blocks)</Label>
          <Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. Install Tech" data-testid="wo-requirements-role-input" />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="wo-requirements-cancel">Cancel</Button>
          <Button onClick={() => save.mutate()} disabled={save.isPending} data-testid="wo-requirements-submit">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
