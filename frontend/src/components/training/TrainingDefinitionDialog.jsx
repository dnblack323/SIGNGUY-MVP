import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";

const TRAINING_TYPES = ["reading", "video", "sop_review", "quiz", "practical_demonstration", "manager_signoff", "retraining"];

function emptyQuestion() {
  return { id: `q-${Math.random().toString(36).slice(2, 8)}`, prompt: "", choices: ["", ""], correct_index: 0 };
}

function QuizBuilder({ questions, onChange }) {
  function updateQ(i, patch) { onChange(questions.map((q, idx) => (idx === i ? { ...q, ...patch } : q))); }
  function updateChoice(i, ci, val) {
    const choices = [...questions[i].choices];
    choices[ci] = val;
    updateQ(i, { choices });
  }
  return (
    <div className="space-y-3" data-testid="quiz-builder">
      {questions.map((q, i) => (
        <div key={q.id} className="rounded-md border p-3 space-y-2" data-testid={`quiz-question-${i}`}>
          <div className="flex items-center gap-2">
            <Input placeholder={`Question ${i + 1} prompt`} value={q.prompt} onChange={(e) => updateQ(i, { prompt: e.target.value })} data-testid={`quiz-question-prompt-${i}`} />
            <Button type="button" variant="ghost" size="icon" onClick={() => onChange(questions.filter((_, idx) => idx !== i))} data-testid={`quiz-question-remove-${i}`}><Trash2 className="size-4" /></Button>
          </div>
          <RadioGroup value={String(q.correct_index)} onValueChange={(v) => updateQ(i, { correct_index: Number(v) })} className="space-y-1.5">
            {q.choices.map((c, ci) => (
              <div key={ci} className="flex items-center gap-2">
                <RadioGroupItem value={String(ci)} data-testid={`quiz-question-${i}-correct-${ci}`} />
                <Input placeholder={`Choice ${ci + 1}`} value={c} onChange={(e) => updateChoice(i, ci, e.target.value)} data-testid={`quiz-question-${i}-choice-${ci}`} />
                {q.choices.length > 2 && (
                  <Button type="button" variant="ghost" size="icon" onClick={() => updateQ(i, { choices: q.choices.filter((_, idx) => idx !== ci), correct_index: q.correct_index >= ci ? Math.max(0, q.correct_index - 1) : q.correct_index })}><Trash2 className="size-3.5" /></Button>
                )}
              </div>
            ))}
          </RadioGroup>
          {q.choices.length < 5 && (
            <Button type="button" variant="outline" size="sm" onClick={() => updateQ(i, { choices: [...q.choices, ""] })} data-testid={`quiz-question-${i}-add-choice`}>Add choice</Button>
          )}
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" onClick={() => onChange([...questions, emptyQuestion()])} data-testid="quiz-add-question-button">
        <Plus className="size-4 mr-1" />Add question
      </Button>
    </div>
  );
}

const emptyForm = { title: "", description: "", equipment_id: "", training_type: "reading", practical_signoff_required: false, passing_score: 80, quiz_questions: [] };

export default function TrainingDefinitionDialog({ open, onOpenChange, editing }) {
  const qc = useQueryClient();
  const { data: equipment } = useQuery({ queryKey: ["equipment-for-training"], queryFn: async () => (await api.get("/equipment")).data.items, enabled: open });
  const [form, setForm] = useState(emptyForm);

  useEffect(() => {
    if (!open) return;
    if (editing) setForm({ ...emptyForm, ...editing, equipment_id: editing.equipment_id || "" });
    else setForm(emptyForm);
  }, [open, editing]);

  const save = useMutation({
    mutationFn: async () => {
      const payload = { ...form, equipment_id: form.equipment_id || null, passing_score: form.training_type === "quiz" ? Number(form.passing_score) || 0 : null };
      if (editing) return (await api.patch(`/training/definitions/${editing.id}`, payload)).data;
      return (await api.post("/training/definitions", payload)).data;
    },
    onSuccess: () => {
      toast.success(editing ? "Training updated" : "Training created");
      qc.invalidateQueries({ queryKey: ["training-definitions"] });
      onOpenChange(false);
    },
    onError: (e) => toast.error(extractError(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[85vh] overflow-y-auto" data-testid="training-definition-dialog">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit Training" : "New Training Definition"}</DialogTitle>
          <DialogDescription>Bounded training content — reading, video, quiz, or a practical signoff.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Title*</Label><Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} data-testid="training-title-input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5"><Label>Type</Label>
              <Select value={form.training_type} onValueChange={(v) => setForm((f) => ({ ...f, training_type: v }))}>
                <SelectTrigger data-testid="training-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>{TRAINING_TYPES.map((t) => <SelectItem key={t} value={t} className="capitalize">{t.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5"><Label>Linked Equipment (optional)</Label>
              <Select value={form.equipment_id || "__none__"} onValueChange={(v) => setForm((f) => ({ ...f, equipment_id: v === "__none__" ? "" : v }))}>
                <SelectTrigger data-testid="training-equipment-select"><SelectValue placeholder="None" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">None</SelectItem>
                  {(equipment || []).map((eq) => <SelectItem key={eq.id} value={eq.id}>{eq.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-1.5"><Label>Description</Label><Textarea rows={2} value={form.description || ""} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} data-testid="training-description-input" /></div>
          <div className="flex items-center justify-between rounded-md border px-3 py-2">
            <Label>Requires a practical signoff (no self-certification)</Label>
            <Switch checked={!!form.practical_signoff_required} onCheckedChange={(v) => setForm((f) => ({ ...f, practical_signoff_required: v }))} data-testid="training-signoff-required-switch" />
          </div>
          {form.training_type === "quiz" && (
            <>
              <div className="grid gap-1.5 max-w-[160px]"><Label>Passing score (%)</Label><Input type="number" min="0" max="100" value={form.passing_score} onChange={(e) => setForm((f) => ({ ...f, passing_score: e.target.value }))} data-testid="training-passing-score-input" /></div>
              <QuizBuilder questions={form.quiz_questions || []} onChange={(qq) => setForm((f) => ({ ...f, quiz_questions: qq }))} />
            </>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => save.mutate()} disabled={save.isPending || !form.title.trim()} data-testid="training-submit-button">{save.isPending ? "Saving…" : editing ? "Save" : "Create"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
