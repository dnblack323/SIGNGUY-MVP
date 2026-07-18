import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Copy, Eye, FileText, PackagePlus, Plus, RotateCcw, Save } from "lucide-react";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";

const TYPES = [
  ["all", "All types"],
  ["intake", "Intake"],
  ["questionnaire", "Questionnaire"],
  ["decision_options", "Decision options"],
  ["task", "Task"],
  ["task_checklist", "Task checklist"],
  ["appointment", "Appointment"],
  ["appointment_confirmation", "Appointment confirmation"],
  ["appointment_reminder", "Appointment reminder"],
  ["message", "Message"],
  ["announcement", "Announcement"],
  ["note", "Note"],
  ["daily_digest", "Daily digest"],
  ["email", "Email"],
  ["sms", "SMS content"],
  ["support_response", "Support response"],
  ["bug_response", "Bug response"],
  ["feature_request_response", "Feature response"],
  ["time_off_response", "Time-off response"],
];

const CHANNELS = [
  ["all", "All channels"],
  ["in_app", "In-app"],
  ["email_subject", "Email subject"],
  ["email_body", "Email body"],
  ["sms_body", "SMS body"],
  ["announcement_body", "Announcement"],
  ["note_body", "Note"],
  ["task_title", "Task title"],
  ["task_description", "Task description"],
  ["digest_section", "Digest section"],
];

const STARTER_BODY = {
  channels: {
    in_app: "Hello {{customer_name}} from {{shop_name}}.",
  },
};

function typeLabel(value) {
  return TYPES.find(([id]) => id === value)?.[1] || String(value || "").replaceAll("_", " ");
}

function Field({ label, children }) {
  return <div className="grid gap-1.5"><label className="text-xs font-medium text-muted-foreground">{label}</label>{children}</div>;
}

