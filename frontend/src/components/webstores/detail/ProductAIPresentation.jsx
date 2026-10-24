import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { DecisionRoomMedia } from "@/components/decisionRoom/DecisionRoomMedia";
import { extractError } from "@/lib/api";
import { previewWebstorePresentation, listWebstorePresentations, generateWebstorePresentation, reviewWebstorePresentation } from "@/lib/webstores";

export default function ProductAIPresentation({ model, variantId, onAccepted, busy: parentBusy }) {
  const { id, productDraft } = model;
  const kind = String(productDraft.product_type || "").toLowerCase().replace(/[_ ]/g, "-");
  const supported = ["t-shirt", "tshirt", "tee"].includes(kind);
  const qc = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const requestStorageKey = `webstore-presentation-request:${productDraft.id}`;
  const key = useRef(sessionStorage.getItem(requestStorageKey));
  const preview = useQuery({ queryKey: ["webstore-presentation-preview", id, productDraft.id], queryFn: () => previewWebstorePresentation(id, productDraft.id), enabled: supported, retry: false });
  const queryKey = ["webstore-presentations", id, productDraft.id];
  const history = useQuery({ queryKey, queryFn: () => listWebstorePresentations(id, productDraft.id), enabled: supported, retry: false });
  const rows = history.data?.items || [];
  const unresolved = rows.some((r) => ["received", "reserved", "executing"].includes(r.status));
  const charge = preview.data?.credit_charge_credits;
  useEffect(() => { setConfirmed(false); }, [charge, variantId, productDraft.revision]);
  const acceptResult = (data) => { qc.setQueryData(queryKey, data); qc.invalidateQueries({ queryKey: ["webstore-setup-files", id] }); };
  const run = useMutation({ retry: false,
    mutationFn: () => {
      if (!key.current) {
        key.current = crypto.randomUUID();
        sessionStorage.setItem(requestStorageKey, key.current);
      }
      return generateWebstorePresentation(id, productDraft.id, { expected_revision: productDraft.revision, variant_id: variantId,
        idempotency_key: key.current, confirmed_credit_charge_credits: charge });
    },
    onSuccess: (data) => {
      acceptResult(data); setConfirmed(false); setError("");
      if (!(data.items || []).some((r) => ["received", "reserved", "executing"].includes(r.status))) {
        key.current = null; sessionStorage.removeItem(requestStorageKey);
      }
    },
    onError: (e) => { setError(`${extractError(e)} Check request status before trying again; the same request identity is retained.`); history.refetch(); },
  });
  const review = useMutation({ retry: false,
    mutationFn: ({ file, decision }) => reviewWebstorePresentation(id, productDraft.id, file.id, { expected_revision: productDraft.revision, decision }),
    onSuccess: (data, request) => { acceptResult(data); setError(""); if (request.decision === "accepted") onAccepted(request.file); },
    onError: (e) => setError(extractError(e)),
  });
  if (!supported) return null;
  const busy = parentBusy || run.isPending || review.isPending;
  return <div className="space-y-3 rounded border bg-muted/20 p-3" data-testid="ai-presentation">
    <h4 className="text-sm font-medium">Generate an unbranded product presentation</h4>
    <p className="text-xs text-muted-foreground">T-shirt front view · saved product color and size · 1024 × 1024. AI may produce the wrong garment or color; review before use. Customer logos are never sent to this generator. Apply original artwork below. No automatic submission or publication.</p>
    <p className="text-xs text-muted-foreground">{[preview.data?.model_display_name, preview.data?.model_key].filter(Boolean).join(" · ")}</p>
    {preview.isError && <p role="alert">{extractError(preview.error)}</p>}
    {preview.data && !preview.data.can_run && <p className="text-sm">{preview.data.unavailable_reason || "AI credits or provider configuration are unavailable."}</p>}
    {preview.data?.can_run && <>
      <Label className="flex items-center gap-2"><Checkbox checked={confirmed} onCheckedChange={(v) => setConfirmed(Boolean(v))} disabled={busy || unresolved} />I confirm {charge} AI credits for one presentation</Label>
      <Button variant="outline" disabled={!variantId || !confirmed || busy || unresolved || history.isPending || history.isError} onClick={() => run.mutate()}>Generate private presentation</Button>
    </>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {(unresolved || history.isError) && <p className="text-sm">A request may be unresolved. No automatic retry. Contact staff responsible for AI reconciliation before starting another generation.</p>}
    <Button size="sm" variant="ghost" disabled={busy || history.isFetching} onClick={() => history.refetch()}>Check request status</Button>
    {rows.map((row) => <div key={row.id} className="space-y-2 rounded border p-2" data-testid={`presentation-${row.id}`}>
      <p className="text-sm">{row.status === "executing" ? "Awaiting reconciliation — credits reserved, no automatic retry" : row.status === "failed" ? "Generation failed — customer credits released" : `${row.status} · ${row.credit_charge_credits} AI credits`}</p>
      {row.file && <>
        <DecisionRoomMedia src={row.file.preview_url} authToken={localStorage.getItem("signguy.token")} alt="Private AI product presentation for staff review" imageClassName="max-h-[340px] w-full rounded border object-contain" />
        <p className="text-xs">{row.file.ai_presentation.color} / {row.file.ai_presentation.size} · {row.file.ai_presentation.review_status} · private</p>
        {row.file.ai_presentation.review_status === "pending" && row.status === "succeeded" && <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={busy} onClick={() => review.mutate({ file: row.file, decision: "accepted" })}>Accept product appearance for composition</Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => review.mutate({ file: row.file, decision: "rejected" })}>Reject presentation</Button>
        </div>}
        <p className="text-xs text-muted-foreground">Review checks the garment, selected color and front view. Rejecting a delivered image does not refund the generation charge. This image is separate from submitted mockups.</p>
      </>}
    </div>)}
  </div>;
}
