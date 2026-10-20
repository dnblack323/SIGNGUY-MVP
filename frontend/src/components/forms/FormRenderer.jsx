import FormQuestionInput from "@/components/forms/FormQuestionInput";

export function formQuestionIsVisible(question, answers) {
  const rule = question?.conditional || question?.conditional_visibility;
  const dependsOn = rule?.depends_on || rule?.question_key;
  if (!dependsOn) return true;
  const actual = answers?.[dependsOn];
  const expected = rule.value;
  if (rule.operator === "not_equals") return actual !== expected;
  if (rule.operator === "includes_any") {
    const wanted = (Array.isArray(expected) ? expected : [expected]).map(String);
    const values = Array.isArray(actual) ? actual : [actual];
    return values.some((v) => v !== undefined && v !== null && v !== "" && wanted.includes(String(v)));
  }
  if (rule.operator === "contains" || rule.operator === "includes")
    return Array.isArray(actual)
      ? actual.includes(expected)
      : String(actual || "").includes(String(expected || ""));
  if (rule.operator === "greater_than")
    return Number(actual) > Number(expected);
  if (rule.operator === "less_than") return Number(actual) < Number(expected);
  return actual === expected;
}

/** Keys currently shown: a question is hidden if its rule fails or the question it depends on is hidden. */
export function formVisibleKeys(sections, answers) {
  const byKey = new Map();
  sections.forEach((s) => (s.questions || []).forEach((q) => byKey.set(q.key, q)));
  const memo = new Map();
  const shown = (key, depth = 0) => {
    if (memo.has(key)) return memo.get(key);
    const question = byKey.get(key);
    const rule = question?.conditional || question?.conditional_visibility;
    const parent = rule?.depends_on || rule?.question_key;
    let result = formQuestionIsVisible(question, answers);
    if (result && parent && parent !== key && byKey.has(parent) && depth < 20) result = shown(parent, depth + 1);
    memo.set(key, result);
    return result;
  };
  return new Set([...byKey.keys()].filter((key) => key && shown(key)));
}

export default function FormRenderer({
  sections = [],
  answers = {},
  onAnswersChange,
  readOnly = false,
  lockedAnswerIds = [],
  onFileSelected,
}) {
  const locked = new Set(lockedAnswerIds);
  const visible = formVisibleKeys(sections, answers);
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
            .filter((question) => visible.has(question.key))
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
                    onFileSelected={onFileSelected}
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
