import ContextualHelp from "@/components/help/ContextualHelp";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STATUS_LABELS = {
  draft: "Owner is filling it in",
  submitted: "Ready for review",
  returned_for_changes: "Returned to owner",
  reviewed: "Approved and applied",
};

export default function OverviewQuestionnaireCard({ model }) {
  const { questionnaire, questionnaireSubmission, setReviewOpen } = model;
  const status = questionnaireSubmission?.status;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Questionnaire <ContextualHelp surfaceKey="webstores.questionnaire" module="webstores" /></CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-muted-foreground">
          {(questionnaire.data?.templates || []).length} Form Maker questionnaire{(questionnaire.data?.templates || []).length === 1 ? "" : "s"} bound to this store.
        </span>
        {status ? (
          <Badge variant={status === "submitted" ? "default" : "secondary"} data-testid="questionnaire-status">
            {STATUS_LABELS[status] || status}{questionnaireSubmission.revision ? ` · revision ${questionnaireSubmission.revision}` : ""}
          </Badge>
        ) : (
          <Badge variant="secondary">Not started</Badge>
        )}
        {questionnaireSubmission?.revision && (
          <Button size="sm" onClick={() => setReviewOpen(true)} data-testid="questionnaire-open-review">Review answers</Button>
        )}
      </CardContent>
    </Card>
  );
}
