import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Wrench } from "lucide-react";

export default function GenerateWorkOrderDialog({ orderId, open, onOpenChange, onCreated }) {
  const qc = useQueryClient();
  const { data: users } = useQuery({
    queryKey: ["users"],
    queryFn: async () => (await api.get("/users")).data,
    enabled: open,
  });

  const [priority, setPriority] = useState("normal");
  const [dueDate, setDueDate] = useState("");
  const [instructions, setInstructions] = useState("");
  const [internalNotes, setInternalNotes] = useState("");
  const [assigneeIds, setAssigneeIds] = useState([]);

  useEffect(() => {
    if (open) {
      setPriority("normal"); setDueDate(""); setInstructions(""); setInternalNotes(""); setAssigneeIds([]);
    }
  }, [open]);

  const create = useMutation({
    mutationFn: async () => (await api.post("/work-orders", {
      order_id: orderId,
      priority,
      due_date: dueDate || null,
      production_instructions: instructions || null,
      internal_notes: internalNotes || null,
      assigned_user_ids: assigneeIds,
    })).data,
    onSuccess: (wo) => {
      if (wo.already_exists) {
        toast.info(`Work order W-${wo.number} already exists for this order`);
      } else {
        toast.success(`Work order W-${wo.number} generated`);
      }
      qc.invalidateQueries({ queryKey: ["prod-board"] });
      qc.invalidateQueries({ queryKey: ["work-orders"] });
      onOpenChange(false);
      onCreated?.(wo);
    },
    onError: (e) => toast.error(extractError(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="generate-wo-dialog" className="max-w-lg">
        <DialogHeader>
          <DialogTitle><Wrench className="inline size-4 mr-1" />Generate Work Order</DialogTitle>
          <DialogDescription>Snapshot production-required items into a new work order.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>Priority</Label>
              <Select value={priority} onValueChange={setPriority}>
                <SelectTrigger data-testid="gen-wo-priority"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="rush">Rush</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>Due date</Label>
              <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} data-testid="gen-wo-due-date" />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Production instructions</Label>
            <Textarea rows={3} value={instructions} onChange={(e) => setInstructions(e.target.value)} data-testid="gen-wo-instructions" />
          </div>
          <div className="grid gap-1.5">
            <Label>Internal notes</Label>
            <Textarea rows={2} value={internalNotes} onChange={(e) => setInternalNotes(e.target.value)} data-testid="gen-wo-internal-notes" />
          </div>
          <div className="grid gap-1.5">
            <Label>Assignees</Label>
            <AssigneePicker users={users || []} value={assigneeIds} onChange={setAssigneeIds} testIdPrefix="gen-wo-assignee" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="gen-wo-cancel">Cancel</Button>
          <Button onClick={() => create.mutate()} disabled={create.isPending} data-testid="gen-wo-submit">
            Generate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function AssigneePicker({ users, value, onChange, testIdPrefix = "assignee" }) {
  const selected = new Set(value || []);
  return (
    <div className="rounded-md border max-h-40 overflow-auto divide-y" data-testid={`${testIdPrefix}-list`}>
      {users.length === 0 && <div className="p-3 text-xs text-muted-foreground italic">No users available</div>}
      {users.map((u) => {
        const checked = selected.has(u.id);
        return (
          <label key={u.id} className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50 cursor-pointer" data-testid={`${testIdPrefix}-row-${u.id}`}>
            <Checkbox
              checked={checked}
              onCheckedChange={(v) => {
                const next = new Set(selected);
                if (v) next.add(u.id); else next.delete(u.id);
                onChange(Array.from(next));
              }}
              data-testid={`${testIdPrefix}-checkbox-${u.id}`}
            />
            <span>{u.full_name || u.email}</span>
            <span className="text-xs text-muted-foreground ml-auto">{u.email}</span>
          </label>
        );
      })}
    </div>
  );
}

export function RegenerateDialog({ workOrderId, open, onOpenChange, onDone }) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  useEffect(() => { if (open) setReason(""); }, [open]);

  const regen = useMutation({
    mutationFn: async () => (await api.post(`/work-orders/${workOrderId}/regenerate`, { reason: reason.trim() })).data,
    onSuccess: (wo) => {
      toast.success(`Regenerated as W-${wo.number} (v${wo.version})`);
      qc.invalidateQueries({ queryKey: ["work-orders"] });
      qc.invalidateQueries({ queryKey: ["prod-board"] });
      qc.invalidateQueries({ queryKey: ["work-order"] });
      onOpenChange(false);
      onDone?.(wo);
    },
    onError: (e) => toast.error(extractError(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="regenerate-wo-dialog">
        <DialogHeader>
          <DialogTitle>Regenerate Work Order</DialogTitle>
          <DialogDescription>Create a new version and mark the current row as superseded.</DialogDescription>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          This will create a new version and mark the current work order as superseded. The original snapshot is preserved.
        </p>
        <div className="grid gap-1.5">
          <Label>Reason <span className="text-rose-600">*</span></Label>
          <Textarea rows={4} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="regen-wo-reason" autoFocus />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="regen-wo-cancel">Cancel</Button>
          <Button onClick={() => regen.mutate()} disabled={regen.isPending || !reason.trim()} data-testid="regen-wo-submit">
            Regenerate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function TransitionReasonDialog({ open, target, onCancel, onConfirm, pending }) {
  const [reason, setReason] = useState("");
  useEffect(() => { if (open) setReason(""); }, [open]);
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onCancel(); }}>
      <DialogContent data-testid="transition-reason-dialog">
        <DialogHeader>
          <DialogTitle>Reason required</DialogTitle>
          <DialogDescription>A reason is required for this transition.</DialogDescription>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Moving to <span className="capitalize font-medium">{target}</span> requires a reason.
        </p>
        <Textarea rows={4} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="transition-reason-input" autoFocus />
        <DialogFooter>
          <Button variant="outline" onClick={onCancel} data-testid="transition-reason-cancel">Cancel</Button>
          <Button onClick={() => onConfirm(reason.trim())} disabled={pending || !reason.trim()} data-testid="transition-reason-confirm">
            Confirm
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function AssignDialog({ workOrderId, currentUserIds, open, onOpenChange }) {
  const qc = useQueryClient();
  const { data: users } = useQuery({
    queryKey: ["users"],
    queryFn: async () => (await api.get("/users")).data,
    enabled: open,
  });
  const [selected, setSelected] = useState(currentUserIds || []);
  useEffect(() => { if (open) setSelected(currentUserIds || []); }, [open, currentUserIds]);

  const save = useMutation({
    mutationFn: async () => (await api.post(`/work-orders/${workOrderId}/assign`, { user_ids: selected })).data,
    onSuccess: () => {
      toast.success("Assignments updated");
      qc.invalidateQueries({ queryKey: ["work-order", workOrderId] });
      qc.invalidateQueries({ queryKey: ["prod-board"] });
      onOpenChange(false);
    },
    onError: (e) => toast.error(extractError(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="assign-wo-dialog">
        <DialogHeader>
          <DialogTitle>Assign work order</DialogTitle>
          <DialogDescription>Select users in this tenant. Newly assigned users are notified.</DialogDescription>
        </DialogHeader>
        <AssigneePicker users={users || []} value={selected} onChange={setSelected} testIdPrefix="assign-wo" />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="assign-wo-cancel">Cancel</Button>
          <Button onClick={() => save.mutate()} disabled={save.isPending} data-testid="assign-wo-submit">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
