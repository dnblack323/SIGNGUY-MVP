import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, FileQuestion } from "lucide-react";
import FormRenderer, {
  formQuestionIsVisible,
} from "@/components/forms/FormRenderer";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { extractError } from "@/lib/api";
import { getPublicFormRequest, submitPublicFormResponse } from "@/lib/forms";
import { toast } from "sonner";

function answerIsEmpty(value) {
  if (value == null) return true;
  if (typeof value === "string") return value.trim() === "";
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value).length === 0;
  return false;
}

function visibleQuestions(sections = [], answers = {}) {
  return sections.flatMap((section) =>
    (section.questions || []).filter((question) =>
      formQuestionIsVisible(question, answers),
    ),
  );
}

function attachmentRefs(sections = [], answers = {}) {
  return visibleQuestions(sections, answers)
    .filter(
      (question) => question.type === "file_upload" && answers[question.key],
    )
    .map((question) => ({ ...answers[question.key], field_key: question.key }))
    .filter((item) => item.file_id || item.file_name);
}

export default function PublicFormRequestPage() {
  const { token } = useParams();
  const [answers, setAnswers] = useState({});
  const [respondent, setRespondent] = useState({ name: "", email: "" });
  const [submitted, setSubmitted] = useState(false);
  const request = useQuery({
    queryKey: ["public-form-request", token],
    queryFn: () => getPublicFormRequest(token),
    enabled: Boolean(token),
  });
  const template = request.data?.template || {};
  const sections = useMemo(() => template.sections || [], [template.sections]);
  const missingRequired = useMemo(
    () =>
      visibleQuestions(sections, answers)
        .filter(
          (question) =>
            question.required &&
            !["heading", "paragraph"].includes(question.type) &&
            answerIsEmpty(answers[question.key]),
        )
        .map((question) => question.label),
    [sections, answers],
  );
  const submit = useMutation({
    mutationFn: () =>
      submitPublicFormResponse(token, {
        respondent_name: respondent.name,
        respondent_email: respondent.email,
        answers,
        attachments: attachmentRefs(sections, answers),
      }),
    onSuccess: () => setSubmitted(true),
    onError: (err) => toast.error(extractError(err)),
  });

  if (request.isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-slate-100 text-slate-700">
        Loading form...
      </div>
    );
  }

  if (request.isError) {
    return (
      <div className="grid min-h-screen place-items-center bg-slate-100 p-4">
        <Alert className="max-w-xl border-rose-200 bg-white">
          <FileQuestion className="size-4" />
          <AlertTitle>Form unavailable</AlertTitle>
          <AlertDescription>
            {extractError(
              request.error,
              "This form link is unavailable or expired.",
            )}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="grid min-h-screen place-items-center bg-slate-100 p-4">
        <Card className="w-full max-w-xl">
          <CardContent className="grid gap-3 p-6 text-center">
            <CheckCircle2 className="mx-auto size-10 text-emerald-600" />
            <h1 className="text-xl font-semibold">Answers submitted</h1>
            <p className="text-sm text-muted-foreground">
              The shop has been notified and will review your answers before
              applying anything to the Webstore setup.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 px-4 py-8">
      <Card className="mx-auto max-w-3xl">
        <CardHeader>
          <CardTitle>{template.name || "Questionnaire"}</CardTitle>
          {template.description && (
            <p className="text-sm text-muted-foreground">
              {template.description}
            </p>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 rounded border bg-slate-50 p-3 md:grid-cols-2">
            <div className="grid gap-1.5">
              <Label>Your name</Label>
              <Input
                value={respondent.name}
                onChange={(event) =>
                  setRespondent({ ...respondent, name: event.target.value })
                }
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Email</Label>
              <Input
                type="email"
                value={respondent.email}
                onChange={(event) =>
                  setRespondent({ ...respondent, email: event.target.value })
                }
              />
            </div>
          </div>
          <FormRenderer
            sections={sections}
            answers={answers}
            onAnswersChange={setAnswers}
          />
          {missingRequired.length > 0 && (
            <Alert className="border-amber-200 bg-amber-50">
              <AlertTitle>Required answers missing</AlertTitle>
              <AlertDescription>{missingRequired.join(", ")}</AlertDescription>
            </Alert>
          )}
          <Button
            className="w-full"
            disabled={submit.isPending || missingRequired.length > 0}
            onClick={() => submit.mutate()}
          >
            Submit answers
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
