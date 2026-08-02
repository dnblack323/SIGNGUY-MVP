import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  Copy,
  Eye,
  FileQuestion,
  Plus,
  Save,
  Send,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import EmptyState from "@/components/common/EmptyState";
import FormBuilder from "@/components/forms/FormBuilder";
import FormRenderer from "@/components/forms/FormRenderer";
import FormResponseViewer from "@/components/forms/FormResponseViewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { extractError } from "@/lib/api";
import {
  archiveFormTemplate,
  createFormTemplate,
  duplicateFormTemplate,
  listFormResponses,
  listFormTemplates,
  publishFormTemplate,
  updateFormTemplate,
} from "@/lib/forms";
import { toast } from "sonner";

const emptyTemplate = {
  name: "",
  module: "webstores",
  context_type: "webstore",
  description: "",
  status: "draft",
  sections: [
    { id: "main", title: "Questions", description: "", questions: [] },
  ],
};

export default function FormsLibraryPage() {
  const qc = useQueryClient();
  const [moduleFilter, setModuleFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState(emptyTemplate);
  const [selected, setSelected] = useState(null);
  const [previewAnswers, setPreviewAnswers] = useState({});

  const templates = useQuery({
    queryKey: ["form-templates", moduleFilter],
    queryFn: () =>
      listFormTemplates({
        module: moduleFilter === "all" ? undefined : moduleFilter,
      }),
  });
  const responses = useQuery({
    queryKey: ["form-responses", selected?.id],
    queryFn: () => listFormResponses({ template_id: selected?.id }),
    enabled: Boolean(selected?.id),
  });
  const items = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = templates.data || [];
    if (!q) return rows;
    return rows.filter((item) =>
      `${item.name} ${item.description || ""} ${item.module}`
        .toLowerCase()
        .includes(q),
    );
  }, [templates.data, search]);
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["form-templates"] });
  const onError = (err) => toast.error(extractError(err));
  const create = useMutation({
    mutationFn: () => createFormTemplate(draft),
    onSuccess: (data) => {
      setSelected(data);
      setDraft(data);
      invalidate();
      toast.success("Form template saved");
    },
    onError,
  });
  const update = useMutation({
    mutationFn: () => updateFormTemplate(selected.id, draft),
    onSuccess: (data) => {
      setSelected(data);
      setDraft(data);
      invalidate();
      toast.success("Form template updated");
    },
    onError,
  });
  const publish = useMutation({
    mutationFn: (id) => publishFormTemplate(id),
    onSuccess: invalidate,
    onError,
  });
  const archive = useMutation({
    mutationFn: (id) => archiveFormTemplate(id),
    onSuccess: invalidate,
    onError,
  });
  const duplicate = useMutation({
    mutationFn: (id) => duplicateFormTemplate(id),
    onSuccess: invalidate,
    onError,
  });
  const load = (template) => {
    setSelected(template);
    setDraft(template);
    setPreviewAnswers({});
  };

  return (
    <div className="space-y-4" data-testid="forms-library-page">
      <PageHeader
        title="Form Maker"
        subtitle="Shared DocuLink/Library form builder. Webstores is the active adapter for this migration."
      />
      <div className="grid gap-4 xl:grid-cols-[420px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {selected ? "Edit Form Template" : "Create Form Template"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <FormBuilder value={draft} onChange={setDraft} />
            <div className="flex flex-wrap justify-between gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setSelected(null);
                  setDraft(emptyTemplate);
                  setPreviewAnswers({});
                }}
              >
                New Blank
              </Button>
              <div className="flex gap-2">
                {selected ? (
                  <Button
                    onClick={() => update.mutate()}
                    disabled={!draft.name.trim() || update.isPending}
                  >
                    <Save className="size-4 mr-1" />
                    Save
                  </Button>
                ) : (
                  <Button
                    onClick={() => create.mutate()}
                    disabled={!draft.name.trim() || create.isPending}
                  >
                    <Plus className="size-4 mr-1" />
                    Create
                  </Button>
                )}
                {selected && (
                  <Button
                    variant="outline"
                    onClick={() => publish.mutate(selected.id)}
                    disabled={publish.isPending}
                  >
                    <Send className="size-4 mr-1" />
                    Publish
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-3">
          <div className="grid gap-2 rounded border bg-card p-3 md:grid-cols-[180px_1fr]">
            <Select value={moduleFilter} onValueChange={setModuleFilter}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All modules</SelectItem>
                <SelectItem value="webstores">Webstores</SelectItem>
                <SelectItem value="general">General</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder="Search forms"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="rounded border border-dashed bg-slate-50 px-3 py-2 text-xs text-muted-foreground">
            Future consumers are recorded for later work: client design intake
            and employee training quizzes. This stage only enables Webstore
            questionnaires.
          </div>

          <Tabs defaultValue="templates">
            <TabsList>
              <TabsTrigger value="templates">Templates</TabsTrigger>
              <TabsTrigger value="preview">Preview</TabsTrigger>
              <TabsTrigger value="responses">Responses</TabsTrigger>
            </TabsList>
            <TabsContent value="templates" className="space-y-3">
              {items.length === 0 ? (
                <EmptyState
                  icon={FileQuestion}
                  title="No form templates"
                  description="Create or migrate a Webstores questionnaire template."
                />
              ) : (
                items.map((template) => (
                  <div
                    key={template.id}
                    className="rounded border bg-white p-3 text-sm"
                    data-testid={`form-template-${template.id}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">{template.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {template.module} - {template.context_type} - v
                          {template.version}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge
                          variant={
                            template.status === "published"
                              ? "secondary"
                              : "outline"
                          }
                        >
                          {template.status}
                        </Badge>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => load(template)}
                        >
                          <Eye className="size-4 mr-1" />
                          Open
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => duplicate.mutate(template.id)}
                        >
                          <Copy className="size-4 mr-1" />
                          Duplicate
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => archive.mutate(template.id)}
                        >
                          <Archive className="size-4 mr-1" />
                          Archive
                        </Button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </TabsContent>
            <TabsContent value="preview" className="space-y-3">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    {draft.name || "Form Preview"}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <FormRenderer
                    sections={draft.sections || []}
                    answers={previewAnswers}
                    onAnswersChange={setPreviewAnswers}
                  />
                </CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="responses" className="space-y-3">
              {(responses.data || []).map((response) => (
                <FormResponseViewer
                  key={response.id}
                  template={selected || draft}
                  response={response}
                />
              ))}
              {selected &&
                !responses.isLoading &&
                (responses.data || []).length === 0 && (
                  <EmptyState
                    icon={FileQuestion}
                    title="No responses"
                    description="Responses submitted through shared form requests will appear here."
                  />
                )}
              {!selected && (
                <EmptyState
                  icon={FileQuestion}
                  title="Select a form"
                  description="Open a form template to view its responses."
                />
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
