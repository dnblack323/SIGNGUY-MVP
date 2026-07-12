import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";

export default function AssignTrainingDialog({ open, onOpenChange, employees, definitions }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ employee_id: "", training_definition_id: "", due_date: "", manager_notes: "" });
  useEffect(() => { if (open) setForm({ employee_id: "", training_definition_id: "", due_date: "", manager_notes: "" }); }, [open]);

  const save = useMutation({
    mutationFn: async () => (await api.post("/training/assignments", {
      employee_id: form.employee_id, training_definition_id: form.training_definition_id,
      due_date: form.due_date || null, manager_notes: form.manager_notes || null,
    })).data,
    onSuccess: () => { toast.success("Training assigned"); qc.invalidateQueries({ queryKey: ["training-assignments"] }); onOpenChange(false); },
    onError: (e) => toast.error(extractError(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="assign-training-dialog">
        <DialogHeader>
          <DialogTitle>Assign Training</DialogTitle>
          <DialogDescription>Give an Employee a Training assignment to complete.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Employee*</Label>
            <Select value={form.employee_id} onValueChange={(v) => setForm((f) => ({ ...f, employee_id: v }))}>
              <SelectTrigger data-testid="assign-training-employee-select"><SelectValue placeholder="Select employee" /></SelectTrigger>
              <SelectContent>{(employees || []).map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Training*</Label>
            <Select value={form.training_definition_id} onValueChange={(v) => setForm((f) => ({ ...f, training_definition_id: v }))}>
              <SelectTrigger data-testid="assign-training-definition-select"><SelectValue placeholder="Select training" /></SelectTrigger>
              <SelectContent>{(definitions || []).map((d) => <SelectItem key={d.id} value={d.id}>{d.title}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Due date</Label><Input type="date" value={form.due_date} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} data-testid="assign-training-due-date-input" /></div>
          <div className="grid gap-1.5"><Label>Manager notes (never shown to employee)</Label><Textarea rows={2} value={form.manager_notes} onChange={(e) => setForm((f) => ({ ...f, manager_notes: e.target.value }))} data-testid="assign-training-notes-input" /></div>
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => save.mutate()} disabled={save.isPending || !form.employee_id || !form.training_definition_id} data-testid="assign-training-submit-button">
            {save.isPending ? "Assigning…" : "Assign"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
