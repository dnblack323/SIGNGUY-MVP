import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import StatusPill from "@/components/common/StatusPill";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { centsToDollarsString } from "@/lib/format";
import { ArrowLeft, Save, RefreshCw, Users as UsersIcon, Printer, AlertTriangle, ShieldCheck } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { RegenerateDialog, TransitionReasonDialog, AssignDialog } from "@/components/work-orders/GenerateWorkOrderDialog";
import RequirementsDialog from "@/components/work-orders/RequirementsDialog";
import PrintSummaryDialog from "@/components/work-orders/PrintSummaryDialog";

const ALLOWED = {
  draft: ["released", "cancelled"],
  released: ["queued", "in_progress", "blocked", "cancelled"],
  queued: ["in_progress", "blocked", "cancelled"],
  in_progress: ["blocked", "ready", "cancelled"],
  blocked: ["released", "queued", "in_progress", "cancelled"],
  ready: ["completed", "cancelled"],
  completed: [],
  cancelled: [],
  superseded: [],
  not_started: ["released", "cancelled"],
  on_hold: ["released", "queued", "in_progress", "cancelled"],
};
const REASON_REQUIRED = new Set(["blocked", "cancelled"]);

export default function WorkOrderDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("work_order:write");

  const { data: w } = useQuery({ queryKey: ["work-order", id], queryFn: async () => (await api.get(`/work-orders/${id}`)).data });
  const { data: audit } = useQuery({ queryKey: ["audit-wo", id], queryFn: async () => (await api.get(`/audit`, { params: { entity_type: "work_order", entity_id: id } })).data, enabled: !!id });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: async () => (await api.get(`/users`)).data });
  const { data: equipment } = useQuery({ queryKey: ["equipment-for-wo"], queryFn: async () => (await api.get("/equipment")).data.items, retry: false });

  const [form, setForm] = useState({});
  const [pending, setPending] = useState(null); // {target}
  const [regenOpen, setRegenOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [printOpen, setPrintOpen] = useState(false);
  const [reqOpen, setReqOpen] = useState(false);

  const usersById = useMemo(() => {
    const m = {};
    (users || []).forEach((u) => { m[u.id] = u; });
    return m;
  }, [users]);
  const equipmentById = useMemo(() => {
    const m = {};
    (equipment || []).forEach((eq) => { m[eq.id] = eq; });
    return m;
  }, [equipment]);

  const save = useMutation({
    mutationFn: async (payload) => (await api.patch(`/work-orders/${id}`, payload)).data,
    onSuccess: () => { toast.success("Saved"); qc.invalidateQueries({ queryKey: ["work-order", id] }); qc.invalidateQueries({ queryKey: ["audit-wo", id] }); setForm({}); },
    onError: (e) => toast.error(extractError(e)),
  });

  const doTransition = useMutation({
    mutationFn: async ({ target, reason }) => (await api.post(`/work-orders/${id}/transition`, { target, reason })).data,
    onSuccess: (res) => {
      toast.success(`Moved to ${res.production_status}`);
      qc.invalidateQueries({ queryKey: ["work-order", id] });
      qc.invalidateQueries({ queryKey: ["audit-wo", id] });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  function handleTransition(target) {
    if (REASON_REQUIRED.has(target)) { setPending({ target }); return; }
    doTransition.mutate({ target });
  }

  if (!w) return <div className="text-sm text-muted-foreground">Loading…</div>;

  const currentStatus = w.production_status;
  const nextStates = ALLOWED[currentStatus] || [];
  const edit = { ...w, ...form };

  return (
    <div className="space-y-4" data-testid="work-order-detail-page">
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="icon"><Link to="/work-orders"><ArrowLeft className="size-4" /></Link></Button>
        <PageHeader
          title={
            <span>
              <span className="mono text-muted-foreground text-lg mr-2">W-{w.number}</span>
              {w.version > 1 && <span className="text-xs mr-2 rounded bg-muted px-1.5 py-0.5" data-testid="wo-version-badge">v{w.version}</span>}
              Work Order
            </span>
          }
          subtitle={<span>Order: <Link className="link-underline" to={`/orders/${w.order_id}`}>Open order</Link></span>}
          actions={
            <div className="flex items-center gap-2 flex-wrap">
              <Button variant="outline" size="sm" onClick={() => setPrintOpen(true)} data-testid="wo-print-summary-button">
                <Printer className="size-4 mr-1" />Print summary
              </Button>
              {canWrite && w.current_version !== false && !["completed", "cancelled", "superseded"].includes(currentStatus) && (
                <Button variant="outline" size="sm" onClick={() => setRegenOpen(true)} data-testid="wo-regenerate-button">
                  <RefreshCw className="size-4 mr-1" />Regenerate
                </Button>
              )}
            </div>
          }
        />
      </div>

      {w.current_version === false && (
        <div className="rounded-md border border-amber-300 bg-amber-50 text-amber-900 px-3 py-2 text-sm flex items-center gap-2" data-testid="wo-superseded-banner">
          <AlertTriangle className="size-4" />
          This work order was superseded.
          {w.superseded_by && (
            <> Current version: <Link className="link-underline ml-1" to={`/work-orders/${w.superseded_by}`} data-testid="wo-current-version-link">open</Link></>
          )}
        </div>
      )}
      {w.superseded_from && (
        <div className="rounded-md border border-slate-300 bg-slate-50 text-slate-800 px-3 py-2 text-sm" data-testid="wo-superseded-from-banner">
          Regenerated from earlier version:{" "}
          <Link className="link-underline" to={`/work-orders/${w.superseded_from}`} data-testid="wo-previous-version-link">open previous</Link>.
          {w.supersede_reason && <span className="ml-2 text-muted-foreground">Reason: {w.supersede_reason}</span>}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        <Tabs defaultValue="items" data-testid="detail-tabs">
          <TabsList>
            <TabsTrigger value="items" data-testid="detail-tab-items">Items</TabsTrigger>
            <TabsTrigger value="details" data-testid="detail-tab-details">Details</TabsTrigger>
            <TabsTrigger value="activity" data-testid="detail-tab-activity">Activity</TabsTrigger>
          </TabsList>
          <TabsContent value="items">
            <Card>
              <CardHeader><CardTitle>Items snapshot (immutable at generation)</CardTitle></CardHeader>
              <CardContent>
                {(!w.items_snapshot || w.items_snapshot.length === 0) ? (
                  <div className="text-sm text-muted-foreground">No production-required items were on the order at generation.</div>
                ) : (
                  <div className="rounded-lg border">
                    <div className="grid grid-cols-[1fr_80px_140px_140px] gap-2 px-3 py-2 border-b text-xs font-medium text-muted-foreground">
                      <div>Description</div><div className="text-right">Qty</div><div className="text-right">Unit</div><div className="text-right">Line total</div>
                    </div>
                    <div className="divide-y">
                      {w.items_snapshot.map((it, i) => (
                        <div key={i} className="grid grid-cols-[1fr_80px_140px_140px] gap-2 px-3 py-2 items-center text-sm" data-testid={`wo-item-row-${i}`}>
                          <div>
                            <div>{it.description}</div>
                            {(it.width_inches || it.height_inches) && (
                              <div className="text-xs text-muted-foreground">{it.width_inches ?? "?"} × {it.height_inches ?? "?"} {it.unit_of_measure || "in"}</div>
                            )}
                          </div>
                          <div className="text-right tabular-nums">{it.quantity}</div>
                          <div className="text-right tabular-nums">{centsToDollarsString(it.unit_price_cents)}</div>
                          <div className="text-right tabular-nums">{centsToDollarsString((it.quantity || 1) * (it.unit_price_cents || 0))}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="details" className="space-y-4">
            <Card>
              <CardHeader><CardTitle>Production details</CardTitle></CardHeader>
              <CardContent className="grid gap-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5">
                    <Label>Priority</Label>
                    <Select value={edit.priority || "normal"} disabled={!canWrite} onValueChange={(v) => setForm((f) => ({ ...f, priority: v }))}>
                      <SelectTrigger data-testid="wo-priority-select"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="low">Low</SelectItem>
                        <SelectItem value="normal">Normal</SelectItem>
                        <SelectItem value="high">High</SelectItem>
                        <SelectItem value="rush">Rush</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-1.5">
                    <Label>Due date</Label>
                    <Input type="date" value={(edit.due_date || "").slice(0, 10)} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value || null }))} data-testid="wo-due-date" />
                  </div>
                </div>
                <div className="grid gap-1.5">
                  <Label>Production instructions</Label>
                  <Textarea rows={4} value={edit.production_instructions || ""} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, production_instructions: e.target.value }))} data-testid="work-order-instructions-input" />
                </div>
                <div className="grid gap-1.5">
                  <Label>Internal notes</Label>
                  <Textarea rows={3} value={edit.internal_notes || ""} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, internal_notes: e.target.value }))} data-testid="wo-internal-notes" />
                </div>
                {canWrite && Object.keys(form).length > 0 && (
                  <Button onClick={() => save.mutate(form)} disabled={save.isPending} data-testid="wo-save-button">
                    <Save className="size-4 mr-1" />Save
                  </Button>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="activity"><AuditTimeline events={audit?.items || []} /></TabsContent>
        </Tabs>

        <aside className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Production status</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <StatusPill kind="production" value={currentStatus} />
                <StatusPill kind="priority" value={w.priority || "normal"} />
              </div>
              {w.due_date && <div className="text-xs text-muted-foreground">Due: <span className="font-medium">{w.due_date}</span></div>}
              {canWrite && nextStates.length === 0 && (
                <div className="text-xs text-muted-foreground italic">Terminal status — no further transitions.</div>
              )}
              {canWrite && nextStates.length > 0 && (
                <div className="grid grid-cols-2 gap-2">
                  {nextStates.map((s) => (
                    <Button key={s} size="sm" variant="outline" onClick={() => handleTransition(s)} data-testid={`wo-transition-${s}`}>
                      <span className="capitalize">{s.replace("_", " ")}</span>
                    </Button>
                  ))}
                </div>
              )}
              {(w.cancel_reason || w.block_reason) && (
                <div className="text-xs text-muted-foreground border-t pt-2">
                  {w.block_reason && <div><span className="font-medium">Block reason:</span> {w.block_reason}</div>}
                  {w.cancel_reason && <div><span className="font-medium">Cancel reason:</span> {w.cancel_reason}</div>}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Assignees</CardTitle>
              {canWrite && (
                <Button variant="ghost" size="sm" onClick={() => setAssignOpen(true)} data-testid="wo-open-assign-button">
                  <UsersIcon className="size-4 mr-1" />Manage
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {((w.assigned_user_ids || []).length === 0) ? (
                <div className="text-sm text-muted-foreground">No assignees.</div>
              ) : (
                <ul className="space-y-1" data-testid="wo-assignee-list">
                  {(w.assigned_user_ids || []).map((uid) => (
                    <li key={uid} className="text-sm" data-testid={`wo-assignee-${uid}`}>
                      {usersById[uid]?.full_name || usersById[uid]?.email || uid}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Assignment requirements</CardTitle>
              {canWrite && (
                <Button variant="ghost" size="sm" onClick={() => setReqOpen(true)} data-testid="wo-open-requirements-button">
                  <ShieldCheck className="size-4 mr-1" />Edit
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {((w.required_equipment_ids || []).length === 0 && !w.required_role) ? (
                <div className="text-muted-foreground" data-testid="wo-requirements-empty">No Equipment or role requirements set.</div>
              ) : (
                <>
                  {(w.required_equipment_ids || []).length > 0 && (
                    <div className="flex flex-wrap gap-1" data-testid="wo-required-equipment-list">
                      {w.required_equipment_ids.map((eid) => (
                        <span key={eid} className="rounded-full bg-muted px-2 py-0.5 text-xs" data-testid={`wo-required-equipment-${eid}`}>{equipmentById[eid]?.name || eid}</span>
                      ))}
                    </div>
                  )}
                  {w.required_role && <div>Required role: <span className="font-medium">{w.required_role}</span></div>}
                </>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>

      <TransitionReasonDialog
        open={!!pending}
        target={pending?.target}
        pending={doTransition.isPending}
        onCancel={() => setPending(null)}
        onConfirm={(reason) => {
          if (!reason) { toast.error("Reason is required"); return; }
          doTransition.mutate({ target: pending.target, reason });
          setPending(null);
        }}
      />
      <RegenerateDialog
        workOrderId={id}
        open={regenOpen}
        onOpenChange={setRegenOpen}
        onDone={(wo) => navigate(`/work-orders/${wo.id}`)}
      />
      <AssignDialog workOrderId={id} currentUserIds={w.assigned_user_ids || []} open={assignOpen} onOpenChange={setAssignOpen} />
      <RequirementsDialog workOrderId={id} currentEquipmentIds={w.required_equipment_ids || []} currentRole={w.required_role} open={reqOpen} onOpenChange={setReqOpen} />
      <PrintSummaryDialog workOrderId={id} open={printOpen} onOpenChange={setPrintOpen} />
    </div>
  );
}
