import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import employeePortalApi, { employeePortalExtractError } from "./employeePortalApi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2, FileText, GraduationCap, XCircle } from "lucide-react";

export default function MyTrainingAssignmentDetailPage() {
  const { assignmentId } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [answers, setAnswers] = useState({});
  const [busy, setBusy] = useState(false);
  const [startedAt, setStartedAt] = useState(() => new Date().toISOString());

  const load = useCallback(async () => {
    try {
      const r = await employeePortalApi.get(`/portal/employee/training/assignments/${assignmentId}`);
      setData(r.data);
      setAnswers({});
    } catch (e) { setErr(employeePortalExtractError(e)); }
  }, [assignmentId]);
  useEffect(() => { load(); }, [load]);

  async function start() {
    setBusy(true);
    try { await employeePortalApi.post(`/portal/employee/training/assignments/${assignmentId}/start`); await load(); }
    catch (e) { toast.error(employeePortalExtractError(e)); }
    setBusy(false);
  }
  async function complete() {
    setBusy(true);
    try { await employeePortalApi.post(`/portal/employee/training/assignments/${assignmentId}/complete`); await load(); toast.success("Training completed"); }
    catch (e) { toast.error(employeePortalExtractError(e)); }
    setBusy(false);
  }
  async function submitQuiz() {
    const questions = data.definition.quiz_questions || [];
    if (questions.some((q) => answers[q.id] === undefined)) { toast.error("Answer every question first"); return; }
    setBusy(true);
    try {
      const r = await employeePortalApi.post(`/portal/employee/training/assignments/${assignmentId}/quiz`, {
        answers: questions.map((q) => ({ question_id: q.id, selected_index: answers[q.id] })),
        started_at: startedAt,
      });
      toast[r.data.passed ? "success" : "error"](`Scored ${r.data.score}% — ${r.data.passed ? "passed" : "failed"}`);
      setStartedAt(new Date().toISOString());
      await load();
    } catch (e) { toast.error(employeePortalExtractError(e)); }
    setBusy(false);
  }

  if (err) return <div className="text-sm text-rose-700 max-w-lg" data-testid="employee-portal-training-detail-error">{err}</div>;
  if (!data) return <p className="text-sm text-slate-500">Loading…</p>;

  const { definition, status, latest_score, quiz_attempts, documents } = data;
  const isQuiz = definition.training_type === "quiz" && (definition.quiz_questions || []).length > 0;

  return (
    <div className="space-y-4 max-w-lg" data-testid="employee-portal-training-detail-page">
      <Button variant="ghost" size="sm" onClick={() => nav("/portal/employee/training")} data-testid="employee-portal-training-back"><ArrowLeft className="h-4 w-4 mr-1" />Back</Button>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 flex-wrap">
            <GraduationCap className="h-4 w-4" />{definition.title}
            <Badge variant="outline" className="capitalize" data-testid="employee-portal-training-detail-status">{status.replace(/_/g, " ")}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {definition.description && <p className="text-slate-600">{definition.description}</p>}

          {documents?.length > 0 && (
            <div>
              <div className="text-xs text-slate-500 mb-1 flex items-center gap-1"><FileText className="h-3.5 w-3.5" />Materials</div>
              <ul className="text-sm" data-testid="employee-portal-training-materials">{documents.map((d) => <li key={d.link_id}>{d.title}</li>)}</ul>
            </div>
          )}

          {status === "pending_signoff" && (
            <div className="rounded border border-indigo-200 bg-indigo-50 text-indigo-900 p-3" data-testid="employee-portal-training-pending-signoff">
              Waiting on your manager's practical signoff.
            </div>
          )}
          {status === "completed" && (
            <div className="rounded border border-emerald-200 bg-emerald-50 text-emerald-900 p-3 flex items-center gap-2" data-testid="employee-portal-training-completed">
              <CheckCircle2 className="h-4 w-4" />Completed{typeof latest_score === "number" ? ` — scored ${latest_score}%` : ""}
            </div>
          )}
          {!isQuiz && status === "failed" && (
            <div className="rounded border border-rose-200 bg-rose-50 text-rose-900 p-3" data-testid="employee-portal-training-failed">This Training was marked failed.</div>
          )}
          {status === "cancelled" && (
            <div className="rounded border border-slate-200 bg-slate-50 text-slate-600 p-3" data-testid="employee-portal-training-cancelled">This Training assignment was cancelled.</div>
          )}

          {isQuiz && !["completed", "pending_signoff", "cancelled"].includes(status) && (
            <div className="space-y-3" data-testid="employee-portal-quiz-form">
              {definition.quiz_questions.map((q, i) => (
                <div key={q.id} className="space-y-1.5" data-testid={`employee-portal-quiz-question-${i}`}>
                  <Label>{i + 1}. {q.prompt}</Label>
                  <RadioGroup value={answers[q.id] != null ? String(answers[q.id]) : ""} onValueChange={(v) => setAnswers((a) => ({ ...a, [q.id]: Number(v) }))}>
                    {q.choices.map((c, ci) => (
                      <div key={ci} className="flex items-center gap-2">
                        <RadioGroupItem value={String(ci)} id={`${q.id}-${ci}`} data-testid={`employee-portal-quiz-${i}-choice-${ci}`} />
                        <label htmlFor={`${q.id}-${ci}`} className="text-sm">{c}</label>
                      </div>
                    ))}
                  </RadioGroup>
                </div>
              ))}
              <Button onClick={submitQuiz} disabled={busy} data-testid="employee-portal-quiz-submit-button">Submit Quiz</Button>
              {quiz_attempts?.length > 0 && (
                <div className="text-xs text-slate-500 pt-2 border-t" data-testid="employee-portal-quiz-attempt-history">
                  Attempt history:{" "}
                  {quiz_attempts.map((qa) => (
                    <span key={qa.attempt_number} className="inline-flex items-center gap-1 mr-2">
                      #{qa.attempt_number} {qa.score}% {qa.passed ? <CheckCircle2 className="h-3 w-3 text-emerald-600" /> : <XCircle className="h-3 w-3 text-rose-600" />}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {!isQuiz && status === "not_started" && (
            <Button onClick={start} disabled={busy} data-testid="employee-portal-training-start-button">Start Training</Button>
          )}
          {!isQuiz && status === "in_progress" && (
            <Button onClick={complete} disabled={busy} data-testid="employee-portal-training-complete-button">Mark Complete</Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
