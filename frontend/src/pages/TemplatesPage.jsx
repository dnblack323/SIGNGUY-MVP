import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Plus, RotateCcw, Archive } from "lucide-react";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";

const TYPES = [
  ["intake", "Intake"],
  ["questionnaire", "Questionnaire"],
  ["decision_options", "Decision options"],
];

const STARTER_BODY = {
  intake: { project_name: "New templated intake", items: [{ item_name: "New item", description: "Describe the work", quantity: 1 }] },
  questionnaire: { prompt_config: { fields: [{ key: "project_notes", label: "Project notes", type: "textarea" }] } },
  decision_options: { options: [{ customer_label: "Standard", headline: "Standard option", manual_price_cents: 0 }] },
};

export default function TemplatesPage() {
  const qc = useQueryClient();
  const [templateType, setTemplateType] = useState("intake");
  const [name, setName] = useState("");
  const [body, setBody] = useState(JSON.stringify(STARTER_BODY.intake, null, 2));
  const [target, setTarget] = useState("");

  const templates = useQuery({
    queryKey: ["templates", templateType],
    queryFn: async () => (await api.get("/templates", { params: { template_type: templateType } })).data,
  });
  const items = useMemo(() => templates.data?.items || [], [templates.data]);
  const activeItems = useMemo(() => items.filter((t) => t.active), [items]);
  const onError = (err) => toast.error(extractError(err));

  const create = useMutation({
    mutationFn: async () => api.post("/templates", { name, template_type: templateType, body: JSON.parse(body || "{}") }),
    onSuccess: () => { setName(""); qc.invalidateQueries({ queryKey: ["templates"] }); toast.success("Template saved"); },
    onError,
  });
  const archive = useMutation({
    mutationFn: async (id) => api.post(`/templates/${id}/archive`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["templates"] }); toast.success("Template archived"); },
    onError,
  });
  const restore = useMutation({
    mutationFn: async (id) => api.post(`/templates/${id}/restore`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["templates"] }); toast.success("Template restored"); },
    onError,
  });
  const apply = useMutation({
    mutationFn: async (tpl) => {
      const payload = tpl.template_type === "intake"
        ? { target_type: "new_intake" }
        : { target_type: tpl.template_type === "questionnaire" ? "customer_intake" : "decision_room", target_id: target };
      return api.post(`/templates/${tpl.id}/apply`, payload);
    },
    onSuccess: () => toast.success("Template applied"),
    onError,
  });

  function changeType(value) {
    setTemplateType(value);
    setBody(JSON.stringify(STARTER_BODY[value], null, 2));
  }

  return (
    <div className="space-y-4" data-testid="templates-page">
      <PageHeader title="Templates" subtitle="Reusable EC10 intake, questionnaire, and Decision Room option templates." />

      <div className="grid gap-3 rounded-xl border bg-card p-4 md:grid-cols-[180px_1fr]">
        <Select value={templateType} onValueChange={changeType}>
          <SelectTrigger data-testid="template-type-select"><SelectValue /></SelectTrigger>
          <SelectContent>{TYPES.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
        </Select>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Template name" data-testid="template-name-input" />
        <Textarea className="md:col-span-2 font-mono text-xs" rows={8} value={body} onChange={(e) => setBody(e.target.value)} data-testid="template-body-input" />
        <div className="md:col-span-2 flex justify-end">
          <Button disabled={!name.trim() || create.isPending} onClick={() => create.mutate()} data-testid="template-create-button">
            <Plus className="size-4 mr-1" />Save template
          </Button>
        </div>
      </div>

      <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="Target id for questionnaire or Decision Room apply" data-testid="template-target-input" />

      {templates.isLoading ? <TableSkeleton /> : activeItems.length === 0 ? (
        <EmptyState icon={FileText} title="No templates" description="Create a reusable EC10 template to start from a known intake, questionnaire, or option shape." />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="templates-table">
            <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Type</TableHead><TableHead>Version</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
            <TableBody>
              {items.map((tpl) => (
                <TableRow key={tpl.id} data-testid={`template-row-${tpl.id}`}>
                  <TableCell className="font-medium">{tpl.name}{!tpl.active && <span className="ml-2 text-xs text-muted-foreground">Archived</span>}</TableCell>
                  <TableCell>{String(tpl.template_type).replace("_", " ")}</TableCell>
                  <TableCell>v{tpl.version}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      {tpl.active && <Button size="sm" variant="outline" onClick={() => apply.mutate(tpl)} data-testid={`template-apply-${tpl.id}`}>Apply</Button>}
                      {tpl.active ? (
                        <Button size="icon" variant="outline" onClick={() => archive.mutate(tpl.id)} data-testid={`template-archive-${tpl.id}`}><Archive className="size-4" /></Button>
                      ) : (
                        <Button size="icon" variant="outline" onClick={() => restore.mutate(tpl.id)} data-testid={`template-restore-${tpl.id}`}><RotateCcw className="size-4" /></Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
