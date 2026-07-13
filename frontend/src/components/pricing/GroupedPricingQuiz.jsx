import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Sparkles, Calculator } from "lucide-react";

const DIFFICULTIES = [
  ["easy", "Easy"],
  ["typical", "Typical"],
  ["difficult", "Difficult"],
  ["rush", "Rush"],
];

const SUGGESTION_LABELS = {
  production_hourly_rate: "Production hourly rate ($/hr)",
  minimum_order_amount: "Minimum order ($)",
  target_profit_margin_percent: "Target profit margin (%)",
};

const emptyAnswers = {
  category: "", job_duration_hours: "", crew_size: "1", material_cost_estimate: "",
  customer_charge: "", price_floor: "", includes_design: false, includes_install: false,
  includes_setup: false, includes_finishing: false, difficulty: "typical",
};

/**
 * EC9 Phase 9C — Grouped Pricing Setup Quiz. ADDITIVE alongside the existing
 * detailed CategorySetupWizard — never a replacement. Suggestions are always
 * provisional; nothing is applied to shop_defaults without an explicit
 * "Apply selected" click after review.
 *
 * `resumeSubmission` (optional): a previously-saved `draft` submission to
 * resume directly at the review/apply step, skipping re-answering the quiz —
 * this is what powers "Continue previous setup" on the Pricing Foundation
 * page (a draft is never lost when the owner clicks "Review later").
 */
