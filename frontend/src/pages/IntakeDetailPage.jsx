import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import StatusPill from "@/components/common/StatusPill";
import FileAttachmentPicker from "@/components/intake/FileAttachmentPicker";
import IntakeItemForm from "@/components/intake/IntakeItemForm";
import { toast } from "sonner";
import { AlertTriangle, ArrowDown, ArrowUp, Copy, Plus, Trash2 } from "lucide-react";
import { relativeTime } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";
import { ALLOWED_TRANSITIONS, TRANSITION_LABELS, blankIntakeItem } from "@/lib/intake";

function ReasonDialog({ open, onOpenChange, title, onConfirm, busy }) {
  const [reason, setReason] = useState("");
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[440px]" data-testid="intake-reason-dialog">
        <DialogHeader><DialogTitle>{title}</DialogTitle><DialogDescription>A reason is required.</DialogDescription></DialogHeader>
        <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="intake-reason-textarea" />
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={!reason.trim() || busy} onClick={() => onConfirm(reason)} data-testid="intake-reason-confirm-button">Confirm</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function IntakeDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("intake:write");
  const [editingDetails, setEditingDetails] = useState(false);
  const [reasonTarget, setReasonTarget] = useState(null);
  const [newItem, setNewItem] = useState(null);

  const { data: intake, isLoading } = useQuery({
    queryKey: ["intake", id],
    queryFn: async () => (await api.get(`/intake/${id}`)).data,
  });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: async () => (await api.get("/users")).data });
  const { data: preview } = useQuery({
    queryKey: ["intake-preview", id],
    queryFn: async () => (await api.get(`/intake/${id}/conversion-preview`)).data,
    enabled: !!intake && ["accepted", "converted_to_quote", "converted_to_order"].includes(intake.status),
  });

  const [draft, setDraft] = useState(null);
  const editable = draft || intake;
  function startEdit() { setDraft({ ...intake }); setEditingDetails(true); }
  function cancelEdit() { setDraft(null); setEditingDetails(false); }

  const invalidate = () => qc.invalidateQueries({ queryKey: ["intake", id] });

  const patchIntake = useMutation({
    mutationFn: async (payload) => (await api.patch(`/intake/${id}`, payload)).data,
    onSuccess: () => { invalidate(); },
    onError: (err) => toast.error(extractError(err)),
  });

  const doTransition = useMutation({
    mutationFn: async ({ target, reason }) => (await api.post(`/intake/${id}/transition`, { target, reason })).data,
    onSuccess: (data) => { invalidate(); toast.success(`Intake moved to ${data.status.replace(/_/g, " ")}`); setReasonTarget(null); },
    onError: (err) => toast.error(extractError(err)),
  });

  const addItemMut = useMutation({
    mutationFn: async (item) => (await api.post(`/intake/${id}/items`, item)).data,
    onSuccess: () => { invalidate(); setNewItem(null); toast.success("Item added"); },
    onError: (err) => toast.error(extractError(err)),
  });
  const updateItemMut = useMutation({
    mutationFn: async ({ itemId, patch }) => (await api.patch(`/intake/${id}/items/${itemId}`, patch)).data,
    onSuccess: () => { invalidate(); toast.success("Item updated"); },
    onError: (err) => toast.error(extractError(err)),
  });
  const removeItemMut = useMutation({
    mutationFn: async (itemId) => (await api.delete(`/intake/${id}/items/${itemId}`)).data,
    onSuccess: () => { invalidate(); toast.success("Item removed"); },
    onError: (err) => toast.error(extractError(err)),
  });
  const duplicateItemMut = useMutation({
    mutationFn: async (itemId) => (await api.post(`/intake/${id}/items/${itemId}/duplicate`)).data,
    onSuccess: () => { invalidate(); toast.success("Item duplicated"); },
    onError: (err) => toast.error(extractError(err)),
  });
  const reorderMut = useMutation({
    mutationFn: async (item_ids) => (await api.patch(`/intake/${id}/items/reorder`, { item_ids })).data,
    onSuccess: () => invalidate(),
    onError: (err) => toast.error(extractError(err)),
  });

  const canEditIntake = intake && ["draft", "needs_information"].includes(intake.status);
  const allowedTargets = intake ? (ALLOWED_TRANSITIONS[intake.status] || []) : [];

  function handleTransitionClick(target) {
    if (["rejected", "cancelled"].includes(target)) { setReasonTarget(target); return; }
    doTransition.mutate({ target });
  }

  function moveItem(idx, dir) {
    const ids = intake.items.map((i) => i.id);
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= ids.length) return;
    [ids[idx], ids[newIdx]] = [ids[newIdx], ids[idx]];
    reorderMut.mutate(ids);
  }

  if (isLoading || !intake) return <div className="p-6 text-sm text-muted-foreground" data-testid="intake-detail-loading">Loading…</div>;

  return (
    <div className="space-y-4" data-testid="intake-detail-page">
      <PageHeader
        title={`IN-${intake.intake_number} · ${intake.project_name || intake.contact_name || "Untitled"}`}
        subtitle={<span className="flex items-center gap-2"><StatusPill kind="intake" value={intake.status} /><StatusPill kind="intake_priority" value={intake.priority} /></span>}
        actions={
          <div className="flex flex-wrap gap-2">
            {canWrite && allowedTargets.map((t) => (
              <Button key={t} size="sm" variant={t === "rejected" || t === "cancelled" ? "outline" : "default"} onClick={() => handleTransitionClick(t)} data-testid={`intake-transition-${t}-button`}>
                {TRANSITION_LABELS[t]}
              </Button>
            ))}
          </div>
        }
      />

      {intake.missing_information?.length > 0 && (
        <div className="rounded-lg bg-amber-50 ring-1 ring-amber-200 p-3 text-sm text-amber-900 flex items-start gap-2" data-testid="intake-missing-info-banner">
          <AlertTriangle className="size-4 mt-0.5" />
          <div>Missing before submission: {intake.missing_information.join(", ")}</div>
        </div>
      )}

      <ReasonDialog
        open={!!reasonTarget} onOpenChange={(v) => !v && setReasonTarget(null)}
        title={reasonTarget === "rejected" ? "Reject intake" : "Cancel intake"}
        busy={doTransition.isPending}
        onConfirm={(reason) => doTransition.mutate({ target: reasonTarget, reason })}
      />

      <div className="rounded-xl border bg-card p-4 grid gap-3" data-testid="intake-details-section">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm">Details</h3>
          {canWrite && canEditIntake && (
            editingDetails ? (
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={cancelEdit}>Cancel</Button>
                <Button size="sm" onClick={() => { patchIntake.mutate(draft); setEditingDetails(false); setDraft(null); }} data-testid="intake-save-details-button">Save</Button>
              </div>
            ) : <Button size="sm" variant="outline" onClick={startEdit} data-testid="intake-edit-details-button">Edit</Button>
          )}
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><Label className="text-xs text-muted-foreground">Contact</Label><div>{intake.contact_name || "—"} {intake.contact_email ? `· ${intake.contact_email}` : ""}</div></div>
          <div><Label className="text-xs text-muted-foreground">Source</Label><div className="capitalize">{(intake.source_type || "").replace(/_/g, " ")}</div></div>
        </div>
        {editingDetails ? (
          <div className="grid gap-3">
            <div className="grid gap-1.5"><Label>Project name</Label><Input value={editable.project_name || ""} onChange={(e) => setDraft({ ...draft, project_name: e.target.value })} data-testid="intake-detail-project-name-input" /></div>
            <div className="grid gap-1.5"><Label>Project description</Label><Textarea rows={2} value={editable.project_description || ""} onChange={(e) => setDraft({ ...draft, project_description: e.target.value })} data-testid="intake-detail-project-description-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5"><Label>Requested due date</Label><Input type="date" value={editable.requested_due_date || ""} onChange={(e) => setDraft({ ...draft, requested_due_date: e.target.value })} data-testid="intake-detail-due-date-input" /></div>
              <div className="grid gap-1.5">
                <Label>Assigned to</Label>
                <Select value={editable.assigned_user_id || "__none__"} onValueChange={(v) => setDraft({ ...draft, assigned_user_id: v === "__none__" ? null : v })}>
                  <SelectTrigger data-testid="intake-detail-assigned-user-select"><SelectValue placeholder="Unassigned" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">Unassigned</SelectItem>
                    {(users || []).map((u) => <SelectItem key={u.id} value={u.id}>{u.name || u.email}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5"><Label>Customer notes</Label><Textarea rows={2} value={editable.customer_notes || ""} onChange={(e) => setDraft({ ...draft, customer_notes: e.target.value })} data-testid="intake-detail-customer-notes-input" /></div>
              <div className="grid gap-1.5"><Label>Internal notes</Label><Textarea rows={2} value={editable.internal_notes || ""} onChange={(e) => setDraft({ ...draft, internal_notes: e.target.value })} data-testid="intake-detail-internal-notes-input" /></div>
            </div>
            <div className="grid gap-1.5">
              <Label>Intake-level files</Label>
              <FileAttachmentPicker fileIds={editable.file_ids || []} onChange={(ids) => setDraft({ ...draft, file_ids: ids })} testIdPrefix="intake-detail-files" />
            </div>
          </div>
        ) : (
          <div className="grid gap-2 text-sm">
            <div>{intake.project_description || <span className="text-muted-foreground">No description</span>}</div>
            <div className="flex flex-wrap gap-4 text-muted-foreground">
              <span>Due: {intake.requested_due_date || "—"}</span>
              <span>Assigned: {(users || []).find((u) => u.id === intake.assigned_user_id)?.name || "Unassigned"}</span>
            </div>
            <FileAttachmentPicker fileIds={intake.file_ids || []} testIdPrefix="intake-detail-files-readonly" />
          </div>
        )}
      </div>

      <div className="rounded-xl border bg-card p-4 grid gap-3" data-testid="intake-items-section">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm">Items ({intake.items?.length || 0})</h3>
          {canWrite && canEditIntake && (
            <Button size="sm" variant="outline" onClick={() => setNewItem(blankIntakeItem())} data-testid="intake-add-item-button"><Plus className="size-4 mr-1" />Add item</Button>
          )}
        </div>
        {newItem && (
          <div className="relative">
            <IntakeItemForm item={newItem} onChange={setNewItem} detailed testIdPrefix="intake-new-item" />
            <div className="flex justify-end gap-2 mt-2">
              <Button size="sm" variant="ghost" onClick={() => setNewItem(null)}>Cancel</Button>
              <Button size="sm" onClick={() => { const { _localId, ...rest } = newItem; addItemMut.mutate(rest); }} data-testid="intake-new-item-save-button">Save item</Button>
            </div>
          </div>
        )}
        {(intake.items || []).map((item, idx) => (
          <div key={item.id} className="relative">
            <IntakeItemForm
              item={item}
              detailed={canEditIntake}
              onChange={(next) => canEditIntake && updateItemMut.mutate({ itemId: item.id, patch: next })}
              testIdPrefix={`intake-item-${item.id}`}
            />
            {canWrite && (
              <div className="absolute top-3 right-3 flex gap-1">
                <Button size="icon" variant="ghost" onClick={() => moveItem(idx, -1)} disabled={idx === 0} data-testid={`intake-item-${item.id}-move-up-button`}><ArrowUp className="size-4" /></Button>
                <Button size="icon" variant="ghost" onClick={() => moveItem(idx, 1)} disabled={idx === (intake.items.length - 1)} data-testid={`intake-item-${item.id}-move-down-button`}><ArrowDown className="size-4" /></Button>
                {canEditIntake && (
                  <>
                    <Button size="icon" variant="ghost" onClick={() => duplicateItemMut.mutate(item.id)} data-testid={`intake-item-${item.id}-duplicate-button`}><Copy className="size-4" /></Button>
                    <Button size="icon" variant="ghost" onClick={() => removeItemMut.mutate(item.id)} disabled={item.conversion_status !== "pending"} data-testid={`intake-item-${item.id}-remove-button`}><Trash2 className="size-4" /></Button>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {preview && (
        <div className="rounded-xl border bg-card p-4 grid gap-2" data-testid="intake-conversion-preview-section">
          <h3 className="font-semibold text-sm">Conversion preview (read-only)</h3>
          <p className="text-xs text-muted-foreground">What a Quote Line Item / Order Item would look like — no price is invented here; pricing happens in the calculator.</p>
          {preview.quote_line_item_previews.map((p, i) => (
            <div key={i} className="text-sm rounded border p-2" data-testid={`intake-conversion-preview-item-${i}`}>
              {p.description} · qty {p.quantity} · {p.category || "no category"}
            </div>
          ))}
        </div>
      )}

      <div className="rounded-xl border bg-card p-4 grid gap-2" data-testid="intake-status-history-section">
        <h3 className="font-semibold text-sm">Status history</h3>
        {(intake.status_history || []).length === 0 ? (
          <div className="text-sm text-muted-foreground">No transitions yet.</div>
        ) : (
          <ul className="grid gap-1.5">
            {intake.status_history.map((h, i) => (
              <li key={i} className="text-sm flex items-center gap-2" data-testid={`intake-status-history-${i}`}>
                <StatusPill kind="intake" value={h.to} />
                <span className="text-muted-foreground">{h.from} → {h.to} · {h.actor_email} · {relativeTime(h.at)}{h.reason ? ` · "${h.reason}"` : ""}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
