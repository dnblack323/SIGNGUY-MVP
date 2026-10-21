import { CheckCircle2, Save, Send } from "lucide-react";
import FormRenderer from "@/components/forms/FormRenderer";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SAVE_LABELS = { saving: "Saving...", saved: "All changes saved", unsaved: "Unsaved changes", error: "Not saved — check your connection" };

export default function OwnerPortalQuestionnaire({
  questionnaire,
  answers,
  onAnswersChange,
  onSaveDraft,
  onSubmit,
  onFileSelected,
  saveState = "idle",
  submitting = false,
}) {
  const latest = questionnaire?.latest_revision;
  const open = Boolean(questionnaire?.submission) || !latest;
  const returned = open && latest?.status === "returned_for_changes";
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Questionnaire</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {returned && (
            <Alert data-testid="owner-questionnaire-returned">
              <AlertTitle>The shop asked for changes</AlertTitle>
              <AlertDescription>{latest.returned_reason}</AlertDescription>
            </Alert>
          )}
          {!open ? (
            <p className="flex items-center gap-2 text-sm text-emerald-700" data-testid="owner-questionnaire-submitted">
              <CheckCircle2 className="size-4" />
              {latest.status === "reviewed" ? "Your answers were reviewed and applied." : `Revision ${latest.revision} was submitted. The shop is reviewing it.`}
            </p>
          ) : (
            <>
              <FormRenderer
                sections={(questionnaire?.templates || []).flatMap((template) => template.sections || [])}
                answers={answers}
                onAnswersChange={onAnswersChange}
                onFileSelected={onFileSelected}
                lockedAnswerIds={(questionnaire?.templates || []).flatMap((template) => template.locked_answer_ids || [])}
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" onClick={onSaveDraft}>
                  <Save className="size-4 mr-2" />
                  Save draft
                </Button>
                <Button onClick={onSubmit} disabled={submitting} data-testid="owner-questionnaire-submit">
                  <Send className="size-4 mr-2" />
                  {submitting ? "Submitting..." : "Submit"}
                </Button>
                {SAVE_LABELS[saveState] && <span className="text-xs text-muted-foreground" data-testid="owner-questionnaire-save-state">{SAVE_LABELS[saveState]}</span>}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </>
  );
}

// The welcome text sent with the information packet, shown on the portal Overview.
export function OwnerPortalWelcome({ welcome }) {
  if (!welcome) return null;
  return (
    <Card data-testid="owner-portal-welcome">
      <CardHeader><CardTitle className="text-base">{welcome.title}</CardTitle></CardHeader>
      <CardContent><pre className="whitespace-pre-wrap font-sans text-sm text-muted-foreground">{welcome.body}</pre></CardContent>
    </Card>
  );
}
