import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Copy, Layers3, Plus, RotateCcw, Save } from "lucide-react";
import api, { extractError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import PageHeader from "@/components/layout/PageHeader";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

const CATEGORY_HINTS = [
  "banners",
  "rigid_signs",
  "cut_vinyl",
  "digital_print",
  "apparel",
  "vehicle_graphics",
  "installation",
];

function splitCategories(value) {
  return value.split(",").map((v) => v.trim()).filter(Boolean);
}

export default function ProductionWorkflowsPage() {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canManage = hasPerm("production_workflow:manage");
  const [selectedId, setSelectedId] = useState(null);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [newName, setNewName] = useState("");
  const [newStage, setNewStage] = useState("");
  const [categories, setCategories] = useState("");
  const [previewCategory, setPreviewCategory] = useState("banners");

  const workflows = useQuery({
    queryKey: ["production-workflows", includeArchived],
    queryFn: async () => (await api.get("/production-workflows", { params: { include_archived: includeArchived } })).data,
  });
  const items = useMemo(() => workflows.data?.items || [], [workflows.data]);
  const selected = useMemo(() => items.find((w) => w.id === selectedId) || items[0], [items, selectedId]);
  const selectedStages = useMemo(() => [...(selected?.stages || [])].sort((a, b) => a.sequence - b.sequence), [selected]);
  const activeStageKeys = selectedStages.filter((s) => s.active !== false).map((s) => s.stage_key);
  const starterLocked = selected?.scope_type === "system_starter";

  const preview = useQuery({
    queryKey: ["production-workflow-resolution", previewCategory],
    queryFn: async () => (await api.get("/production-workflows/resolve", { params: { category_id: previewCategory } })).data,
    enabled: !!previewCategory,
  });

  const onError = (e) => toast.error(extractError(e));
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["production-workflows"] });
    qc.invalidateQueries({ queryKey: ["production-workflow-resolution"] });
  };

  const createWorkflow = useMutation({
    mutationFn: async () => (await api.post("/production-workflows", {
      name: newName,
      stages: [
        { stage_key: "design", display_name: "Design", sequence: 1 },
        { stage_key: "production", display_name: "Production", sequence: 2, may_skip: false },
        { stage_key: "quality_check", display_name: "Quality Check", sequence: 3 },
      ],
    })).data,
    onSuccess: (w) => { setNewName(""); setSelectedId(w.id); invalidate(); toast.success("Workflow created"); },
    onError,
  });
  const duplicateWorkflow = useMutation({
    mutationFn: async (id) => (await api.post(`/production-workflows/${id}/duplicate`, {})).data,
    onSuccess: (w) => { setSelectedId(w.id); invalidate(); toast.success("Workflow duplicated"); },
    onError,
  });
  const updateWorkflow = useMutation({
    mutationFn: async ({ id, payload }) => (await api.patch(`/production-workflows/${id}`, payload)).data,
    onSuccess: invalidate,
    onError,
  });
  const archiveWorkflow = useMutation({
    mutationFn: async (id) => (await api.post(`/production-workflows/${id}/archive`)).data,
    onSuccess: invalidate,
    onError,
  });
  const restoreWorkflow = useMutation({
    mutationFn: async (id) => (await api.post(`/production-workflows/${id}/restore`)).data,
    onSuccess: invalidate,
    onError,
  });
  const setDefault = useMutation({
    mutationFn: async (id) => (await api.post(`/production-workflows/${id}/set-default`)).data,
    onSuccess: () => { invalidate(); toast.success("Tenant default updated"); },
    onError,
  });
  const assignCategory = useMutation({
    mutationFn: async ({ id, category_ids }) => (await api.post(`/production-workflows/${id}/assign-category`, { category_ids })).data,
    onSuccess: () => { invalidate(); toast.success("Category assignment updated"); },
    onError,
  });
  const addStage = useMutation({
    mutationFn: async ({ id, display_name }) => (await api.post(`/production-workflows/${id}/stages`, { display_name })).data,
    onSuccess: () => { setNewStage(""); invalidate(); toast.success("Stage added"); },
    onError,
  });
  const updateStage = useMutation({
    mutationFn: async ({ id, stage_key, payload }) => (await api.patch(`/production-workflows/${id}/stages/${stage_key}`, payload)).data,
    onSuccess: invalidate,
    onError,
  });
  const reorderStages = useMutation({
    mutationFn: async ({ id, stage_keys }) => (await api.post(`/production-workflows/${id}/stages/reorder`, { stage_keys })).data,
    onSuccess: invalidate,
    onError,
  });
  const archiveStage = useMutation({
    mutationFn: async ({ id, stage_key }) => (await api.post(`/production-workflows/${id}/stages/${stage_key}/archive`)).data,
    onSuccess: invalidate,
    onError,
  });

  function moveStage(stageKey, dir) {
    const idx = activeStageKeys.indexOf(stageKey);
    const next = [...activeStageKeys];
    const target = idx + dir;
    if (idx < 0 || target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    reorderStages.mutate({ id: selected.id, stage_keys: next });
  }

  return (
    <div className="space-y-4" data-testid="production-workflows-page">
      <PageHeader title="Production Workflows" subtitle="Configure reusable production stage definitions for EC11 core production." />

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card>
          <CardHeader className="space-y-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Workflows</CardTitle>
              <label className="text-xs text-muted-foreground inline-flex items-center gap-2">
                <input type="checkbox" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} data-testid="workflow-include-archived" />
                archived
              </label>
            </div>
            {canManage && (
              <div className="flex gap-2">
                <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="New workflow" data-testid="workflow-new-name" />
                <Button size="icon" disabled={!newName.trim() || createWorkflow.isPending} onClick={() => createWorkflow.mutate()} data-testid="workflow-create-button">
                  <Plus className="size-4" />
                </Button>
              </div>
            )}
          </CardHeader>
          <CardContent className="space-y-2">
            {workflows.isLoading ? <TableSkeleton /> : items.length === 0 ? (
              <EmptyState icon={Layers3} title="No workflows" description="Starter workflows seed automatically for each tenant." />
            ) : items.map((w) => (
              <button
                key={w.id}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm ${selected?.id === w.id ? "bg-muted" : "bg-background"}`}
                onClick={() => { setSelectedId(w.id); setCategories((w.category_ids || []).join(", ")); }}
                data-testid={`workflow-row-${w.id}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium truncate">{w.name}</span>
                  {w.is_tenant_default && <Badge>Default</Badge>}
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  <Badge variant="secondary">{w.scope_type?.replace("_", " ")}</Badge>
                  {w.archived_at && <Badge variant="outline">Archived</Badge>}
                  {(w.category_ids || []).slice(0, 2).map((c) => <Badge key={c} variant="outline">{c}</Badge>)}
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        {!selected ? (
          <Card><CardContent className="pt-6 text-sm text-muted-foreground">Select or create a workflow.</CardContent></Card>
        ) : (
          <div className="space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base">{selected.name}</CardTitle>
                  <div className="mt-1 flex gap-1 flex-wrap">
                    {selected.is_tenant_default && <Badge>Tenant default</Badge>}
                    <Badge variant="secondary">v{selected.version}</Badge>
                    {starterLocked && <Badge variant="outline">starter locked</Badge>}
                  </div>
                </div>
                {canManage && (
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => duplicateWorkflow.mutate(selected.id)} data-testid="workflow-duplicate-button">
                      <Copy className="size-4 mr-1" />Duplicate
                    </Button>
                    {selected.archived_at ? (
                      <Button size="sm" variant="outline" onClick={() => restoreWorkflow.mutate(selected.id)} data-testid="workflow-restore-button">
                        <RotateCcw className="size-4 mr-1" />Restore
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" onClick={() => archiveWorkflow.mutate(selected.id)} data-testid="workflow-archive-button">
                        <Archive className="size-4 mr-1" />Archive
                      </Button>
                    )}
                  </div>
                )}
              </CardHeader>
              <CardContent className="grid gap-3">
                <div className="grid gap-2 md:grid-cols-2">
                  <div className="grid gap-1.5">
                    <Label>Name</Label>
                    <Input
                      defaultValue={selected.name}
                      disabled={!canManage || starterLocked}
                      onBlur={(e) => e.target.value !== selected.name && updateWorkflow.mutate({ id: selected.id, payload: { name: e.target.value } })}
                      data-testid="workflow-name-input"
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label>Workflow key</Label>
                    <Input
                      defaultValue={selected.workflow_key}
                      disabled={!canManage || starterLocked}
                      onBlur={(e) => e.target.value !== selected.workflow_key && updateWorkflow.mutate({ id: selected.id, payload: { workflow_key: e.target.value } })}
                      data-testid="workflow-key-input"
                    />
                  </div>
                </div>
                <div className="grid gap-1.5">
                  <Label>Description</Label>
                  <Textarea
                    defaultValue={selected.description || ""}
                    rows={2}
                    disabled={!canManage || starterLocked}
                    onBlur={(e) => e.target.value !== (selected.description || "") && updateWorkflow.mutate({ id: selected.id, payload: { description: e.target.value } })}
                    data-testid="workflow-description-input"
                  />
                </div>
                <div className="grid gap-2 md:grid-cols-[1fr_auto_auto] items-end">
                  <div className="grid gap-1.5">
                    <Label>Category assignment</Label>
                    <Input
                      value={categories || (selected.category_ids || []).join(", ")}
                      onChange={(e) => setCategories(e.target.value)}
                      disabled={!canManage || !!selected.archived_at}
                      placeholder={CATEGORY_HINTS.join(", ")}
                      data-testid="workflow-categories-input"
                    />
                  </div>
                  <Button
                    variant="outline"
                    disabled={!canManage || !!selected.archived_at}
                    onClick={() => assignCategory.mutate({ id: selected.id, category_ids: splitCategories(categories || (selected.category_ids || []).join(",")) })}
                    data-testid="workflow-save-categories-button"
                  >
                    <Save className="size-4 mr-1" />Categories
                  </Button>
                  <Button
                    disabled={!canManage || selected.is_tenant_default || !!selected.archived_at}
                    onClick={() => setDefault.mutate(selected.id)}
                    data-testid="workflow-set-default-button"
                  >
                    Set default
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="text-base">Stages</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {selectedStages.map((stage, index) => (
                  <div key={stage.stage_key} className={`rounded-md border p-3 ${stage.active === false ? "opacity-60" : ""}`} data-testid={`workflow-stage-${stage.stage_key}`}>
                    <div className="grid gap-2 md:grid-cols-[56px_1fr_1fr_auto] items-center">
                      <div className="text-xs text-muted-foreground tabular-nums">#{stage.sequence}</div>
                      <Input
                        defaultValue={stage.display_name}
                        disabled={!canManage || starterLocked || stage.active === false}
                        onBlur={(e) => e.target.value !== stage.display_name && updateStage.mutate({ id: selected.id, stage_key: stage.stage_key, payload: { display_name: e.target.value } })}
                        data-testid={`workflow-stage-name-${stage.stage_key}`}
                      />
                      <Input
                        defaultValue={stage.default_role || ""}
                        disabled={!canManage || starterLocked || stage.active === false}
                        placeholder="Default role"
                        onBlur={(e) => e.target.value !== (stage.default_role || "") && updateStage.mutate({ id: selected.id, stage_key: stage.stage_key, payload: { default_role: e.target.value || null } })}
                        data-testid={`workflow-stage-role-${stage.stage_key}`}
                      />
                      <div className="flex gap-1 justify-end">
                        <Button size="sm" variant="outline" disabled={!canManage || starterLocked || index === 0 || stage.active === false} onClick={() => moveStage(stage.stage_key, -1)} data-testid={`workflow-stage-up-${stage.stage_key}`}>Up</Button>
                        <Button size="sm" variant="outline" disabled={!canManage || starterLocked || index === activeStageKeys.length - 1 || stage.active === false} onClick={() => moveStage(stage.stage_key, 1)} data-testid={`workflow-stage-down-${stage.stage_key}`}>Down</Button>
                        <Button size="sm" variant="outline" disabled={!canManage || starterLocked || stage.active === false} onClick={() => archiveStage.mutate({ id: selected.id, stage_key: stage.stage_key })} data-testid={`workflow-stage-archive-${stage.stage_key}`}>Archive</Button>
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      <Badge variant={stage.required ? "secondary" : "outline"}>{stage.required ? "required" : "optional"}</Badge>
                      {stage.may_skip && <Badge variant="outline">may skip</Badge>}
                      {stage.requires_reason_to_skip && <Badge variant="outline">reason to skip</Badge>}
                      {stage.employee_visible && <Badge variant="outline">employee visible</Badge>}
                      {stage.customer_visible && <Badge variant="outline">customer visible</Badge>}
                    </div>
                  </div>
                ))}
                {canManage && !starterLocked && !selected.archived_at && (
                  <div className="flex gap-2">
                    <Input value={newStage} onChange={(e) => setNewStage(e.target.value)} placeholder="Add stage" data-testid="workflow-new-stage-input" />
                    <Button disabled={!newStage.trim()} onClick={() => addStage.mutate({ id: selected.id, display_name: newStage })} data-testid="workflow-add-stage-button">
                      <Plus className="size-4 mr-1" />Add stage
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="text-base">Resolution preview</CardTitle></CardHeader>
              <CardContent className="grid gap-2 md:grid-cols-[1fr_auto] items-end">
                <div className="grid gap-1.5">
                  <Label>Category</Label>
                  <Input value={previewCategory} onChange={(e) => setPreviewCategory(e.target.value)} data-testid="workflow-preview-category-input" />
                </div>
                <div className="rounded-md border px-3 py-2 text-sm" data-testid="workflow-resolution-preview">
                  {preview.data?.workflow ? (
                    <span><Badge className="mr-2">{preview.data.source}</Badge>{preview.data.workflow.name}</span>
                  ) : (
                    <span className="text-muted-foreground">manual/no workflow</span>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
