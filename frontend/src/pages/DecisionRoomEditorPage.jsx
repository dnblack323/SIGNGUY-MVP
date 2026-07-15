import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import StatusPill from "@/components/common/StatusPill";
import DecisionOptionCard from "@/components/decisionRoom/DecisionOptionCard";
import DecisionRoomVersionHistory from "@/components/decisionRoom/DecisionRoomVersionHistory";
import DecisionRoomPreviewDialog from "@/components/decisionRoom/DecisionRoomPreviewDialog";
import { toast } from "sonner";
import { AlertTriangle, Eye, History, Plus } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { ALLOWED_ROOM_TRANSITIONS, ROOM_TRANSITION_LABELS, blankDecisionOption } from "@/lib/decisionRoom";

export default function DecisionRoomEditorPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("decision_room:write");
  const canPublish = hasPerm("decision_room:publish");
  const canArchive = hasPerm("decision_room:archive");
  const [editingHeader, setEditingHeader] = useState(false);
  const [headerDraft, setHeaderDraft] = useState(null);
  const [showVersions, setShowVersions] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const { data: room, isLoading } = useQuery({
    queryKey: ["decision-room", id],
    queryFn: async () => (await api.get(`/decision-rooms/${id}`)).data,
  });
  const { data: readiness } = useQuery({
    queryKey: ["decision-room-readiness", id],
    queryFn: async () => (await api.get(`/decision-rooms/${id}/readiness`)).data,
    enabled: !!room,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["decision-room", id] });
    qc.invalidateQueries({ queryKey: ["decision-room-readiness", id] });
  };
  const onError = (err) => toast.error(extractError(err));

  const patchRoom = useMutation({ mutationFn: async (payload) => (await api.patch(`/decision-rooms/${id}`, payload)).data, onSuccess: invalidate, onError });
  const addOption = useMutation({ mutationFn: async (payload) => (await api.post(`/decision-rooms/${id}/options`, payload)).data, onSuccess: () => { invalidate(); toast.success("Option added"); }, onError });
  const updateOption = useMutation({ mutationFn: async ({ optionId, patch }) => (await api.patch(`/decision-rooms/${id}/options/${optionId}`, patch)).data, onSuccess: invalidate, onError });
  const duplicateOption = useMutation({ mutationFn: async (optionId) => (await api.post(`/decision-rooms/${id}/options/${optionId}/duplicate`)).data, onSuccess: () => { invalidate(); toast.success("Option duplicated"); }, onError });
  const reorderOptions = useMutation({ mutationFn: async (option_ids) => (await api.patch(`/decision-rooms/${id}/options/reorder`, { option_ids })).data, onSuccess: invalidate, onError });
  const archiveOption = useMutation({ mutationFn: async (optionId) => (await api.post(`/decision-rooms/${id}/options/${optionId}/archive`)).data, onSuccess: invalidate, onError });
  const restoreOption = useMutation({ mutationFn: async (optionId) => (await api.post(`/decision-rooms/${id}/options/${optionId}/restore`)).data, onSuccess: invalidate, onError });
  const attachSnapshot = useMutation({ mutationFn: async ({ optionId, pricing_snapshot_id }) => (await api.post(`/decision-rooms/${id}/options/${optionId}/pricing-snapshot/attach`, { pricing_snapshot_id })).data, onSuccess: invalidate, onError });
  const detachSnapshot = useMutation({ mutationFn: async (optionId) => (await api.post(`/decision-rooms/${id}/options/${optionId}/pricing-snapshot/detach`)).data, onSuccess: invalidate, onError });
  const attachMedia = useMutation({ mutationFn: async ({ optionId, fields }) => (await api.post(`/decision-rooms/${id}/options/${optionId}/media/attach`, fields)).data, onSuccess: invalidate, onError });
  const detachMedia = useMutation({ mutationFn: async ({ optionId, field_names }) => (await api.post(`/decision-rooms/${id}/options/${optionId}/media/detach`, { field_names })).data, onSuccess: invalidate, onError });
  const doTransition = useMutation({
    mutationFn: async (target) => (await api.post(`/decision-rooms/${id}/transition`, { target })).data,
    onSuccess: (data) => { invalidate(); toast.success(`Decision Room moved to ${data.status.replace(/_/g, " ")}`); },
    onError,
  });
  const publish = useMutation({
    mutationFn: async () => (await api.post(`/decision-rooms/${id}/publish`)).data,
    onSuccess: (data) => { invalidate(); toast.success(`Published version ${data.published_version}`); },
    onError,
  });

  if (isLoading || !room) return <div className="p-6 text-sm text-muted-foreground" data-testid="decision-room-editor-loading">Loading…</div>;

  const editable = headerDraft || room;
  const editableStatus = !["expired", "closed", "archived"].includes(room.status);
  const allowedTargets = (ALLOWED_ROOM_TRANSITIONS[room.status] || []).filter((t) => t !== "archived" || canArchive);
  const options = [...(room.options || [])].sort((a, b) => a.display_order - b.display_order);
  const unpublishedChanges = room.status === "published" && room.current_version !== room.published_version;

  function moveOption(idx, dir) {
    const ids = options.map((o) => o.id);
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= ids.length) return;
    [ids[idx], ids[newIdx]] = [ids[newIdx], ids[idx]];
    reorderOptions.mutate(ids);
  }

  return (
    <div className="space-y-4" data-testid="decision-room-editor-page">
      <PageHeader
        title={room.title}
        subtitle={
          <span className="flex items-center gap-2 flex-wrap">
            <StatusPill kind="decision_room" value={room.status} />
            {unpublishedChanges && <span className="text-xs text-amber-700" data-testid="decision-room-unpublished-changes-badge">Unpublished changes (current v{room.current_version} vs published v{room.published_version})</span>}
          </span>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => setShowPreview(true)} data-testid="decision-room-preview-button"><Eye className="size-4 mr-1" />Preview</Button>
            <Button size="sm" variant="outline" onClick={() => setShowVersions(true)} data-testid="decision-room-versions-button"><History className="size-4 mr-1" />Versions</Button>
            {canWrite && allowedTargets.map((t) => (
              <Button key={t} size="sm" variant={t === "archived" ? "outline" : "default"} onClick={() => doTransition.mutate(t)} data-testid={`decision-room-transition-${t}-button`}>
                {ROOM_TRANSITION_LABELS[t]}
              </Button>
            ))}
            {canPublish && ["ready", "published"].includes(room.status) && (
              <Button size="sm" onClick={() => publish.mutate()} data-testid="decision-room-publish-button">
                {room.status === "published" ? "Publish new version" : "Publish"}
              </Button>
            )}
            {canArchive && room.status === "archived" && (
              <Button size="sm" onClick={() => api.post(`/decision-rooms/${id}/restore`).then(invalidate)} data-testid="decision-room-restore-button">Restore</Button>
            )}
          </div>
        }
      />

      {readiness && !readiness.ready && editableStatus && (
        <div className="rounded-lg bg-amber-50 ring-1 ring-amber-200 p-3 text-sm text-amber-900 flex items-start gap-2" data-testid="decision-room-readiness-banner">
          <AlertTriangle className="size-4 mt-0.5" />
          <div>Not ready to publish: {readiness.errors.join(", ")}</div>
        </div>
      )}

      <div className="rounded-xl border bg-card p-4 grid gap-3" data-testid="decision-room-details-section">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm">Room details</h3>
          {canWrite && editableStatus && (
            editingHeader ? (
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => { setEditingHeader(false); setHeaderDraft(null); }}>Cancel</Button>
                <Button size="sm" onClick={() => { patchRoom.mutate(headerDraft); setEditingHeader(false); setHeaderDraft(null); }} data-testid="decision-room-save-details-button">Save</Button>
              </div>
            ) : <Button size="sm" variant="outline" onClick={() => { setHeaderDraft({ ...room }); setEditingHeader(true); }} data-testid="decision-room-edit-details-button">Edit</Button>
          )}
        </div>
        {editingHeader ? (
          <div className="grid gap-3">
            <div className="grid gap-1.5"><Label>Title</Label><Input value={editable.title} onChange={(e) => setHeaderDraft({ ...headerDraft, title: e.target.value })} data-testid="decision-room-detail-title-input" /></div>
            <div className="grid gap-1.5"><Label>Customer-safe introduction</Label><Textarea rows={2} value={editable.customer_safe_intro || ""} onChange={(e) => setHeaderDraft({ ...headerDraft, customer_safe_intro: e.target.value })} data-testid="decision-room-detail-intro-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5"><Label>Expiration date</Label><Input type="date" value={editable.expiration_at || ""} onChange={(e) => setHeaderDraft({ ...headerDraft, expiration_at: e.target.value })} data-testid="decision-room-detail-expiration-input" /></div>
              <div className="grid gap-1.5"><Label>Order id</Label><Input value={editable.order_id || ""} onChange={(e) => setHeaderDraft({ ...headerDraft, order_id: e.target.value })} data-testid="decision-room-detail-order-input" /></div>
            </div>
          </div>
        ) : (
          <div className="grid gap-1 text-sm text-muted-foreground">
            <div>{room.customer_safe_intro || "No customer-safe introduction yet"}</div>
            <div className="flex gap-4">
              <span>Customer: {room.customer_id || "—"}</span>
              <span>Order: {room.order_id || "—"} · Quote: {room.quote_id || "—"} · Intake: {room.intake_id || "—"}</span>
              <span>Expires: {room.expiration_at || "—"}</span>
            </div>
          </div>
        )}
      </div>

      <div className="grid gap-3" data-testid="decision-room-options-section">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm">Options ({options.length})</h3>
          {canWrite && editableStatus && (
            <Button size="sm" variant="outline" onClick={() => addOption.mutate(blankDecisionOption())} data-testid="decision-room-add-option-button"><Plus className="size-4 mr-1" />Add option</Button>
          )}
        </div>
        {options.map((option, idx) => (
          <DecisionOptionCard
            key={option.id} option={option} testIdPrefix={`decision-option-${option.id}`}
            disabled={!canWrite || !editableStatus}
            canMoveUp={idx > 0} canMoveDown={idx < options.length - 1}
            onMoveUp={() => moveOption(idx, -1)} onMoveDown={() => moveOption(idx, 1)}
            onChange={(patch) => updateOption.mutate({ optionId: option.id, patch })}
            onDuplicate={() => duplicateOption.mutate(option.id)}
            onArchiveToggle={() => (option.active === false ? restoreOption.mutate(option.id) : archiveOption.mutate(option.id))}
            onAttachSnapshot={(snapshotId) => attachSnapshot.mutate({ optionId: option.id, pricing_snapshot_id: snapshotId })}
            onDetachSnapshot={() => detachSnapshot.mutate(option.id)}
            onAttachField={(field, val) => attachMedia.mutate({ optionId: option.id, fields: { [field]: val } })}
            onDetachField={(fields) => detachMedia.mutate({ optionId: option.id, field_names: fields })}
          />
        ))}
      </div>

      <DecisionRoomVersionHistory roomId={id} open={showVersions} onOpenChange={setShowVersions} />
      <DecisionRoomPreviewDialog roomId={id} open={showPreview} onOpenChange={setShowPreview} />
    </div>
  );
}
