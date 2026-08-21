import { Save, Send } from "lucide-react";
import FormRenderer from "@/components/forms/FormRenderer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function OwnerPortalQuestionnaire({
  questionnaire,
  answers,
  onAnswersChange,
  onSaveDraft,
  onSubmit,
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Questionnaire</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <FormRenderer
          sections={(questionnaire?.templates || []).flatMap(
            (template) => template.sections || [],
          )}
          answers={answers}
          onAnswersChange={onAnswersChange}
          lockedAnswerIds={(questionnaire?.templates || []).flatMap(
            (template) => template.locked_answer_ids || [],
          )}
        />
        <div className="flex gap-2">
          <Button variant="outline" onClick={onSaveDraft}>
            <Save className="size-4 mr-2" />
            Save draft
          </Button>
          <Button onClick={onSubmit}>
            <Send className="size-4 mr-2" />
            Submit
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
