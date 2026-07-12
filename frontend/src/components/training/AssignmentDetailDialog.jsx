import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import StatusPill from "@/components/common/StatusPill";
import { formatDate, formatDateTime } from "@/lib/format";
import { toast } from "sonner";
import { CheckCircle2, XCircle } from "lucide-react";

export default function AssignmentDetailDialog({ assignmentId, open, onOpenChange, employeeName }) {
  const qc = useQueryClient();
  const [signoffResult, setSignoffResult] = useState("passed");
  const [signoffNotes, setSignoffNotes] = useState("");
  const [failReason, setFailReason] = useState("");

  const { data: a } = useQuery({
    queryKey: ["training-assignment-detail", assignmentId],
    queryFn: async () => (await api.get(`/training/assignments/${assignmentId}`)).data,
    enabled: open && !!assignmentId,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["training-assignment-detail", assignmentId] });
    qc.invalidateQueries({ queryKey: ["training-assignments"] });
  };

  const signoff = useMutation({
    mutationFn: async () => (await api.post(`/training/assignments/${assignmentId}/signoff`, { result: signoffResult, notes: signoffNotes || undefined })).data,
    onSuccess: () => { toast.success("Signoff recorded"); invalidate(); setSignoffNotes(""); },
    onError: (e) => toast.error(extractError(e)),
  });

  const fail = useMutation({
    mutationFn: async () => (await api.post(`/training/assignments/${assignmentId}/fail`, null, { params: { reason: failReason || undefined } })).data,
    onSuccess: () => { toast.success("Marked failed"); invalidate(); setFailReason(""); },
    onError: (e) => toast.error(extractError(e)),
  });

  const cancel = useMutation({
    mutationFn: async () => (await api.post(`/training/assignments/${assignmentId}/cancel`)).data,
    onSuccess: () => { toast.success("Assignment cancelled"); invalidate(); onOpenChange(false); },
    onError: (e) => toast.error(extractError(e)),
  });

  if (!a) return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="training-assignment-detail-dialog">
        <DialogHeader><DialogTitle>Assignment · {employeeName}</DialogTitle></DialogHeader>
        <div className="text-sm text-muted-foreground">Loading…</div>
      </DialogContent>
    </Dialog>
  );

  const canSignoff = a.practical_signoff_required && a.status === "pending_signoff";
  const terminal = ["completed", "failed", "cancelled"].includes(a.status);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]" data-testid="training-assignment-detail-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">Assignment · {employeeName}<StatusPill kind="training_assignment" value={a.status} /></DialogTitle>
          <DialogDescription>Due {a.due_date ? formatDate(a.due_date) : "no due date"}{a.overdue ? " · overdue" : ""}</DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-sm">
          {typeof a.latest_score === "number" && <div>Latest score: <span className="font-medium">{a.latest_score}%</span> (passing {a.required_score ?? "—"}%)</div>}

          {a.quiz_attempts?.length > 0 && (
            <div className="rounded-md border p-2" data-testid="training-assignment-quiz-attempts">
              <div className="text-xs text-muted-foreground mb-1">Quiz attempts</div>
              <ul className="divide-y">
                {a.quiz_attempts.map((qa) => (
                  <li key={qa.attempt_number} className="py-1.5 flex items-center justify-between" data-testid={`training-quiz-attempt-${qa.attempt_number}`}>
                    <span>Attempt {qa.attempt_number}</span>
                    <span className="flex items-center gap-2">
                      {qa.score}% {qa.passed ? <CheckCircle2 className="size-4 text-emerald-600" /> : <XCircle className="size-4 text-rose-600" />}
                      <span className="text-xs text-muted-foreground">{formatDateTime(qa.completed_at)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {a.practical_signoffs?.length > 0 && (
            <div className="rounded-md border p-2" data-testid="training-assignment-signoffs">
              <div className="text-xs text-muted-foreground mb-1">Practical signoffs</div>
              <ul className="divide-y">
                {a.practical_signoffs.map((s) => (
                  <li key={s.id} className="py-1.5">
                    <div className="flex items-center justify-between"><span className="capitalize">{s.result}</span><span className="text-xs text-muted-foreground">{formatDateTime(s.created_at)}</span></div>
                    {s.notes && <div className="text-xs text-muted-foreground">{s.notes}</div>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {canSignoff && (
            <div className="rounded-md border p-3 space-y-2" data-testid="training-signoff-form">
              <div className="text-xs font-medium">Practical signoff — pending your evaluation (no self-certification)</div>
              <Select value={signoffResult} onValueChange={setSignoffResult}>
                <SelectTrigger data-testid="training-signoff-result-select"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="passed">Passed</SelectItem><SelectItem value="failed">Failed</SelectItem></SelectContent>
              </Select>
              <Textarea rows={2} placeholder="Notes (optional)" value={signoffNotes} onChange={(e) => setSignoffNotes(e.target.value)} data-testid="training-signoff-notes-input" />
              <Button size="sm" onClick={() => signoff.mutate()} disabled={signoff.isPending} data-testid="training-signoff-submit-button">Record signoff</Button>
            </div>
          )}

          {!terminal && !canSignoff && (
            <div className="rounded-md border p-3 space-y-2" data-testid="training-fail-form">
              <div className="text-xs font-medium">Manual actions</div>
              <Textarea rows={2} placeholder="Reason for failing (optional)" value={failReason} onChange={(e) => setFailReason(e.target.value)} data-testid="training-fail-reason-input" />
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => fail.mutate()} disabled={fail.isPending} data-testid="training-fail-button">Mark failed</Button>
                <Button size="sm" variant="ghost" onClick={() => cancel.mutate()} disabled={cancel.isPending} data-testid="training-cancel-button">Cancel assignment</Button>
              </div>
            </div>
          )}
        </div>

        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)} data-testid="training-assignment-detail-close">Close</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