export default function GroupedPricingQuiz({ open, onOpenChange, categoryOptions, resumeSubmission }) {
  const qc = useQueryClient();
  const [answers, setAnswers] = useState(emptyAnswers);
  const [submission, setSubmission] = useState(null);
  const [selected, setSelected] = useState({});
  const [values, setValues] = useState({});

  useEffect(() => {
    if (open && resumeSubmission) {
      setSubmission(resumeSubmission);
      const map = resumeSubmission.derived_suggestions?.suggested_shop_defaults_map || {};
      setSelected(Object.fromEntries(Object.keys(map).map((k) => [k, true])));
      setValues(map);
    }
  }, [open, resumeSubmission]);

  const submit = useMutation({
    mutationFn: async () => {
      const payload = {
        ...answers,
        job_duration_hours: Number(answers.job_duration_hours),
        crew_size: parseInt(answers.crew_size, 10),
        material_cost_estimate: answers.material_cost_estimate === "" ? null : Number(answers.material_cost_estimate),
        customer_charge: Number(answers.customer_charge),
        price_floor: Number(answers.price_floor),
      };
      const { data } = await api.post("/pricing/quiz/submit", payload);
      return data;
    },
    onSuccess: (data) => {
      setSubmission(data);
      const map = data.derived_suggestions?.suggested_shop_defaults_map || {};
      setSelected(Object.fromEntries(Object.keys(map).map((k) => [k, true])));
      setValues(map);
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const apply = useMutation({
    mutationFn: async () => {
      const accepted_shop_defaults = Object.fromEntries(
        Object.entries(values).filter(([k]) => selected[k]).map(([k, v]) => [k, Number(v)])
      );
      const { data } = await api.post(`/pricing/quiz/submissions/${submission.id}/apply`, { accepted_shop_defaults });
      return data;
    },
    onSuccess: () => {
      toast.success("Applied to Pricing Foundation");
      qc.invalidateQueries({ queryKey: ["pricing-settings"] });
      qc.invalidateQueries({ queryKey: ["pricing-quiz-drafts"] });
      reset();
      onOpenChange(false);
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const skip = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/pricing/quiz/submissions/${submission.id}/skip`);
      return data;
    },
    onSuccess: () => {
      toast.message("Quiz skipped — you can start again anytime");
      qc.invalidateQueries({ queryKey: ["pricing-quiz-drafts"] });
      reset();
      onOpenChange(false);
    },
    onError: (e) => toast.error(extractError(e)),
  });

  function reset() {
    setAnswers(emptyAnswers);
    setSubmission(null);
    setSelected({});
    setValues({});
  }

  const s = submission?.derived_suggestions;

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="grouped-pricing-quiz">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Sparkles className="size-4" />Quick Setup — Grouped Pricing Quiz</DialogTitle>
        </DialogHeader>

        {!submission ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Think of one typical job you do often, and answer a few practical questions. We'll show you provisional suggestions you can review before anything changes.</p>
            <div className="grid gap-1.5">
              <Label>What type of job is this?</Label>
              <Select value={answers.category} onValueChange={(v) => setAnswers((a) => ({ ...a, category: v }))}>
                <SelectTrigger data-testid="quiz-category"><SelectValue placeholder="Select a category" /></SelectTrigger>
                <SelectContent>{(categoryOptions || []).map(([id, name]) => <SelectItem key={id} value={id}>{name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <Label>About how long does it take, start to finish? (hours)</Label>
                <Input type="number" step="0.1" min="0.1" value={answers.job_duration_hours} onChange={(e) => setAnswers((a) => ({ ...a, job_duration_hours: e.target.value }))} data-testid="quiz-duration" />
              </div>
              <div className="grid gap-1.5">
                <Label>How many people normally work on it?</Label>
                <Input type="number" min="1" step="1" value={answers.crew_size} onChange={(e) => setAnswers((a) => ({ ...a, crew_size: e.target.value }))} data-testid="quiz-crew-size" />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label>About how much material does it use? (estimated $ cost, optional)</Label>
              <Input type="number" step="0.01" min="0" value={answers.material_cost_estimate} onChange={(e) => setAnswers((a) => ({ ...a, material_cost_estimate: e.target.value }))} data-testid="quiz-material-cost" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <Label>What would you normally charge the customer?</Label>
                <Input type="number" step="0.01" min="0" value={answers.customer_charge} onChange={(e) => setAnswers((a) => ({ ...a, customer_charge: e.target.value }))} data-testid="quiz-customer-charge" />
              </div>
              <div className="grid gap-1.5">
                <Label>What's the lowest price you'd accept?</Label>
                <Input type="number" step="0.01" min="0" value={answers.price_floor} onChange={(e) => setAnswers((a) => ({ ...a, price_floor: e.target.value }))} data-testid="quiz-price-floor" />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label>Does that price include any of these?</Label>
              <div className="flex flex-wrap gap-4 text-sm">
                {[["includes_design", "Design"], ["includes_install", "Installation"], ["includes_setup", "Setup"], ["includes_finishing", "Finishing"]].map(([k, label]) => (
                  <label key={k} className="flex items-center gap-2" data-testid={`quiz-${k}`}>
                    <Checkbox checked={answers[k]} onCheckedChange={(v) => setAnswers((a) => ({ ...a, [k]: !!v }))} />{label}
                  </label>
                ))}
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label>Is this a typical, easy, difficult, or rush job?</Label>
              <Select value={answers.difficulty} onValueChange={(v) => setAnswers((a) => ({ ...a, difficulty: v }))}>
                <SelectTrigger data-testid="quiz-difficulty"><SelectValue /></SelectTrigger>
                <SelectContent>{DIFFICULTIES.map(([id, name]) => <SelectItem key={id} value={id}>{name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => { reset(); onOpenChange(false); }} data-testid="quiz-cancel-button">Skip for now</Button>
              <Button
                onClick={() => submit.mutate()}
                disabled={submit.isPending || !answers.category || !answers.job_duration_hours || !answers.customer_charge || answers.price_floor === ""}
                data-testid="quiz-submit-button"
              >
                <Calculator className="size-4 mr-1" />Get suggestions
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-4">
            <Badge variant="secondary">Provisional — nothing has been applied yet</Badge>
            <div className="rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground space-y-1" data-testid="quiz-math-shown">
              {submission.math_shown.map((line, i) => <div key={i}>{line}</div>)}
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><span className="text-muted-foreground">Labor rate</span>: {s.labor_rate != null ? `$${s.labor_rate}/hr` : "—"}</div>
              <div><span className="text-muted-foreground">Effective shop rate</span>: {s.effective_shop_rate != null ? `$${s.effective_shop_rate}/hr` : "—"}</div>
              <div><span className="text-muted-foreground">Minimum charge</span>: {s.minimum_charge != null ? `$${s.minimum_charge}` : "—"}</div>
              <div><span className="text-muted-foreground">Overhead recovery</span>: {s.overhead_recovery != null ? `$${s.overhead_recovery}` : "—"}</div>
              <div><span className="text-muted-foreground">Target margin</span>: {s.target_margin != null ? `${s.target_margin}%` : "—"}</div>
              <div><span className="text-muted-foreground">Suggested sell rate</span>: {s.suggested_sell_rate != null ? `$${s.suggested_sell_rate}/hr` : "—"}</div>
              <div><span className="text-muted-foreground">Design allowance</span>: {s.design_allowance != null ? `$${s.design_allowance}` : "—"}</div>
              <div><span className="text-muted-foreground">Install allowance</span>: {s.install_allowance != null ? `$${s.install_allowance}` : "—"}</div>
              <div><span className="text-muted-foreground">Setup allowance</span>: {s.setup_allowance != null ? `$${s.setup_allowance}` : "—"}</div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm">Apply to your Pricing Foundation shop defaults (review before applying):</Label>
              {Object.entries(s.suggested_shop_defaults_map || {}).map(([field, suggestedVal]) => (
                <div key={field} className="flex items-center gap-3" data-testid={`quiz-apply-row-${field}`}>
                  <Checkbox checked={!!selected[field]} onCheckedChange={(v) => setSelected((sel) => ({ ...sel, [field]: !!v }))} data-testid={`quiz-apply-check-${field}`} />
                  <span className="text-sm flex-1">{SUGGESTION_LABELS[field] || field}</span>
                  <Input
                    type="number" step="0.01" className="w-32"
                    value={values[field] ?? suggestedVal ?? ""}
                    onChange={(e) => setValues((v) => ({ ...v, [field]: e.target.value }))}
                    disabled={!selected[field]}
                    data-testid={`quiz-apply-value-${field}`}
                  />
                </div>
              ))}
            </div>

            <DialogFooter className="gap-2">
              <Button variant="ghost" onClick={() => skip.mutate()} disabled={skip.isPending} data-testid="quiz-skip-button">Skip this suggestion</Button>
              <Button variant="outline" onClick={() => { toast.message("Saved as a draft — resume anytime from \"Continue previous setup\" on this page"); qc.invalidateQueries({ queryKey: ["pricing-quiz-drafts"] }); reset(); onOpenChange(false); }} data-testid="quiz-review-later-button">Review later</Button>
              <Button
                onClick={() => apply.mutate()}
                disabled={apply.isPending || Object.values(selected).every((v) => !v)}
                data-testid="quiz-apply-button"
              >
                Apply selected
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