export default function TemplatesPage() {
  const qc = useQueryClient();
  const [templateType, setTemplateType] = useState("all");
  const [channel, setChannel] = useState("all");
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [draft, setDraft] = useState({
    name: "",
    template_type: "task",
    description: "",
    body: JSON.stringify(STARTER_BODY, null, 2),
  });
  const [selected, setSelected] = useState(null);
  const [preview, setPreview] = useState(null);

  const templates = useQuery({
    queryKey: ["templates", templateType, channel, includeArchived],
    queryFn: async () => {
      const params = {
        include_archived: includeArchived,
        template_type: templateType === "all" ? undefined : templateType,
        channel: channel === "all" ? undefined : channel,
      };
      return (await api.get("/templates", { params })).data;
    },
  });
  const onError = (err) => toast.error(extractError(err));
  const items = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = templates.data?.items || [];
    if (!q) return rows;
    return rows.filter((t) => `${t.name} ${t.description || ""} ${t.template_type}`.toLowerCase().includes(q));
  }, [templates.data, search]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["templates"] });

  const create = useMutation({
    mutationFn: async () => api.post("/templates", { ...draft, body: JSON.parse(draft.body || "{}") }),
    onSuccess: () => { setDraft((d) => ({ ...d, name: "" })); invalidate(); toast.success("Template saved"); },
    onError,
  });
  const update = useMutation({
    mutationFn: async () => api.patch(`/templates/${selected.id}`, {
      name: draft.name,
      template_type: draft.template_type,
      description: draft.description,
      body: JSON.parse(draft.body || "{}"),
    }),
    onSuccess: () => { setSelected(null); invalidate(); toast.success("Template updated"); },
    onError,
  });
  const duplicate = useMutation({
    mutationFn: async (id) => api.post(`/templates/${id}/duplicate`),
    onSuccess: () => { invalidate(); toast.success("Template duplicated"); },
    onError,
  });
  const archive = useMutation({
    mutationFn: async (id) => api.post(`/templates/${id}/archive`),
    onSuccess: () => { invalidate(); toast.success("Template archived"); },
    onError,
  });
  const restore = useMutation({
    mutationFn: async (id) => api.post(`/templates/${id}/restore`),
    onSuccess: () => { invalidate(); toast.success("Template restored"); },
    onError,
  });
  const starterPack = useMutation({
    mutationFn: async () => api.post("/templates/packs/starter/install"),
    onSuccess: () => { invalidate(); toast.success("Starter templates installed"); },
    onError,
  });
  const newerCopy = useMutation({
    mutationFn: async (id) => api.post(`/templates/${id}/install-newer-source-copy`),
    onSuccess: () => { invalidate(); toast.success("New source copy installed"); },
    onError,
  });
  const showPreview = useMutation({
    mutationFn: async (id) => (await api.post(`/templates/${id}/preview`, { context: {} })).data,
    onSuccess: (data) => setPreview(data),
    onError,
  });

  function loadForEdit(tpl) {
    setSelected(tpl);
    setPreview(null);
    setDraft({
      name: tpl.name || "",
      template_type: tpl.template_type,
      description: tpl.description || "",
      body: JSON.stringify(tpl.body || STARTER_BODY, null, 2),
    });
  }

  function changeDraftType(value) {
    setDraft((d) => ({ ...d, template_type: value, body: d.body || JSON.stringify(STARTER_BODY, null, 2) }));
  }

  const isEditingPlatform = selected?.owner_scope === "platform";

  return (
    <div className="space-y-4" data-testid="templates-page">
      <PageHeader title="Templates" subtitle="Reusable templates for intake, Decision Rooms, productivity, communication, reminders, and support responses." />

      <div className="flex flex-wrap gap-2">
        <Button onClick={() => starterPack.mutate()} disabled={starterPack.isPending} data-testid="template-install-starter-pack">
          <PackagePlus className="size-4 mr-1" />Install starter pack
        </Button>
        <Badge variant="secondary">SMS content is stored only</Badge>
        <Badge variant="outline">No pricing or storefront</Badge>
      </div>

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader><CardTitle className="text-base">{selected ? "Edit template" : "Create tenant template"}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {isEditingPlatform && <div className="rounded bg-amber-50 p-2 text-xs text-amber-800">Platform master templates are read-only for tenants. Install or duplicate before editing.</div>}
            <Field label="Type">
              <Select value={draft.template_type} onValueChange={changeDraftType} disabled={isEditingPlatform}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{TYPES.filter(([id]) => id !== "all").map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
            <Field label="Name"><Input value={draft.name} onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))} disabled={isEditingPlatform} /></Field>
            <Field label="Description"><Input value={draft.description} onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))} disabled={isEditingPlatform} /></Field>
            <Field label="Body JSON"><Textarea className="font-mono text-xs" rows={10} value={draft.body} onChange={(e) => setDraft((d) => ({ ...d, body: e.target.value }))} disabled={isEditingPlatform} /></Field>
            <div className="flex justify-between gap-2">
              <Button variant="outline" onClick={() => { setSelected(null); setPreview(null); setDraft({ name: "", template_type: "task", description: "", body: JSON.stringify(STARTER_BODY, null, 2) }); }}>Clear</Button>
              {selected ? (
                <Button onClick={() => update.mutate()} disabled={update.isPending || isEditingPlatform}><Save className="size-4 mr-1" />Update</Button>
              ) : (
                <Button onClick={() => create.mutate()} disabled={!draft.name.trim() || create.isPending}><Plus className="size-4 mr-1" />Save</Button>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-3">
          <div className="grid gap-2 rounded border bg-card p-3 md:grid-cols-[180px_180px_1fr_auto]">
            <Select value={templateType} onValueChange={setTemplateType}>
              <SelectTrigger data-testid="template-type-select"><SelectValue /></SelectTrigger>
              <SelectContent>{TYPES.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
            </Select>
            <Select value={channel} onValueChange={setChannel}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{CHANNELS.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
            </Select>
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search templates" />
            <Button variant={includeArchived ? "default" : "outline"} onClick={() => setIncludeArchived((v) => !v)}>
              {includeArchived ? "Showing archived" : "Active only"}
            </Button>
          </div>

          {templates.isLoading ? <TableSkeleton /> : items.length === 0 ? (
            <EmptyState icon={FileText} title="No templates" description="Create a tenant template or install the starter pack." />
          ) : (
            <div className="grid gap-3">
              {items.map((tpl) => (
                <Card key={tpl.id} data-testid={`template-row-${tpl.id}`}>
                  <CardContent className="p-3">
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <button className="text-left font-medium hover:underline" onClick={() => loadForEdit(tpl)}>{tpl.name}</button>
                        <div className="mt-1 flex flex-wrap gap-1 text-xs text-muted-foreground">
                          <Badge variant="outline">{typeLabel(tpl.template_type)}</Badge>
                          <Badge variant={tpl.owner_scope === "platform" ? "default" : "secondary"}>{tpl.owner_scope === "platform" ? "Starter" : "Custom"}</Badge>
                          {tpl.premium_reserved && <Badge variant="outline">Reserved</Badge>}
                          {tpl.source_update_available && <Badge variant="destructive">Update available</Badge>}
                          {!tpl.active && <Badge variant="secondary">Archived</Badge>}
                          <span>v{tpl.version}</span>
                          {tpl.source_template_version && <span>source v{tpl.source_template_version}</span>}
                        </div>
                        {tpl.description && <p className="mt-2 text-sm text-muted-foreground">{tpl.description}</p>}
                        {(tpl.channels || []).length > 0 && <p className="mt-2 text-xs text-muted-foreground">Channels: {tpl.channels.join(", ")}</p>}
                      </div>
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button size="sm" variant="outline" onClick={() => showPreview.mutate(tpl.id)}><Eye className="size-4 mr-1" />Preview</Button>
                        <Button size="sm" variant="outline" onClick={() => duplicate.mutate(tpl.id)}><Copy className="size-4 mr-1" />Duplicate</Button>
                        {tpl.source_update_available && <Button size="sm" variant="outline" onClick={() => newerCopy.mutate(tpl.id)}>Install update</Button>}
                        {tpl.owner_scope !== "platform" && (tpl.active ? (
                          <Button size="sm" variant="outline" onClick={() => archive.mutate(tpl.id)}><Archive className="size-4 mr-1" />Archive</Button>
                        ) : (
                          <Button size="sm" variant="outline" onClick={() => restore.mutate(tpl.id)}><RotateCcw className="size-4 mr-1" />Restore</Button>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>

      {preview && (
        <Card data-testid="template-preview">
          <CardHeader><CardTitle className="text-base">Preview</CardTitle></CardHeader>
          <CardContent>
            <pre className="max-h-80 overflow-auto rounded bg-slate-950 p-3 text-xs text-white">{JSON.stringify(preview.rendered, null, 2)}</pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
