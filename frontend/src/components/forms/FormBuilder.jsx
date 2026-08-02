import { Copy, GripVertical, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export const FORM_QUESTION_TYPES = [
  { value: "text", label: "Text (Single Line)" },
  { value: "textarea", label: "Text (Multi-Line)" },
  { value: "number", label: "Number" },
  { value: "email", label: "Email" },
  { value: "phone", label: "Phone Number" },
  { value: "select", label: "Dropdown Select" },
  { value: "multi_select", label: "Multi-Select" },
  { value: "radio", label: "Radio Buttons" },
  { value: "checkbox", label: "Checkboxes" },
  { value: "date", label: "Date Picker" },
  { value: "file_upload", label: "File Upload" },
  { value: "signature", label: "Signature" },
  { value: "heading", label: "Section Heading" },
  { value: "paragraph", label: "Paragraph Text" },
];

const OPTION_TYPES = new Set(["select", "multi_select", "radio", "checkbox"]);
const NON_INPUT_TYPES = new Set(["heading", "paragraph"]);
const WEBSTORE_STORE_TYPES = [
  { value: "all", label: "All Webstores" },
  { value: "base", label: "Base setup" },
  { value: "b2b", label: "B2B" },
  { value: "fundraiser", label: "Fundraiser" },
  { value: "event", label: "Event" },
  { value: "promotional", label: "Promotional" },
  { value: "employee", label: "Employee" },
  { value: "general", label: "General" },
];

function makeQuestion(type = "text", index = 0) {
  const id = `q-${Math.random().toString(36).slice(2, 8)}`;
  return {
    id,
    key: id,
    type,
    label: type === "heading" ? "Section heading" : "Question",
    description: "",
    placeholder: "",
    required: false,
    options: OPTION_TYPES.has(type)
      ? [{ value: "option_1", label: "Option 1" }]
      : [],
    validation: {},
    conditional: {},
    accept_file_types: type === "file_upload" ? ["image/*", ".pdf"] : [],
    max_file_size_mb: type === "file_upload" ? 10 : undefined,
    order: index,
  };
}

function makeSection(index = 0) {
  return {
    id: `section-${index + 1}`,
    title: `Section ${index + 1}`,
    description: "",
    questions: [],
  };
}

function OptionEditor({ question, onChange }) {
  const options = question.options || [];
  return (
    <div className="grid gap-2 rounded-md border bg-slate-50 p-2">
      <Label className="text-xs">Options</Label>
      {options.map((option, index) => (
        <div
          key={`${option.value}-${index}`}
          className="grid gap-2 md:grid-cols-[1fr_1fr_auto]"
        >
          <Input
            value={option.value || ""}
            placeholder="value"
            onChange={(event) =>
              onChange({
                ...question,
                options: options.map((item, i) =>
                  i === index ? { ...item, value: event.target.value } : item,
                ),
              })
            }
          />
          <Input
            value={option.label || ""}
            placeholder="label"
            onChange={(event) =>
              onChange({
                ...question,
                options: options.map((item, i) =>
                  i === index ? { ...item, label: event.target.value } : item,
                ),
              })
            }
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() =>
              onChange({
                ...question,
                options: options.filter((_, i) => i !== index),
              })
            }
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() =>
          onChange({
            ...question,
            options: [
              ...options,
              {
                value: `option_${options.length + 1}`,
                label: `Option ${options.length + 1}`,
              },
            ],
          })
        }
      >
        Add Option
      </Button>
    </div>
  );
}

function ConditionalRuleEditor({ question, allQuestions, onChange }) {
  const conditional = question.conditional || {};
  return (
    <div className="grid gap-2 rounded-md border bg-slate-50 p-2 md:grid-cols-3">
      <div className="grid gap-1">
        <Label className="text-xs">Show when question</Label>
        <Select
          value={conditional.depends_on || "__none__"}
          onValueChange={(value) =>
            onChange({
              ...question,
              conditional:
                value === "__none__"
                  ? {}
                  : { ...conditional, depends_on: value },
            })
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">No condition</SelectItem>
            {allQuestions
              .filter(
                (item) =>
                  item.key !== question.key && !NON_INPUT_TYPES.has(item.type),
              )
              .map((item) => (
                <SelectItem key={item.key} value={item.key}>
                  {item.label || item.key}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-1">
        <Label className="text-xs">Operator</Label>
        <Select
          value={conditional.operator || "equals"}
          onValueChange={(operator) =>
            onChange({ ...question, conditional: { ...conditional, operator } })
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="equals">Equals</SelectItem>
            <SelectItem value="not_equals">Does not equal</SelectItem>
            <SelectItem value="contains">Contains</SelectItem>
            <SelectItem value="greater_than">Greater than</SelectItem>
            <SelectItem value="less_than">Less than</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-1">
        <Label className="text-xs">Value</Label>
        <Input
          value={conditional.value || ""}
          onChange={(event) =>
            onChange({
              ...question,
              conditional: { ...conditional, value: event.target.value },
            })
          }
        />
      </div>
    </div>
  );
}

function QuestionEditor({
  question,
  allQuestions,
  onChange,
  onDuplicate,
  onRemove,
}) {
  const usesOptions = OPTION_TYPES.has(question.type);
  const isInput = !NON_INPUT_TYPES.has(question.type);
  return (
    <div
      className="rounded-md border p-3 space-y-3"
      data-testid={`shared-form-question-${question.key}`}
    >
      <div className="grid gap-2 md:grid-cols-[auto_1fr_220px_auto_auto] md:items-center">
        <GripVertical className="size-4 text-muted-foreground" />
        <Input
          value={question.label || ""}
          placeholder="Question label"
          onChange={(event) =>
            onChange({ ...question, label: event.target.value })
          }
        />
        <Select
          value={question.type || "text"}
          onValueChange={(type) =>
            onChange({
              ...question,
              ...makeQuestion(type, question.order),
              id: question.id,
              key: question.key,
              label: question.label,
              type,
            })
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {FORM_QUESTION_TYPES.map((type) => (
              <SelectItem key={type.value} value={type.value}>
                {type.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="button" variant="ghost" size="icon" onClick={onDuplicate}>
          <Copy className="size-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" onClick={onRemove}>
          <Trash2 className="size-4" />
        </Button>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        <Input
          value={question.key || ""}
          placeholder="answer_key"
          onChange={(event) =>
            onChange({ ...question, key: event.target.value })
          }
        />
        <Input
          value={question.placeholder || ""}
          placeholder="Placeholder"
          disabled={!isInput}
          onChange={(event) =>
            onChange({ ...question, placeholder: event.target.value })
          }
        />
      </div>
      <Textarea
        rows={2}
        value={question.description || ""}
        placeholder="Description or help text"
        onChange={(event) =>
          onChange({ ...question, description: event.target.value })
        }
      />
      {isInput && (
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={Boolean(question.required)}
            onCheckedChange={(checked) =>
              onChange({ ...question, required: Boolean(checked) })
            }
          />
          Required
        </label>
      )}
      {usesOptions && <OptionEditor question={question} onChange={onChange} />}
      {question.type === "file_upload" && (
        <div className="grid gap-2 rounded-md border bg-slate-50 p-2 md:grid-cols-2">
          <div className="grid gap-1">
            <Label className="text-xs">Accepted file types</Label>
            <Input
              value={(question.accept_file_types || []).join(", ")}
              onChange={(event) =>
                onChange({
                  ...question,
                  accept_file_types: event.target.value
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
                })
              }
            />
          </div>
          <div className="grid gap-1">
            <Label className="text-xs">Max file size MB</Label>
            <Input
              type="number"
              min="1"
              value={question.max_file_size_mb || 10}
              onChange={(event) =>
                onChange({
                  ...question,
                  max_file_size_mb: Number(event.target.value) || 10,
                })
              }
            />
          </div>
        </div>
      )}
      {isInput && (
        <ConditionalRuleEditor
          question={question}
          allQuestions={allQuestions}
          onChange={onChange}
        />
      )}
    </div>
  );
}

export default function FormBuilder({ value = {}, onChange }) {
  const sections = value.sections?.length ? value.sections : [makeSection(0)];
  const allQuestions = sections.flatMap((section) => section.questions || []);
  const updateSections = (nextSections) =>
    onChange({ ...value, sections: nextSections });
  const privateConfig = value.private_config || {};
  const updateSection = (sectionIndex, patch) =>
    updateSections(
      sections.map((section, index) =>
        index === sectionIndex ? { ...section, ...patch } : section,
      ),
    );
  const updateQuestion = (sectionIndex, questionIndex, question) =>
    updateSection(sectionIndex, {
      questions: (sections[sectionIndex].questions || []).map((item, index) =>
        index === questionIndex ? question : item,
      ),
    });

  return (
    <div className="space-y-4" data-testid="shared-form-builder">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Form Details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          <div className="grid gap-1.5">
            <Label>Name</Label>
            <Input
              value={value.name || ""}
              onChange={(event) =>
                onChange({ ...value, name: event.target.value })
              }
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Module</Label>
            <Input
              value={value.module || "general"}
              onChange={(event) =>
                onChange({ ...value, module: event.target.value })
              }
            />
          </div>
          {(value.module || "general") === "webstores" && (
            <div className="grid gap-1.5 md:col-span-2">
              <Label>Webstore questionnaire type</Label>
              <Select
                value={privateConfig.store_type || "all"}
                onValueChange={(storeType) =>
                  onChange({
                    ...value,
                    private_config: {
                      ...privateConfig,
                      adapter: "webstore_questionnaire",
                      store_type: storeType === "all" ? undefined : storeType,
                    },
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {WEBSTORE_STORE_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="grid gap-1.5 md:col-span-2">
            <Label>Description</Label>
            <Textarea
              rows={2}
              value={value.description || ""}
              onChange={(event) =>
                onChange({ ...value, description: event.target.value })
              }
            />
          </div>
        </CardContent>
      </Card>
      {sections.map((section, sectionIndex) => (
        <Card key={section.id || sectionIndex}>
          <CardHeader>
            <CardTitle className="grid gap-2 text-base md:grid-cols-[1fr_auto]">
              <Input
                value={section.title || ""}
                onChange={(event) =>
                  updateSection(sectionIndex, { title: event.target.value })
                }
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  updateSections(
                    sections.filter((_, index) => index !== sectionIndex),
                  )
                }
              >
                Remove Section
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              rows={2}
              value={section.description || ""}
              placeholder="Section description"
              onChange={(event) =>
                updateSection(sectionIndex, { description: event.target.value })
              }
            />
            {(section.questions || []).map((question, questionIndex) => (
              <QuestionEditor
                key={question.id || question.key}
                question={question}
                allQuestions={allQuestions}
                onChange={(nextQuestion) =>
                  updateQuestion(sectionIndex, questionIndex, nextQuestion)
                }
                onDuplicate={() =>
                  updateSection(sectionIndex, {
                    questions: [
                      ...(section.questions || []),
                      {
                        ...question,
                        id: `q-${Math.random().toString(36).slice(2, 8)}`,
                        key: `${question.key}_copy`,
                      },
                    ],
                  })
                }
                onRemove={() =>
                  updateSection(sectionIndex, {
                    questions: (section.questions || []).filter(
                      (_, index) => index !== questionIndex,
                    ),
                  })
                }
              />
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                updateSection(sectionIndex, {
                  questions: [
                    ...(section.questions || []),
                    makeQuestion("text", (section.questions || []).length),
                  ],
                })
              }
            >
              <Plus className="size-4 mr-1" />
              Add Question
            </Button>
          </CardContent>
        </Card>
      ))}
      <Button
        type="button"
        variant="outline"
        onClick={() =>
          updateSections([...sections, makeSection(sections.length)])
        }
      >
        Add Section
      </Button>
    </div>
  );
}
