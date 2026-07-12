import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { FileImage, Plus, Send, RefreshCw } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";

const PROOF_STATUSES = {
  draft: "Draft", sent: "Sent", viewed: "Viewed", approved: "Approved",
  changes_requested: "Changes requested", cancelled: "Cancelled", superseded: "Superseded",
};
const ALLOWED_NEXT = {
  draft: ["sent", "cancelled"], sent: ["viewed", "approved", "changes_requested", "cancelled"],
  viewed: ["approved", "changes_requested", "cancelled"],
  approved: ["superseded", "cancelled"], changes_requested: ["sent", "cancelled"],
  cancelled: [], superseded: [],
};
const REASON_REQUIRED = new Set(["changes_requested", "cancelled"]);

export default function ProofsPanel({ orderId, customerId }) {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("document:write");
  const [openCreate, setOpenCreate] = useState(false);
  const [openVersion, setOpenVersion] = useState(null); // proof id
  const [openReason, setOpenReason] = useState(null);   // {id, target}

  const { data } = useQuery({
    queryKey: ["order-proofs", orderId],
    queryFn: async () => (await api.get("/proofs", { params: { parent_type: "order", parent_id: orderId, limit: 50 } })).data,
    enabled: !!orderId,
  });
  const proofs = data?.items || [];

  const transition = useMutation({
    mutationFn: async ({ id, target, reason }) => (await api.post(`/proofs/${id}/transition`, { target, reason })).data,
    onSuccess: () => { toast.success("Updated"); qc.invalidateQueries({ queryKey: ["order-proofs", orderId] }); },
    onError: (e) => toast.error(extractError(e)),
  });

  return (
    <Card data-testid="proofs-panel">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base flex items-center gap-2"><FileImage className="size-4" />Proofs</CardTitle>
        {canWrite && (
          <Button size="sm" onClick={() => setOpenCreate(true)} data-testid="proofs-create-btn">
            <Plus className="size-4 mr-1" />New proof
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {proofs.length === 0 ? (
          <div className="text-sm text-muted-foreground italic">No proofs yet.</div>
        ) : (
          <ul className="divide-y">
            {proofs.map((p) => (
              <li key={p.id} className="py-2 grid grid-cols-[1fr_auto] gap-2 items-center" data-testid={`proof-row-${p.id}`}>
                <div>
                  <div className="text-sm font-medium">P-{p.number} · v{p.current_version} · <span className="capitalize">{PROOF_STATUSES[p.status] || p.status}</span></div>
                  <div className="text-xs text-muted-foreground">{p.title}</div>
                  {p.changes_requested_reason && <div className="text-xs text-rose-700">Changes: {p.changes_requested_reason}</div>}
                </div>
                {canWrite && (
                  <div className="flex items-center gap-1 flex-wrap justify-end">
                    <Button variant="outline" size="sm" onClick={() => setOpenVersion(p.id)} data-testid={`proof-new-version-${p.id}`}>
                      <RefreshCw className="size-3 mr-1" />New version
                    </Button>
                    {(ALLOWED_NEXT[p.status] || []).map((t) => (
                      <Button
                        key={t}
                        variant={t === "sent" ? "default" : "outline"}
                        size="sm"
                        onClick={() => {
                          if (REASON_REQUIRED.has(t)) setOpenReason({ id: p.id, target: t });
                          else transition.mutate({ id: p.id, target: t });
                        }}
                        data-testid={`proof-transition-${p.id}-${t}`}
                      >
                        {t === "sent" && <Send className="size-3 mr-1" />}
                        <span className="capitalize">{t.replace("_", " ")}</span>
                      </Button>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <CreateProofDialog
        open={openCreate} onOpenChange={setOpenCreate}
        orderId={orderId} customerId={customerId}
        onCreated={() => qc.invalidateQueries({ queryKey: ["order-proofs", orderId] })}
      />
      <ProofVersionDialog
        proofId={openVersion} open={!!openVersion}
        onOpenChange={(o) => !o && setOpenVersion(null)}
        onSaved={() => qc.invalidateQueries({ queryKey: ["order-proofs", orderId] })}
      />
      <ProofReasonDialog
        pending={openReason} open={!!openReason}
        onOpenChange={(o) => !o && setOpenReason(null)}
        onConfirm={(reason) => {
          transition.mutate({ id: openReason.id, target: openReason.target, reason });
          setOpenReason(null);
        }}
        busy={transition.isPending}
      />
    </Card>
  );
}

function CreateProofDialog({ open, onOpenChange, orderId, customerId, onCreated }) {
  const [title, setTitle] = useState("");
  const [fileId, setFileId] = useState("");
  const [description, setDescription] = useState("");
  const create = useMutation({
    mutationFn: async () => (await api.post("/proofs", {
      parent_type: "order", parent_id: orderId, title, description,
      file_id: fileId || null, customer_id: customerId || null,
    })).data,
    onSuccess: () => { toast.success("Proof created"); onOpenChange(false); setTitle(""); setFileId(""); setDescription(""); onCreated?.(); },
    onError: (e) => toast.error(extractError(e)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="create-proof-dialog">
        <DialogHeader><DialogTitle>New proof</DialogTitle><DialogDescription>Version 1 will be created against this order.</DialogDescription></DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Title</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} data-testid="create-proof-title" /></div>
          <div className="grid gap-1.5"><Label>Attached File ID (optional)</Label><Input value={fileId} onChange={(e) => setFileId(e.target.value)} data-testid="create-proof-file-id" /></div>
          <div className="grid gap-1.5"><Label>Description</Label><Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => create.mutate()} disabled={!title || create.isPending} data-testid="create-proof-submit">Create</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ProofVersionDialog({ proofId, open, onOpenChange, onSaved }) {
  const [fileId, setFileId] = useState("");
  const [notes, setNotes] = useState("");
  const save = useMutation({
    mutationFn: async () => (await api.post(`/proofs/${proofId}/versions`, { file_id: fileId, notes })).data,
    onSuccess: () => { toast.success("Version added"); onOpenChange(false); setFileId(""); setNotes(""); onSaved?.(); },
    onError: (e) => toast.error(extractError(e)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="proof-version-dialog">
        <DialogHeader><DialogTitle>Add proof version</DialogTitle><DialogDescription>Snapshotting a new file bumps the proof to a new version and resets status to draft.</DialogDescription></DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>File ID</Label><Input value={fileId} onChange={(e) => setFileId(e.target.value)} data-testid="proof-version-file-id" /></div>
          <div className="grid gap-1.5"><Label>Notes</Label><Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => save.mutate()} disabled={!fileId || save.isPending} data-testid="proof-version-submit">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ProofReasonDialog({ pending, open, onOpenChange, onConfirm, busy }) {
  const [reason, setReason] = useState("");
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) { setReason(""); onOpenChange(false); } }}>
      <DialogContent data-testid="proof-reason-dialog">
        <DialogHeader><DialogTitle>Reason required</DialogTitle><DialogDescription>Provide a reason for this transition.</DialogDescription></DialogHeader>
        <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="proof-reason-input" autoFocus />
        <DialogFooter>
          <Button variant="outline" onClick={() => { setReason(""); onOpenChange(false); }}>Cancel</Button>
          <Button onClick={() => { onConfirm(reason.trim()); setReason(""); }} disabled={busy || !reason.trim()} data-testid="proof-reason-confirm">Confirm</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
