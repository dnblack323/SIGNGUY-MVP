import FormQuestionInput from "@/components/forms/FormQuestionInput";

export function formQuestionIsVisible(question, answers) {
  const rule = question?.conditional || question?.conditional_visibility;
  const dependsOn = rule?.depends_on || rule?.question_key;
  if (!dependsOn) return true;
  const actual = answers?.[dependsOn];
  const expected = rule.value;
  if (rule.operator === "not_equals") return actual !== expected;
  if (rule.operator === "contains" || rule.operator === "includes")
    return Array.isArray(actual)
      ? actual.includes(expected)
      : String(actual || "").includes(String(expected || ""));
  if (rule.operator === "greater_than")
    return Number(actual) > Number(expected);
  if (rule.operator === "less_than") return Number(actual) < Number(expected);
  return actual === expected;
}

export default function FormRenderer({
  sections = [],
  answers = {},
  onAnswersChange,
  readOnly = false,
  lockedAnswerIds = [],
}) {
  const locked = new Set(lockedAnswerIds);
  const update = (key, value) => {
    if (readOnly || typeof onAnswersChange !== "function") return;
    onAnswersChange({ ...answers, [key]: value });
  };

  return (
    <div className="space-y-3" data-testid="shared-form-renderer">
      {sections.map((section) => (
        <div
          key={section.id || section.title}
          className="rounded border p-3 space-y-3"
        >
          {section.title && <div className="font-medium">{section.title}</div>}
          {section.description && (
            <p className="text-sm text-muted-foreground">
              {section.description}
            </p>
          )}
          {(section.questions || [])
            .filter((question) => formQuestionIsVisible(question, answers))
            .map((question) => (
              <div key={question.key} className="grid gap-1.5 text-sm">
                {!["heading", "paragraph"].includes(question.type) && (
                  <span>
                    {question.label}
                    {question.required && !locked.has(question.key) && (
                      <span className="text-rose-600"> *</span>
                    )}
                    {locked.has(question.key) && (
                      <span className="ml-2 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                        Set by shop
                      </span>
                    )}
                  </span>
                )}
                <div data-testid={`shared-form-answer-${question.key}`}>
                  <FormQuestionInput
                    question={question}
                    value={answers[question.key]}
                    onChange={(value) => update(question.key, value)}
                    readOnly={readOnly || locked.has(question.key)}
                  />
                </div>
                {question.description && (
                  <span className="text-xs text-muted-foreground">
                    {question.description}
                  </span>
                )}
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}
