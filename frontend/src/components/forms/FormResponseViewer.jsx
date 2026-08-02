import { Badge } from "@/components/ui/badge";

function displayValue(value) {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return value == null || value === "" ? "Not answered" : String(value);
}

function questionRows(template = {}) {
  return (template.sections || []).flatMap((section) =>
    (section.questions || []).map((question) => ({
      ...question,
      section_title: section.title,
    })),
  );
}

export default function FormResponseViewer({
  template = {},
  response = {},
  mappingResults = [],
}) {
  const answers =
    response.submitted_snapshot?.answers || response.answers || {};
  const questions = questionRows(template);
  const mappingByKey = new Map(
    (mappingResults || response.mapping_results || []).map((item) => [
      item.answer_key || item.key,
      item,
    ]),
  );

  return (
    <div
      className="space-y-3 text-sm"
      data-testid="shared-form-response-viewer"
    >
      <div className="rounded border divide-y">
        {questions.map((question) => {
          const mapping = mappingByKey.get(question.key) || question.mapping;
          return (
            <div
              key={question.key}
              className="grid gap-2 p-3 md:grid-cols-[220px_1fr_180px]"
            >
              <div>
                <div className="font-medium">{question.label}</div>
                <div className="text-xs text-muted-foreground">
                  {question.section_title}
                </div>
              </div>
              <div className="text-muted-foreground">
                {displayValue(answers[question.key])}
              </div>
              <div>
                {mapping?.target ? (
                  <Badge variant="outline">{mapping.target}</Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    No mapping
                  </span>
                )}
              </div>
            </div>
          );
        })}
        {questions.length === 0 &&
          Object.entries(answers).map(([key, value]) => (
            <div key={key} className="grid gap-2 p-3 md:grid-cols-[220px_1fr]">
              <div className="font-medium">{key.replace(/_/g, " ")}</div>
              <div className="text-muted-foreground">{displayValue(value)}</div>
            </div>
          ))}
      </div>
      {(response.attachments || []).length > 0 && (
        <div className="rounded border p-3">
          <div className="font-medium">Attachments</div>
          <div className="mt-2 grid gap-1">
            {response.attachments.map((attachment, index) => (
              <div
                key={`${attachment.file_id || attachment.file_name}-${index}`}
                className="text-muted-foreground"
              >
                {attachment.file_name || attachment.file_id}{" "}
                {attachment.field_key ? `(${attachment.field_key})` : ""}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
