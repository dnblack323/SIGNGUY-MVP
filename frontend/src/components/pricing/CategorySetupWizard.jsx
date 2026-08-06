import { useMemo, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Wand2, ArrowRight, ArrowLeft, Loader2 } from "lucide-react";
import api, { extractError } from "@/lib/api";
import { toast } from "sonner";

const METHOD_LABELS = {
  per_sqft: "Price by Size / Quantity",
  cost_plus_labor: "Cost + Labor + Profit",
  common_job_prices: "Use My Common Project Prices",
};

function QuestionRow({ q, value, onChange }) {
  if (q.type === "bool") {
    return (
      <div className="flex items-center justify-between gap-4 py-3">
        <Label htmlFor={q.id} className="font-normal">{q.label}</Label>
        <Switch id={q.id} checked={!!value} onCheckedChange={onChange} data-testid={`wizard-q-${q.id}`} />
      </div>
    );
  }
  if (q.type === "number" || q.type === "money") {
    return (
      <div className="grid gap-1.5 py-2">
        <Label>{q.label}{q.helper && <span className="ml-2 text-xs text-muted-foreground">{q.helper}</span>}</Label>
        <Input
          type="number" step={q.type === "money" ? "0.01" : q.step || "1"} inputMode="decimal"
          value={value ?? ""} onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
          placeholder={q.placeholder}
          data-testid={`wizard-q-${q.id}`}
        />
      </div>
    );
  }
  if (q.type === "text") {
    return (
      <div className="grid gap-1.5 py-2">
        <Label>{q.label}</Label>
        <Input value={value ?? ""} onChange={(e) => onChange(e.target.value)} data-testid={`wizard-q-${q.id}`} />
      </div>
    );
  }
  if (q.type === "textarea") {
    return (
      <div className="grid gap-1.5 py-2">
        <Label>{q.label}</Label>
        <Textarea rows={3} value={value ?? ""} onChange={(e) => onChange(e.target.value)} data-testid={`wizard-q-${q.id}`} />
      </div>
    );
  }
  return null;
}

export default function CategorySetupWizard({ open, onOpenChange, categoryId, categoryConfig, currentSettings, onApplied }) {
  const meta = currentSettings?.category_meta?.[categoryId] || {};
  const current = currentSettings?.category_defaults?.[categoryId] || {};

  const [step, setStep] = useState(0);
  const [method, setMethod] = useState(current.pricing_method || categoryConfig.defaultMethod);
  const [answers, setAnswers] = useState({});
  const [suggestions, setSuggestions] = useState([]);
  const [busy, setBusy] = useState(false);

  const questions = categoryConfig.questions || [];
  const upd = (id) => (v) => setAnswers((a) => ({ ...a, [id]: v }));

  async function fetchSuggestions() {
    setBusy(true);
    try {
      const payload = { answers: { ...answers, pricing_method: method } };
      const { data } = await api.post(`/pricing/settings/categories/${categoryId}/wizard/suggestions`, payload);
      setSuggestions(data.suggestions.map((s) => ({ ...s, apply: s.apply !== false })));
      setStep(2);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  async function applySuggestions() {
    setBusy(true);
    try {
      await api.post(`/pricing/settings/categories/${categoryId}/wizard/apply`, {
        suggestions, mark_setup_complete: true,
      });
      toast.success(`${meta.name || categoryId} setup applied`);
      onApplied?.();
      onOpenChange(false);
      // reset for next time
      setStep(0); setAnswers({}); setSuggestions([]);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[720px] max-h-[85vh] overflow-y-auto" data-testid="wizard-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Wand2 className="size-4" />{meta.name || categoryId} setup</DialogTitle>
          <DialogDescription>{meta.description}</DialogDescription>
        </DialogHeader>

        {step === 0 && (
          <div className="space-y-4">
            <div>
              <div className="text-sm font-medium mb-2">How do you usually want to price this type of work?</div>
              <RadioGroup value={method} onValueChange={setMethod} data-testid="wizard-method">
                {categoryConfig.methodOptions.map((m) => (
                  <label key={m} className="flex items-center gap-2 py-2 cursor-pointer">
                    <RadioGroupItem value={m} id={`m-${m}`} />
                    <span>{METHOD_LABELS[m]}</span>
                  </label>
                ))}
              </RadioGroup>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
              <Button onClick={() => setStep(1)} disabled={!method} data-testid="wizard-next-questions"><ArrowRight className="size-4 mr-1" />Continue</Button>
            </DialogFooter>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-2">
            <div className="text-xs text-muted-foreground mb-2">Skip any question you’re unsure about — the wizard only suggests values based on what you answer.</div>
            <div className="divide-y">
              {questions.map((q) => (
                <QuestionRow key={q.id} q={q} value={answers[q.id]} onChange={upd(q.id)} />
              ))}
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setStep(0)}><ArrowLeft className="size-4 mr-1" />Back</Button>
              <Button onClick={fetchSuggestions} disabled={busy} data-testid="wizard-review-suggestions">
                {busy && <Loader2 className="size-4 mr-2 animate-spin" />}Review suggestions
              </Button>
            </DialogFooter>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            {suggestions.length === 0 ? (
              <div className="text-sm text-muted-foreground py-4">No suggestions from your answers. Skip back to add more, or close.</div>
            ) : (
              <div className="rounded-lg border divide-y" data-testid="wizard-suggestions-list">
                {suggestions.map((s, i) => (
                  <div key={i} className="p-3 flex items-start gap-3" data-testid={`wizard-suggestion-${s.target_field}`}>
                    <Checkbox checked={!!s.apply} onCheckedChange={(v) => setSuggestions((list) => list.map((x, idx) => idx === i ? { ...x, apply: !!v } : x))} className="mt-1" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium">{s.question}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">You said: <span className="text-foreground">{String(s.answer)}</span></div>
                      <div className="mt-1 flex items-center gap-2 text-sm">
                        <span className="text-muted-foreground">Suggest:</span>
                        <span className="font-medium mono">{typeof s.suggested === "object" ? JSON.stringify(s.suggested) : String(s.suggested)}</span>
                        <span className="text-muted-foreground">for</span>
                        <code className="text-xs bg-muted rounded px-1 py-0.5">{s.target_field}</code>
                        <Badge variant={s.confidence === "recommended" ? "default" : "secondary"} className="ml-auto capitalize">{s.confidence.replace("_", " ")}</Badge>
                      </div>
                      {s.note && <div className="text-xs text-muted-foreground mt-1">{s.note}</div>}
                    </div>
                  </div>
                ))}
              </div>
            )}
            <DialogFooter>
              <Button variant="ghost" onClick={() => setStep(1)}><ArrowLeft className="size-4 mr-1" />Back</Button>
              <Button onClick={applySuggestions} disabled={busy || suggestions.filter((s) => s.apply).length === 0} data-testid="wizard-apply-button">
                {busy && <Loader2 className="size-4 mr-2 animate-spin" />}Apply selected & mark setup complete
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
