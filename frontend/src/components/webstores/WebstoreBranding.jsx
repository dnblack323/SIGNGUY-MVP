import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Eye, MessageSquare, Send, Save, Rocket } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { extractError } from "@/lib/api";
import {
  getWebstoreBranding,
  listWebstoreSetupFiles,
  publishWebstoreBranding,
  requestWebstoreBrandingReview,
  saveWebstoreBrandingDraft,
} from "@/lib/webstores";
import portalApi, { portalExtractError } from "@/portal/portalApi";
import { toast } from "sonner";
import { CategoryControls } from "./WebstoreBrandingFields";
import { WebstoreBrandingPreview } from "./WebstoreBrandingPreview";
import { CATEGORY_CARDS, setPath, statusLabel } from "./WebstoreBrandingUtils";

export { WebstoreBrandingPreview } from "./WebstoreBrandingPreview";

export default function WebstoreBrandingEditor({ webstoreId, portal = false, products = [] }) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState("brand_basics");
  const [previewMode, setPreviewMode] = useState("desktop");
  const [note, setNote] = useState("");
  const queryKey = [portal ? "portal-webstore-branding" : "webstore-branding", webstoreId];
  const branding = useQuery({
    queryKey,
    queryFn: async () => {
      if (portal) {
        const r = await portalApi.get(`/portal/webstores/${webstoreId}/branding`);
        return r.data;
      }
      return getWebstoreBranding(webstoreId);
    },
    enabled: !!webstoreId,
  });
  const setupFiles = useQuery({
    queryKey: ["webstore-branding-setup-files", webstoreId],
    queryFn: () => listWebstoreSetupFiles(webstoreId),
    enabled: !!webstoreId,
  });
  const [draftOverride, setDraftOverride] = useState(null);
  const storedDraft = branding.data?.branding?.draft;
  const setupAwareDraft = useMemo(() => {
    const items = setupFiles.data?.items || setupFiles.data || [];
    const baseDraft = storedDraft || {};
    const activeFile = (category) => items.find((item) => item.status === "active" && item.category === category);
    const imageForFile = (file) => file ? {
      file_id: file.id,
      file_name: file.file_name,
      content_type: file.detected_content_type || file.content_type,
      ...(file.preview_url ? { url: file.preview_url } : {}),
    } : {};
    const logo = activeFile("logo");
    const banner = activeFile("banner");
    let next = baseDraft;
    if (logo && !baseDraft.brand_basics?.primary_logo?.file_id && !baseDraft.brand_basics?.primary_logo?.url) {
      next = setPath(next, "brand_basics.primary_logo", imageForFile(logo));
    }
    if (banner && !baseDraft.hero?.image?.file_id && !baseDraft.hero?.image?.url) {
      next = setPath(next, "hero.image", imageForFile(banner));
    }
    return next;
  }, [storedDraft, setupFiles.data]);
  const draft = draftOverride || setupAwareDraft;
  const webstore = branding.data?.webstore || {};
  const permissions = branding.data?.permissions || {};
  const validation = branding.data?.branding?.validation || { errors: [], warnings: [] };
  const invalidate = async () => {
    setDraftOverride(null);
    await qc.invalidateQueries({ queryKey });
  };
  const saveDraft = useMutation({
    mutationFn: () => portal
      ? portalApi.patch(`/portal/webstores/${webstoreId}/branding/draft`, { content: draft })
      : saveWebstoreBrandingDraft(webstoreId, draft),
    onSuccess: async () => { toast.success("Branding draft saved"); await invalidate(); },
    onError: (e) => toast.error(portal ? portalExtractError(e) : extractError(e)),
  });
  const requestReview = useMutation({
    mutationFn: () => portal
      ? portalApi.post(`/portal/webstores/${webstoreId}/branding/request-review`, { note })
      : requestWebstoreBrandingReview(webstoreId, note),
    onSuccess: async () => { toast.success("Owner review requested"); setNote(""); await invalidate(); },
    onError: (e) => toast.error(portal ? portalExtractError(e) : extractError(e)),
  });
  const approve = useMutation({
    mutationFn: () => portalApi.post(`/portal/webstores/${webstoreId}/branding/approve`, { note }),
    onSuccess: async () => { toast.success("Branding approved"); setNote(""); await invalidate(); },
    onError: (e) => toast.error(portalExtractError(e)),
  });
  const changes = useMutation({
    mutationFn: () => portalApi.post(`/portal/webstores/${webstoreId}/branding/request-changes`, { note }),
    onSuccess: async () => { toast.success("Changes requested"); setNote(""); await invalidate(); },
    onError: (e) => toast.error(portalExtractError(e)),
  });
  const publish = useMutation({
    mutationFn: () => publishWebstoreBranding(webstoreId),
    onSuccess: async () => { toast.success("Branding published"); await invalidate(); },
    onError: (e) => toast.error(extractError(e)),
  });
  const status = branding.data?.branding?.status || "draft";
  const selectedLabel = useMemo(() => CATEGORY_CARDS.find(([key]) => key === selected)?.[1] || "Brand Basics", [selected]);

  if (branding.isLoading) return <div className="text-sm text-muted-foreground">Loading branding...</div>;

  return (
    <div className="space-y-4" data-testid="webstore-branding-editor">
      <div className="rounded border bg-white p-2 flex flex-wrap items-center gap-2" data-testid="webstore-branding-ribbon">
        <Badge variant="outline">{statusLabel(status)}</Badge>
        <Button size="sm" variant="outline" onClick={() => saveDraft.mutate()} disabled={!permissions.can_save_draft || saveDraft.isPending}><Save className="size-4 mr-2" />Save Draft</Button>
        <Button size="sm" variant="outline" onClick={() => setPreviewMode(previewMode === "desktop" ? "mobile" : "desktop")}><Eye className="size-4 mr-2" />Preview</Button>
        <Button size="sm" variant="outline" disabled={!branding.data?.branding?.feedback_note} onClick={() => document.querySelector("[data-testid='branding-feedback']")?.scrollIntoView({ block: "center" })}><MessageSquare className="size-4 mr-2" />View Feedback</Button>
        {permissions.can_request_review && <Button size="sm" onClick={() => requestReview.mutate()} disabled={requestReview.isPending}><Send className="size-4 mr-2" />Request Owner Review</Button>}
        {permissions.can_owner_decide && <Button size="sm" onClick={() => approve.mutate()} disabled={approve.isPending || status !== "waiting_owner_approval"}><CheckCircle2 className="size-4 mr-2" />Approve</Button>}
        {permissions.can_owner_decide && <Button size="sm" variant="outline" onClick={() => changes.mutate()} disabled={changes.isPending || !note || status !== "waiting_owner_approval"}><MessageSquare className="size-4 mr-2" />Request Changes</Button>}
        {permissions.can_publish && <Button size="sm" onClick={() => publish.mutate()} disabled={publish.isPending || status !== "owner_approved"}><Rocket className="size-4 mr-2" />Publish</Button>}
      </div>

      {branding.data?.branding?.feedback_note && (
        <Card data-testid="branding-feedback"><CardContent className="p-3 text-sm">Feedback: {branding.data.branding.feedback_note}</CardContent></Card>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,520px)] gap-4">
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2" data-testid="branding-category-cards">
            {CATEGORY_CARDS.map(([key, label]) => (
              <button key={key} type="button" onClick={() => setSelected(key)} className={`rounded border p-3 text-left text-sm ${selected === key ? "border-blue-500 bg-blue-50" : "bg-white hover:bg-slate-50"}`}>
                {label}
              </button>
            ))}
          </div>
          <Card>
            <CardHeader><CardTitle className="text-base">{selectedLabel}</CardTitle></CardHeader>
            <CardContent className="grid gap-3">
              <CategoryControls
                category={selected}
                draft={draft}
                onDraft={setDraftOverride}
                permissions={permissions}
                portal={portal}
                webstoreId={webstoreId}
                storeType={webstore.store_type || "general"}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Review note</CardTitle></CardHeader>
            <CardContent><Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional note or owner feedback" data-testid="branding-review-note" /></CardContent>
          </Card>
        </div>
        <div className="space-y-4">
          {(validation.errors || []).length > 0 && <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" data-testid="branding-validation-errors">{validation.errors.join(" ")}</div>}
          {(validation.warnings || []).length > 0 && <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800" data-testid="branding-validation-warnings">{validation.warnings.join(" ")}</div>}
          <div className="flex gap-2">
            <Button size="sm" variant={previewMode === "desktop" ? "default" : "outline"} onClick={() => setPreviewMode("desktop")}>Desktop</Button>
            <Button size="sm" variant={previewMode === "mobile" ? "default" : "outline"} onClick={() => setPreviewMode("mobile")}>Mobile</Button>
          </div>
          <WebstoreBrandingPreview branding={draft} webstore={webstore} products={products} compact={previewMode === "mobile"} draft />
          <Card>
            <CardHeader><CardTitle className="text-base">Published history</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm" data-testid="branding-history">
              {(branding.data?.history || []).map((version) => (
                <div key={version.id} className="flex items-center justify-between gap-3 rounded border p-2">
                  <span>Version {version.version}</span>
                  <span className="text-muted-foreground">{version.created_at || version.published_at}</span>
                </div>
              ))}
              {(branding.data?.history || []).length === 0 && <div className="text-muted-foreground">No published branding versions yet.</div>}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Branding activity</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm" data-testid="branding-activity">
              {(branding.data?.activity || []).map((row) => (
                <div key={row.id} className="rounded border p-2">
                  <div className="font-medium">{row.summary}</div>
                  <div className="text-xs text-muted-foreground">{row.actor_email || row.actor_id || "Unknown"} - {row.created_at}</div>
                  {row.metadata?.note && <div className="mt-1 text-xs">Note: {row.metadata.note}</div>}
                </div>
              ))}
              {(branding.data?.activity || []).length === 0 && <div className="text-muted-foreground">No branding activity yet.</div>}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
