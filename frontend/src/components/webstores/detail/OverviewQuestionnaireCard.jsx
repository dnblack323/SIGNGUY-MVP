import FormResponseViewer from "@/components/forms/FormResponseViewer";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { editableAnswerValue } from "./WebstoreDetailUtils";

export default function OverviewQuestionnaireCard({ model }) {
  const {
    answerPreview,
    applyAnswers,
    id,
    lastApplication,
    previewAnswers,
    proposedValues,
    questionnaire,
    questionnaireResponse,
    questionnaireReviewResponse,
    questionnaireReviewTemplate,
    reverseAnswers,
    selectedAnswerKeys,
    setProposedValues,
    setSelectedAnswerKeys,
    templates,
  } = model;

return (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Questionnaire Review
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="text-muted-foreground">
                  {(questionnaire.data?.templates || []).length} active template
                  section groups bound to this Webstore.
                </div>
                {questionnaireResponse.data?.submission ? (
                  <>
                    {Object.keys(
                      questionnaireResponse.data.submission.submitted_snapshot
                        ?.answers ||
                        questionnaireResponse.data.submission.answers ||
                        {},
                    ).length > 0 && (
                      <div
                        className="rounded border p-3 space-y-2"
                        data-testid="webstore-answer-selection"
                      >
                        <div>
                          <div className="font-medium">
                            Select answers to apply
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Submitted answers stay unchanged. Only selected
                            answers are previewed and applied to setup fields.
                          </div>
                        </div>
                        {Object.entries(
                          questionnaireResponse.data.submission
                            .submitted_snapshot?.answers ||
                            questionnaireResponse.data.submission.answers ||
                            {},
                        ).map(([key, value]) => (
                          <label
                            key={key}
                            className="grid gap-1.5 md:grid-cols-[180px_1fr] items-center text-sm"
                          >
                            <span className="flex items-center gap-2">
                              <Checkbox
                                checked={selectedAnswerKeys.includes(key)}
                                onCheckedChange={(checked) => {
                                  setSelectedAnswerKeys(
                                    checked
                                      ? [...selectedAnswerKeys, key]
                                      : selectedAnswerKeys.filter(
                                          (item) => item !== key,
                                        ),
                                  );
                                  setProposedValues({
                                    ...proposedValues,
                                    [key]:
                                      proposedValues[key] ??
                                      editableAnswerValue(value),
                                  });
                                }}
                                data-testid={`webstore-select-answer-${key}`}
                              />
                              {key.replace(/_/g, " ")}
                            </span>
                            <Input
                              value={
                                proposedValues[key] ??
                                editableAnswerValue(value)
                              }
                              onChange={(e) =>
                                setProposedValues({
                                  ...proposedValues,
                                  [key]: e.target.value,
                                })
                              }
                              disabled={!selectedAnswerKeys.includes(key)}
                              data-testid={`webstore-proposed-answer-${key}`}
                            />
                          </label>
                        ))}
                      </div>
                    )}
                    <div className="rounded border bg-slate-50 p-3">
                      <div className="font-medium">
                        Latest response:{" "}
                        {questionnaireResponse.data.submission.status}
                      </div>
                      {questionnaireReviewResponse && (
                        <div className="mt-2">
                          <FormResponseViewer
                            template={questionnaireReviewTemplate}
                            response={questionnaireReviewResponse}
                          />
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        onClick={() => previewAnswers.mutate()}
                        disabled={
                          previewAnswers.isPending ||
                          selectedAnswerKeys.length === 0
                        }
                      >
                        Preview apply
                      </Button>
                      <Button
                        onClick={() => applyAnswers.mutate()}
                        disabled={
                          !questionnaireResponse.data?.submission?.id ||
                          applyAnswers.isPending ||
                          selectedAnswerKeys.length === 0
                        }
                      >
                        Apply safe answers
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => reverseAnswers.mutate()}
                        disabled={!lastApplication || reverseAnswers.isPending}
                      >
                        Reverse last apply
                      </Button>
                    </div>
                    {answerPreview && (
                      <div
                        className="rounded border p-3"
                        data-testid="webstore-answer-preview"
                      >
                        <div className="font-medium">Safe changes</div>
                        {(answerPreview.proposed_changes || []).map(
                          (change) => (
                            <div key={`${change.answer_key}-${change.target}`}>
                              {change.label}: {String(change.from || "")} to{" "}
                              {String(change.to || "")}
                            </div>
                          ),
                        )}
                        {(answerPreview.rejected_changes || []).length > 0 && (
                          <div className="mt-2 text-amber-700">
                            Rejected:{" "}
                            {answerPreview.rejected_changes
                              .map((c) => c.answer_key)
                              .join(", ")}
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-muted-foreground">
                    No submitted owner questionnaire yet.
                  </div>
                )}
              </CardContent>
            </Card>
  );
}
