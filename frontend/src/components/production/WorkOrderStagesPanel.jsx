import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock3, Play, RotateCcw, UserPlus, Wrench } from "lucide-react";
import api, { extractError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

const STATUS_TONE = {
  not_started: "secondary",
  in_progress: "default",
  waiting: "outline",
  blocked: "destructive",
  completed: "secondary",
  skipped: "outline",
};

function stageNamesToPayload(names, workflow) {
  const base = workflow?.stages || [];
  return names.split(",").map((raw, index) => {
    const stage = base[index] || {};
    const display = raw.trim();
    if (!display) return null;
    return {
      ...stage,
      stage_key: stage.stage_key || display.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, ""),
      display_name: display,
      sequence: index + 1,
      active: true,
    };
  }).filter(Boolean);
}

function useStageAction(workOrderId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ stageId, action, payload }) => {
      const method = action === "due-date" ? "patch" : "post";
      return (await api[method](`/production-stages/${stageId}/${action}`, payload || {})).data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["work-order-stages", workOrderId] });
      qc.invalidateQueries({ queryKey: ["production-timeline"] });
    },
    onError: (e) => toast.error(extractError(e)),
  });
}

function StageRow({ stage, employees, canWrite, canManage, action }) {
  const [employeeId, setEmployeeId] = useState(stage.assigned_employee_id || "");
  const [dueAt, setDueAt] = useState(stage.due_at || "");
  const [note, setNote] = useState("");

  function reason(label) {
    return window.prompt(label) || "";
  }

  return (
    <div className="rounded-md border p-3" data-testid={`production-stage-${stage.id}`}>
      <div className="grid gap-3 lg:grid-cols-[40px_1fr_160px_180px] lg:items-start">
        <div className="text-xs tabular-nums text-muted-foreground">#{stage.sequence}</div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="font-medium text-sm">{stage.stage_name}</div>
            <Badge variant={STATUS_TONE[stage.status] || "secondary"}>{stage.status.replace("_", " ")}</Badge>
            {stage.required && <Badge variant="outline">required</Badge>}
            {stage.proof_gate_type && <Badge variant="outline">proof gate</Badge>}
          </div>
          {stage.description && <div className="mt-1 text-xs text-muted-foreground">{stage.description}</div>}
          {stage.blocker_reason && <div className="mt-1 text-xs text-rose-700">Blocked: {stage.blocker_reason}</div>}
          {stage.production_notes?.length > 0 && (
            <div className="mt-2 text-xs text-muted-foreground">
              Latest note: {stage.production_notes[stage.production_notes.length - 1]?.note}
            </div>
          )}
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Assignee</Label>
          <Select value={employeeId || "none"} disabled={!canManage} onValueChange={(v) => setEmployeeId(v === "none" ? "" : v)}>
            <SelectTrigger className="h-8" data-testid={`stage-assignee-${stage.id}`}><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Unassigned</SelectItem>
              {(employees || []).map((e) => (
                <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {canManage && (
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="outline"
                disabled={!employeeId || action.isPending}
                onClick={() => action.mutate({ stageId: stage.id, action: "assign", payload: { employee_id: employeeId } })}
              >
                <UserPlus className="size-3 mr-1" />Assign
              </Button>
              <Button size="sm" variant="outline" disabled={action.isPending} onClick={() => action.mutate({ stageId: stage.id, action: "unassign" })}>Clear</Button>
            </div>
          )}
        </div>
        <div className="grid gap-1.5">
          <Label className="text-xs">Due</Label>
          <Input className="h-8" type="date" value={(dueAt || "").slice(0, 10)} disabled={!canManage} onChange={(e) => setDueAt(e.target.value)} />
          {canManage && <Button size="sm" variant="outline" onClick={() => action.mutate({ stageId: stage.id, action: "due-date", payload: { due_at: dueAt || null } })}>Save due</Button>}
        </div>
      </div>

      {canWrite && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={action.isPending || stage.status !== "not_started"} onClick={() => action.mutate({ stageId: stage.id, action: "start" })}>
            <Play className="size-3 mr-1" />Start
          </Button>
          <Button size="sm" variant="outline" disabled={action.isPending || stage.status !== "in_progress"} onClick={() => action.mutate({ stageId: stage.id, action: "wait" })}>
            <Clock3 className="size-3 mr-1" />Wait
          </Button>
          <Button size="sm" variant="outline" disabled={action.isPending || stage.status !== "in_progress"} onClick={() => action.mutate({ stageId: stage.id, action: "block", payload: { reason: reason("Block reason") } })}>
            <AlertTriangle className="size-3 mr-1" />Block
          </Button>
          <Button size="sm" variant="outline" disabled={action.isPending || !["waiting", "blocked"].includes(stage.status)} onClick={() => action.mutate({ stageId: stage.id, action: "resume" })}>
            Resume
          </Button>
          <Button size="sm" variant="outline" disabled={action.isPending || stage.status !== "in_progress"} onClick={() => action.mutate({ stageId: stage.id, action: "complete" })}>
            <CheckCircle2 className="size-3 mr-1" />Complete
          </Button>
          {canManage && (
            <>
              <Button size="sm" variant="outline" disabled={action.isPending || !["not_started", "in_progress"].includes(stage.status)} onClick={() => action.mutate({ stageId: stage.id, action: "skip", payload: { reason: stage.requires_reason_to_skip ? reason("Skip reason") : "" } })}>
                Skip
              </Button>
              <Button size="sm" variant="outline" disabled={action.isPending || !["completed", "skipped"].includes(stage.status)} onClick={() => action.mutate({ stageId: stage.id, action: "reopen", payload: { reason: reason("Reopen reason") } })}>
                <RotateCcw className="size-3 mr-1" />Reopen
              </Button>
            </>
          )}
        </div>
      )}

      {canWrite && (
        <div className="mt-3 grid gap-2 md:grid-cols-[1fr_auto]">
          <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Production note" data-testid={`stage-note-${stage.id}`} />
          <Button
            variant="outline"
            disabled={!note.trim() || action.isPending}
            onClick={() => {
              action.mutate({ stageId: stage.id, action: "notes", payload: { note } });
              setNote("");
            }}
          >
            Add note
          </Button>
        </div>
      )}
    </div>
  );
}

export default function WorkOrderStagesPanel({ workOrderId }) {
  const qc = useQueryClient();
  const { hasPerm, user } = useAuth();
  const canWrite = hasPerm("work_order:write");
  const canManage = canWrite && ["owner", "admin", "production_manager"].includes(user?.role);
  const [selectedWorkflowByItem, setSelectedWorkflowByItem] = useState({});
  const [customStagesByItem, setCustomStagesByItem] = useState({});

  const stagesQuery = useQuery({
    queryKey: ["work-order-stages", workOrderId],
    queryFn: async () => (await api.get(`/work-orders/${workOrderId}/stages`)).data,
    enabled: !!workOrderId,
  });
  const previewQuery = useQuery({
    queryKey: ["work-order-stage-preview", workOrderId],
    queryFn: async () => (await api.get(`/work-orders/${workOrderId}/stage-preview`)).data,
    enabled: !!workOrderId,
  });
  const workflowsQuery = useQuery({
    queryKey: ["production-workflows", false],
    queryFn: async () => (await api.get("/production-workflows")).data,
    enabled: canWrite,
  });
  const employeesQuery = useQuery({
    queryKey: ["employees", "active"],
    queryFn: async () => (await api.get("/employees", { params: { status: "active" } })).data,
    enabled: canWrite,
  });
  const action = useStageAction(workOrderId);

  const generate = useMutation({
    mutationFn: async () => (await api.post(`/work-orders/${workOrderId}/stages/generate`)).data,
    onSuccess: () => {
      toast.success("Production stages generated");
      qc.invalidateQueries({ queryKey: ["work-order-stages", workOrderId] });
      qc.invalidateQueries({ queryKey: ["work-order-stage-preview", workOrderId] });
      qc.invalidateQueries({ queryKey: ["production-timeline"] });
    },
    onError: (e) => toast.error(extractError(e)),
  });
  const saveOverride = useMutation({
    mutationFn: async ({ orderId, itemId, workflowId, stages }) => (
      await api.post(`/orders/${orderId}/items/${itemId}/production-workflow-override`, { workflow_id: workflowId, stages })
    ).data,
    onSuccess: () => {
      toast.success("Item workflow override saved");
      qc.invalidateQueries({ queryKey: ["work-order-stage-preview", workOrderId] });
      qc.invalidateQueries({ queryKey: ["production-timeline"] });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const stages = stagesQuery.data?.stages || [];
  const instances = stagesQuery.data?.workflow_instances || [];
  const previewItems = previewQuery.data?.items || [];
  const workflows = useMemo(() => workflowsQuery.data?.items || [], [workflowsQuery.data]);
  const workflowById = useMemo(() => {
    const map = {};
    workflows.forEach((w) => { map[w.id] = w; });
    return map;
  }, [workflows]);

  return (
    <Card data-testid="work-order-stages-panel">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base"><Wrench className="inline size-4 mr-1" />Production stages</CardTitle>
        {canWrite && stages.length > 0 && (
          <Button size="sm" variant="outline" onClick={() => generate.mutate()} disabled={generate.isPending}>
            Regenerate check
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {stagesQuery.isLoading ? (
          <div className="text-sm text-muted-foreground">Loading stages...</div>
        ) : stages.length === 0 ? (
          <div className="space-y-3">
            <div className="text-sm text-muted-foreground">No live production stages have been generated for this work order.</div>
            {previewItems.map((item) => {
              const selectedWorkflowId = selectedWorkflowByItem[item.order_item_id] || item.workflow?.id || "";
              const selectedWorkflow = workflowById[selectedWorkflowId] || item.workflow;
              const custom = customStagesByItem[item.order_item_id] || "";
              const customStages = custom ? stageNamesToPayload(custom, selectedWorkflow) : null;
              return (
                <div key={item.order_item_id} className="rounded-md border p-3 text-sm" data-testid={`stage-preview-item-${item.order_item_id}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="font-medium">Item {item.order_item_id}</div>
                      <div className="text-xs text-muted-foreground">
                        {item.workflow ? `${item.workflow.name} (${item.source})` : `No workflow: ${item.reason}`}
                      </div>
                    </div>
                    {canWrite && (
                      <div className="flex flex-wrap gap-2">
                        <Select value={selectedWorkflowId || "none"} onValueChange={(v) => setSelectedWorkflowByItem((m) => ({ ...m, [item.order_item_id]: v === "none" ? "" : v }))}>
                          <SelectTrigger className="h-8 w-[220px]"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">Use resolved workflow</SelectItem>
                            {workflows.map((w) => <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>)}
                          </SelectContent>
                        </Select>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={!selectedWorkflowId || saveOverride.isPending}
                          onClick={() => saveOverride.mutate({
                            orderId: stagesQuery.data?.order_id || previewQuery.data?.order_id,
                            itemId: item.order_item_id,
                            workflowId: selectedWorkflowId,
                            stages: customStages,
                          })}
                        >
                          Save override
                        </Button>
                      </div>
                    )}
                  </div>
                  {canWrite && selectedWorkflow && (
                    <div className="mt-2 grid gap-1.5">
                      <Label className="text-xs">Override stage names/order before generation</Label>
                      <Input
                        value={custom}
                        onChange={(e) => setCustomStagesByItem((m) => ({ ...m, [item.order_item_id]: e.target.value }))}
                        placeholder={(selectedWorkflow.stages || []).map((s) => s.display_name).join(", ")}
                      />
                    </div>
                  )}
                </div>
              );
            })}
            {canWrite && (
              <Button onClick={() => generate.mutate()} disabled={generate.isPending} data-testid="generate-production-stages-button">
                Generate stages
              </Button>
            )}
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {instances.map((instance) => (
                <Badge key={instance.id} variant="outline">
                  {instance.source_name || "Manual"} / {instance.resolution_source}
                </Badge>
              ))}
            </div>
            <div className="space-y-3">
              {stages.map((stage) => (
                <StageRow
                  key={stage.id}
                  stage={stage}
                  employees={employeesQuery.data?.items || []}
                  canWrite={canWrite}
                  canManage={canManage}
                  action={action}
                />
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
