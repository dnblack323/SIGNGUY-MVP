import { useState } from "react";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/auth/AuthContext";

const PRIORITIES = ["low", "normal", "high", "rush"];

export default function TaskHandoffButton({ sourceType, sourceId, defaults = {}, size = "sm", variant = "outline" }) {
  const { hasPerm } = useAuth();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: defaults.title || "Follow up",
    description: defaults.description || "",
    priority: defaults.priority || "normal",
    task_type: defaults.task_type || sourceType || "general",
    due_at: "",
  });

  const set = (key) => (valueOrEvent) => {
    const value = valueOrEvent?.target ? valueOrEvent.target.value : valueOrEvent;
    setForm((current) => ({ ...current, [key]: value }));
  };

  if (!hasPerm("task:create")) return null;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = {
        ...form,
        source_type: sourceType,
        source_id: sourceId,
        idempotency_key: `handoff:${sourceType}:${sourceId}:${form.title}:${form.due_at || "no-due"}`,
      };
      if (!payload.due_at) delete payload.due_at;
      await api.post("/tasks", payload);
      toast.success("Task created");
      setOpen(false);
    } catch (err) {
      toast.error(extractError(err, "Could not create task"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size={size} variant={variant} data-testid={`create-task-${sourceType}-${sourceId}`}>
          <Plus className="size-4 mr-1" />Create task
        </Button>
      </DialogTrigger>
      <DialogContent data-testid="task-handoff-dialog">
        <DialogHeader><DialogTitle>Create task for this record</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-1.5">
            <Label>Title</Label>
            <Input required value={form.title} onChange={set("title")} />
          </div>
          <div className="grid gap-1.5">
            <Label>Description</Label>
            <Textarea rows={3} value={form.description} onChange={set("description")} />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="grid gap-1.5">
              <Label>Priority</Label>
              <Select value={form.priority} onValueChange={set("priority")}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p.replace("_", " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>Type</Label>
              <Input value={form.task_type} onChange={set("task_type")} />
            </div>
            <div className="grid gap-1.5">
              <Label>Due</Label>
              <Input type="date" value={form.due_at} onChange={set("due_at")} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy}>{busy ? "Creating..." : "Create task"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
