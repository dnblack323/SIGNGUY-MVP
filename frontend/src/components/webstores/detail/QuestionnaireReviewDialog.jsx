import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Undo2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { extractError } from "@/lib/api";
import {
  approveWebstoreQuestionnaire,
  getWebstoreQuestionnaireReview,
  returnWebstoreQuestionnaire,
  reverseWebstoreAnswerApplication,
} from "@/lib/webstores";
import { toast } from "sonner";

export function displayValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) {
    return value.map((item) => (typeof item === "object" ? [item.date, item.start && `${item.start}–${item.end}`, item.location].filter(Boolean).join(" ") : item)).join(", ") || "—";
  }
  if (typeof value === "object") return value.file_name || JSON.stringify(value);
  return String(value);
}

export default function QuestionnaireReviewDialog({ webstoreId, open, onOpenChange, onChanged }) {
  const [returning, setReturning] = useState(false);
  const [reason, setReason] = useState("");
  const [application, setApplication] = useState(null);
  const review = useQuery({
    queryKey: ["webstore-questionnaire-review", webstoreId],
    queryFn: () => getWebstoreQuestionnaireReview(webstoreId),
    enabled: open && Boolean(webstoreId),
  });
  const done = async (message) => {
    toast.success(message);
    await review.refetch();
    await onChanged?.();
  };
  const approve = useMutation({
    mutationFn: () => approveWebstoreQuestionnaire(webstoreId, review.data.submission.id),
    onSuccess: async (data) => { setApplication(data.application); await done("Answers approved and applied to the draft store"); },
    onError: (err) => toast.error(extractError(err)),
  });
  const sendBack = useMutation({
    mutationFn: () => returnWebstoreQuestionnaire(webstoreId, review.data.submission.id, reason),
    onSuccess: async () => { setReturning(false); setReason(""); await done("Returned to the owner for changes"); onOpenChange(false); },
    onError: (err) => toast.error(extractError(err)),
  });
  const reverse = useMutation({
    mutationFn: () => reverseWebstoreAnswerApplication(webstoreId, application.id, { reason: "Reversed from questionnaire review", idempotency_key: `reverse-${application.id}` }),
    onSuccess: async () => { setApplication(null); await done("Applied answers reversed"); },
    onError: (err) => toast.error(extractError(err)),
  });

  const data = review.data;
  const submission = data?.submission;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[860px]" data-testid="questionnaire-review-dialog">
        <DialogHeader>
          <DialogTitle>Questionnaire review{submission ? ` — revision ${submission.revision}` : ""}</DialogTitle>
          <DialogDescription>Check the summary and proposed draft settings, then Approve &amp; Apply. Financial terms are confirmed later at store approval.</DialogDescription>
        </DialogHeader>
        {review.isLoading && <p className="text-sm text-muted-foreground">Loading review...</p>}
        {review.isError && <p className="text-sm text-rose-700">{extractError(review.error)}</p>}
        {data && (
          <div className="space-y-4 text-sm">
            {data.warnings.length > 0 && (
              <Alert variant="destructive" data-testid="questionnaire-review-warnings">
                <AlertTriangle className="size-4" />
                <AlertTitle>Check before applying</AlertTitle>
                <AlertDescription><ul className="list-disc pl-4">{data.warnings.map((w) => <li key={w.code + w.message}>{w.message}</li>)}</ul></AlertDescription>
              </Alert>
            )}
            {data.comparison.length > 0 && (
              <section data-testid="questionnaire-review-comparison">
                <h3 className="font-medium">Changes since revision {data.previous_revision}</h3>
                <table className="mt-1 w-full text-left text-xs">
                  <thead><tr className="text-muted-foreground"><th className="py-1">Question</th><th>Before</th><th>Now</th></tr></thead>
                  <tbody>
                    {data.comparison.map((row) => (
                      <tr key={row.key} className={row.material ? "bg-amber-50 font-medium" : ""}>
                        <td className="py-1 pr-2">{row.label}{row.affects_settings && <Badge variant="outline" className="ml-2">affects settings</Badge>}</td>
                        <td className="pr-2">{row.change === "added" ? "—" : displayValue(row.previous)}</td>
                        <td>{row.change === "removed" ? "Removed" : displayValue(row.current)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}
            <section data-testid="questionnaire-review-changes">
              <h3 className="font-medium">Proposed draft settings</h3>
              {data.proposed_changes.length === 0 ? <p className="text-muted-foreground">No settings change.</p> : (
                <table className="mt-1 w-full text-left text-xs">
                  <thead><tr className="text-muted-foreground"><th className="py-1">Setting</th><th>Current</th><th>Proposed</th></tr></thead>
                  <tbody>{data.proposed_changes.map((c) => <tr key={c.target}><td className="py-1 pr-2">{c.label}</td><td className="pr-2">{displayValue(c.from)}</td><td>{displayValue(c.to)}</td></tr>)}</tbody>
                </table>
              )}
            </section>
            <section className="grid gap-3 md:grid-cols-2" data-testid="questionnaire-review-brief">
              {data.brief.map((section) => (
                <div key={section.id} className="rounded border p-3">
                  <div className="font-medium">{section.title}</div>
                  <dl className="mt-1 space-y-1">
                    {section.items.map((item) => <div key={item.key}><dt className="text-xs text-muted-foreground">{item.label}</dt><dd>{item.value}</dd></div>)}
                  </dl>
                </div>
              ))}
            </section>
            {returning && (
              <div className="space-y-2">
                <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="What should the owner change?" data-testid="questionnaire-return-reason" />
              </div>
            )}
            {submission?.status === "reviewed" && (
              <p className="flex items-center gap-2 text-emerald-700"><CheckCircle2 className="size-4" />Applied to the draft store.</p>
            )}
          </div>
        )}
        <DialogFooter className="gap-2 sm:justify-between">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <div className="flex flex-wrap gap-2">
            {application && (
              <Button variant="outline" onClick={() => reverse.mutate()} disabled={reverse.isPending}><Undo2 className="size-4 mr-2" />Reverse</Button>
            )}
            {data?.can_apply && (returning ? (
              <Button variant="outline" onClick={() => sendBack.mutate()} disabled={!reason.trim() || sendBack.isPending} data-testid="questionnaire-return-confirm">Send back to owner</Button>
            ) : (
              <Button variant="outline" onClick={() => setReturning(true)} data-testid="questionnaire-return">Return for changes</Button>
            ))}
            {data?.can_apply && (
              <Button onClick={() => approve.mutate()} disabled={approve.isPending} data-testid="questionnaire-approve-apply">{approve.isPending ? "Applying..." : "Approve & Apply"}</Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
