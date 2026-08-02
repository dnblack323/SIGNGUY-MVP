import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export default function FormQuestionInput({
  question,
  value,
  onChange,
  readOnly = false,
}) {
  const type = question?.type || "text";
  const options = question?.options || [];

  if (type === "heading") {
    return <h3 className="text-base font-semibold">{question.label}</h3>;
  }
  if (type === "paragraph") {
    return (
      <p className="rounded border bg-slate-50 p-3 text-sm text-muted-foreground">
        {question.label}
      </p>
    );
  }
  if (type === "textarea" || type === "signature") {
    return (
      <Textarea
        rows={type === "signature" ? 2 : 3}
        value={value || ""}
        disabled={readOnly}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }
  if (type === "select") {
    return (
      <select
        className="rounded-md border bg-white px-3 py-2 text-sm"
        value={value || ""}
        disabled={readOnly}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Choose one</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }
  if (type === "radio") {
    return (
      <div className="grid gap-2 rounded-md border p-2">
        {options.map((option) => (
          <label key={option.value} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              disabled={readOnly}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    );
  }
  if (type === "checkbox" || type === "multi_select") {
    const selected = Array.isArray(value) ? value : [];
    return (
      <div className="grid gap-2 rounded-md border p-2">
        {options.map((option) => (
          <label key={option.value} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              disabled={readOnly}
              checked={selected.includes(option.value)}
              onChange={(event) =>
                onChange(
                  event.target.checked
                    ? [...selected, option.value]
                    : selected.filter((item) => item !== option.value),
                )
              }
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    );
  }
  if (type === "file_upload") {
    return (
      <Input
        type="file"
        disabled={readOnly}
        accept={(question.file_settings?.accept || []).join(",")}
        onChange={(event) => {
          const file = event.target.files?.[0];
          onChange(
            file
              ? {
                  file_name: file.name,
                  size_bytes: file.size,
                  content_type: file.type,
                  field_key: question.key,
                }
              : null,
          );
        }}
      />
    );
  }

  const inputType = ["date", "email", "number"].includes(type) ? type : "text";
  return (
    <Input
      type={inputType}
      value={value || ""}
      disabled={readOnly}
      placeholder={question.placeholder || ""}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
