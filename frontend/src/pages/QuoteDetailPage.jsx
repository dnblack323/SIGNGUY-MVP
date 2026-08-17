import { useState } from "react";
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
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import StatusPill from "@/components/common/StatusPill";
import { centsToDollarsString } from "@/lib/format";
import { buildApprovalCenterUrl } from "@/lib/approvalCenter";
import { buildShopScheduleUrl } from "@/lib/shopScheduleLinks";
import {
  ArrowLeft, ArrowRightCircle, CalendarDays, Save, Mail, Plus, Pencil, Trash2,
  AlertTriangle, ClipboardCheck, Copy, Download, ExternalLink, Eye, FileText,
  Link2, RotateCw, ShieldOff, TimerOff, Truck,
} from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import ComposeEmailDialog from "@/components/email/ComposeEmailDialog";
import LineItemDialog from "@/components/commerce/LineItemDialog";
import DigitalPrintMinimumAdjustmentRow from "@/components/commerce/DigitalPrintMinimumAdjustmentRow";
import AIContextualActions from "@/components/ai/AIContextualActions";
import ApprovalHistoryPanel from "@/components/approvals/ApprovalHistoryPanel";
import DecisionRoomSharePanel from "@/components/approvals/DecisionRoomSharePanel";
import { useWorkspaceDirty } from "@/context/WorkspaceContext";

// ------------- helpers -------------

function isSentOrLater(status) {
  return status && !["draft"].includes(status);
}

function tokenStatus(token) {
  if (token.revoked) return "revoked";
  if (token.consumed_at) return "used";
  if (token.expires_at && new Date(token.expires_at).getTime() < Date.now()) return "expired";
  return "active";
}

function isWrapLineItem(item) {
  return [item?.category, item?.product_type, item?.description, item?.item_name, item?.material_key].join(" ").toLowerCase().includes("wrap")
    || item?.category === "vehicle_graphics";
}

function buildPublicQuoteUrl(quoteId, token) {
  if (!quoteId || !token) return "";
  return `${window.location.origin}/p/quotes/${quoteId}?t=${encodeURIComponent(token)}`;
}

// ------------- convert dialog -------------

function ConvertToOrderDialog({ quote, disabled, onConverted }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [needOverride, setNeedOverride] = useState(false);
  const [busy, setBusy] = useState(false);

  async function doConvert(allow_expired = false, override_reason = null) {
    setBusy(true);
    try {
      const { data } = await api.post(`/quotes/${quote.id}/convert-to-order`, {
        allow_expired, override_reason,
      });
      toast.success(data.already_converted
        ? `Already converted to O-${data.order.number}`
        : `Converted to O-${data.order.number}`);
      onConverted?.(data);
      setOpen(false);
    } catch (e) {
      const msg = extractError(e);
      if (/expired/i.test(msg) || /override/i.test(msg)) {
        setNeedOverride(true);
        toast.warning(msg);
      } else {
        toast.error(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  function trigger() {
    setOpen(true);
    setNeedOverride(quote.expired === true);
    setReason("");
  }

  return (
    <>
      <Button
        size="sm"
        disabled={disabled}
        onClick={trigger}
        data-testid="quote-convert-button"
      >
        <ArrowRightCircle className="size-4 mr-1" /> Convert to order
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-[480px]" data-testid="convert-dialog">
          <DialogHeader>
            <DialogTitle>Convert Q-{quote.number} to order</DialogTitle>
            <DialogDescription>
              {quote.expired
                ? "This quote is expired. An authorized override with a reason is required."
                : "This creates an Order that copies every line item + pricing snapshot from the current revision."}
            </DialogDescription>
          </DialogHeader>
          {(needOverride || quote.expired) && (
            <div className="grid gap-1.5">
              <Label>Override reason*</Label>
              <Input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. customer approved verbally"
                data-testid="convert-override-reason"
              />
              <div className="text-xs text-muted-foreground flex items-center gap-1">
                <AlertTriangle className="size-3" /> This will be recorded in the audit trail.
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)} type="button">Cancel</Button>
            <Button
              onClick={() => doConvert(needOverride || quote.expired, reason || null)}
              disabled={busy || ((needOverride || quote.expired) && !reason.trim())}
              data-testid="convert-confirm-button"
            >
              {busy ? "Converting…" : "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function StaffApprovalDialog({ quoteId, action, trigger, onDone }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const mutation = useMutation({
    mutationFn: async () => (await api.post(`/quotes/${quoteId}/staff-approval`, { action, reason, comment })).data,
    onSuccess: () => {
      toast.success(action === "approve" ? "Quote approved" : "Quote declined");
      setOpen(false);
      setReason("");
      setComment("");
      onDone?.();
    },
    onError: (e) => toast.error(extractError(e)),
  });

  return (
    <>
      <span onClick={() => setOpen(true)}>{trigger}</span>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-[480px]" data-testid={`quote-staff-${action}-dialog`}>
          <DialogHeader>
            <DialogTitle>{action === "approve" ? "Approve quote" : "Decline quote"}</DialogTitle>
            <DialogDescription>
              Staff overrides require a reason and are recorded in approval history and audit.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label>Reason*</Label>
              <Input
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Customer approved by phone"
                data-testid={`quote-staff-${action}-reason`}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Customer/internal comment</Label>
              <Textarea
                rows={3}
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                data-testid={`quote-staff-${action}-comment`}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button
              type="button"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || !reason.trim()}
              data-testid={`quote-staff-${action}-confirm`}
            >
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function QuoteSharePanel({ quote }) {
  const qc = useQueryClient();
  const [audienceEmail, setAudienceEmail] = useState("");
  const [latestLink, setLatestLink] = useState("");
  const tokens = useQuery({
    queryKey: ["quote-share-tokens", quote.id],
    queryFn: async () => (await api.get(`/quotes/${quote.id}/share-tokens`)).data,
    enabled: Boolean(quote?.id),
  });
  const mint = useMutation({
    mutationFn: async (email) => (await api.post(`/quotes/${quote.id}/share`, {
      audience_email: email || null,
      ttl_hours: 168,
    })).data,
    onSuccess: (data) => {
      setLatestLink(buildPublicQuoteUrl(quote.id, data.token));
      qc.invalidateQueries({ queryKey: ["quote-share-tokens", quote.id] });
      qc.invalidateQueries({ queryKey: ["quote", quote.id] });
      qc.invalidateQueries({ queryKey: ["quote-timeline", quote.id] });
      toast.success("Quote link created. Copy it manually or send it through an approved channel.");
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const resend = useMutation({
    mutationFn: async (tokenId) => (await api.post(`/quotes/${quote.id}/share-tokens/${tokenId}/resend`)).data,
    onSuccess: (data) => {
      setLatestLink(buildPublicQuoteUrl(quote.id, data.token));
      qc.invalidateQueries({ queryKey: ["quote-share-tokens", quote.id] });
      qc.invalidateQueries({ queryKey: ["quote-timeline", quote.id] });
      toast.success("Replacement quote link created. Delivery was not marked as sent.");
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const revoke = useMutation({
    mutationFn: async (tokenId) => api.delete(`/quotes/share-tokens/${tokenId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quote-share-tokens", quote.id] });
      qc.invalidateQueries({ queryKey: ["quote-timeline", quote.id] });
      toast.success("Quote link revoked");
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const expire = useMutation({
    mutationFn: async (tokenId) => api.post(`/quotes/share-tokens/${tokenId}/expire`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quote-share-tokens", quote.id] });
      qc.invalidateQueries({ queryKey: ["quote-timeline", quote.id] });
      toast.success("Quote link expired");
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const copyLatest = async () => {
    if (!latestLink) return;
    try {
      await navigator.clipboard?.writeText(latestLink);
      toast.success("Quote link copied");
    } catch {
      toast.message("Copy the displayed link manually.");
    }
  };
  const items = tokens.data?.items || [];
  return (
    <Card data-testid="quote-share-panel">
      <CardHeader><CardTitle className="text-base">Quote sharing</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2">
          <Label className="text-xs">Audience email (optional)</Label>
          <div className="flex flex-wrap gap-2">
            <Input
              value={audienceEmail}
              onChange={(event) => setAudienceEmail(event.target.value)}
              placeholder="customer@example.com"
              className="min-w-0 flex-1"
              data-testid="quote-share-email"
            />
            <Button type="button" onClick={() => mint.mutate(audienceEmail)} disabled={mint.isPending} data-testid="quote-share-create-button">
              <Link2 className="size-4 mr-1" /> Create link
            </Button>
          </div>
          <div className="text-xs text-muted-foreground">
            This creates a secure quote preview link only. Email or SMS delivery is not marked successful by this service.
          </div>
        </div>
        {latestLink && (
          <div className="rounded-md border p-3 grid gap-2" data-testid="quote-share-latest">
            <Label className="text-xs">Latest one-time-visible link</Label>
            <div className="flex gap-2">
              <Input readOnly value={latestLink} />
              <Button type="button" variant="outline" onClick={copyLatest} data-testid="quote-share-copy-button">
                <Copy className="size-4 mr-1" /> Copy
              </Button>
            </div>
          </div>
        )}
        <div className="space-y-2" data-testid="quote-share-history">
          {items.length === 0 ? (
            <div className="text-sm text-muted-foreground">No quote links have been created yet.</div>
          ) : items.map((token) => (
            <div key={token.id} className="rounded-md border p-3 text-sm" data-testid={`quote-share-token-${token.id}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{token.audience_email || "Manual share link"}</div>
                  <div className="text-xs text-muted-foreground">
                    Revision {token.parent_version || "current"}
                    {token.created_at ? ` · issued ${String(token.created_at).slice(0, 16)}` : ""}
                    {token.expires_at ? ` · expires ${String(token.expires_at).slice(0, 16)}` : ""}
                  </div>
                </div>
                <StatusPill kind="quote" value={tokenStatus(token)} />
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => resend.mutate(token.id)} disabled={resend.isPending} data-testid={`quote-share-resend-${token.id}`}>
                  <RotateCw className="size-4 mr-1" /> Resend link
                </Button>
                {!token.revoked && (
                  <>
                    <Button type="button" size="sm" variant="outline" onClick={() => expire.mutate(token.id)} disabled={expire.isPending} data-testid={`quote-share-expire-${token.id}`}>
                      <TimerOff className="size-4 mr-1" /> Expire
                    </Button>
                    <Button type="button" size="sm" variant="outline" onClick={() => revoke.mutate(token.id)} disabled={revoke.isPending} data-testid={`quote-share-revoke-${token.id}`}>
                      <ShieldOff className="size-4 mr-1" /> Revoke
                    </Button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function QuoteAssetsPanel({ quoteId }) {
  const { data, isLoading } = useQuery({
    queryKey: ["quote-linked-assets", quoteId],
    queryFn: async () => (await api.get(`/quotes/${quoteId}/linked-assets`)).data,
    enabled: Boolean(quoteId),
  });
  const proofs = data?.proofs || [];
  const files = data?.files || [];
  const documents = data?.documents || [];
  return (
    <Card data-testid="quote-assets-panel">
      <CardHeader><CardTitle className="text-base">Proofs, artwork, attachments, and documents</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? <div className="text-sm text-muted-foreground">Loading linked assets...</div> : (
          <>
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">Proofs</div>
              {proofs.length === 0 ? <div className="text-sm text-muted-foreground">No linked proofs.</div> : proofs.map((proof) => (
                <div key={proof.id} className="text-sm flex justify-between border-b py-1">
                  <span>{proof.title || `Proof ${proof.number}`}</span><StatusPill kind="quote" value={proof.status} />
                </div>
              ))}
            </div>
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">Attachments</div>
              {files.length === 0 ? <div className="text-sm text-muted-foreground">No quote attachments.</div> : files.map((file) => (
                <div key={file.id} className="text-sm flex justify-between border-b py-1">
                  <span>{file.original_filename}</span><span className="text-xs text-muted-foreground">{file.visibility}</span>
                </div>
              ))}
            </div>
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">Documents</div>
              {documents.length === 0 ? <div className="text-sm text-muted-foreground">No linked documents.</div> : documents.map((doc) => (
                <div key={doc.id} className="text-sm flex justify-between border-b py-1">
                  <span>{doc.title}</span><span className="text-xs text-muted-foreground">v{doc.version}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function QuoteLifecycleTimeline({ quoteId }) {
  const { data, isLoading } = useQuery({
    queryKey: ["quote-timeline", quoteId],
    queryFn: async () => (await api.get(`/quotes/${quoteId}/timeline`)).data,
    enabled: Boolean(quoteId),
  });
  const items = data?.items || [];
  return (
    <Card data-testid="quote-lifecycle-timeline">
      <CardHeader><CardTitle className="text-base">Quote lifecycle</CardTitle></CardHeader>
      <CardContent className="space-y-2">
        {isLoading ? <div className="text-sm text-muted-foreground">Loading timeline...</div> : items.length === 0 ? (
          <div className="text-sm text-muted-foreground">No quote events yet.</div>
        ) : items.map((event, index) => (
          <div key={`${event.kind}-${event.at}-${index}`} className="grid grid-cols-[110px_1fr] gap-3 text-sm border-b py-2">
            <div className="text-xs text-muted-foreground">{event.at ? String(event.at).slice(0, 16) : "Unknown"}</div>
            <div>
              <div className="font-medium">{event.label}</div>
              <div className="text-xs text-muted-foreground">{event.kind} · {event.source}</div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ------------- line items panel -------------

function LineItemsPanel({ quoteId, quote, lineItems, totals, pricingSummary, canWrite }) {
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [pendingOp, setPendingOp] = useState(null);   // for revision warning
  const [confirmOpen, setConfirmOpen] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["quote", quoteId] });
    qc.invalidateQueries({ queryKey: ["quote-revs", quoteId] });
    qc.invalidateQueries({ queryKey: ["audit-quote", quoteId] });
  };

  async function addItem(payload) {
    await api.post(`/quotes/${quoteId}/line-items`, payload);
    toast.success("Line item added");
    invalidate();
  }
  async function updateItem(itemId, payload) {
    await api.patch(`/quotes/${quoteId}/line-items/${itemId}`, payload);
    toast.success("Line item updated");
    invalidate();
  }
  async function deleteItem(itemId) {
    await api.delete(`/quotes/${quoteId}/line-items/${itemId}`);
    toast.success("Line item removed");
    invalidate();
  }

  function guardOrRun(op) {
    if (isSentOrLater(quote.status)) {
      setPendingOp(() => op);
      setConfirmOpen(true);
    } else {
      op();
    }
  }

  const disabled = !canWrite || quote.status === "converted" || quote.status === "void";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Line items ({lineItems.length})</CardTitle>
        {!disabled && (
          <Button size="sm" onClick={() => guardOrRun(() => setAddOpen(true))} data-testid="quote-line-item-add">
            <Plus className="size-4 mr-1" /> Add item
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {lineItems.length === 0 ? (
          <div className="text-sm text-muted-foreground" data-testid="line-items-empty">
            No line items yet. Backend totals derive from these.
          </div>
        ) : (
          <div className="space-y-1">
            <div className="grid grid-cols-[1fr_80px_120px_120px_80px] gap-2 px-2 py-1 text-xs text-muted-foreground font-medium">
              <div>Description</div>
              <div className="text-right">Qty</div>
              <div className="text-right">Unit</div>
              <div className="text-right">Line total</div>
              <div />
            </div>
            {lineItems.map((li) => (
              <div key={li.id} className="grid grid-cols-[1fr_80px_120px_120px_80px] gap-2 items-center px-2 py-1 border-t text-sm" data-testid={`line-item-row-${li.id}`}>
                <div>
                  <div className="font-medium">{li.description}</div>
                  <div className="text-xs text-muted-foreground">
                    {li.category || "—"}{li.width_inches && li.height_inches ? ` · ${li.width_inches}×${li.height_inches}in` : ""}
                    {li.manual_override_reason ? ` · override: ${li.manual_override_reason}` : ""}
                  </div>
                </div>
                <div className="text-right tabular-nums">{li.quantity}</div>
                <div className="text-right tabular-nums">{centsToDollarsString(li.unit_price_cents)}</div>
                <div className="text-right tabular-nums font-medium">{centsToDollarsString(li.line_total_cents)}</div>
                <div className="flex items-center gap-1 justify-end">
                  {!disabled && (
                    <>
                      <Button variant="ghost" size="icon" onClick={() => guardOrRun(() => setEditing(li))} aria-label="Edit" data-testid={`line-item-edit-${li.id}`}>
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => guardOrRun(() => deleteItem(li.id))} aria-label="Remove" data-testid={`line-item-delete-${li.id}`}>
                        <Trash2 className="size-3.5 text-muted-foreground" />
                      </Button>
                    </>
                  )}
                </div>
              </div>
            ))}
            <div className="grid grid-cols-[1fr_120px] gap-2 pt-3 border-t items-baseline">
              <div className="text-xs text-muted-foreground text-right">Subtotal</div>
              <div className="text-right tabular-nums">{centsToDollarsString(totals.subtotal_cents ?? 0)}</div>
              <div className="text-xs text-muted-foreground text-right">Discount</div>
              <div className="text-right tabular-nums">{centsToDollarsString(totals.discount_cents ?? 0)}</div>
              <div className="text-xs text-muted-foreground text-right">Tax</div>
              <div className="text-right tabular-nums">{centsToDollarsString(totals.tax_cents ?? 0)}</div>
              <DigitalPrintMinimumAdjustmentRow totals={totals} />
              <div className="text-sm font-medium text-right">Total</div>
              <div className="text-right tabular-nums font-semibold" data-testid="quote-derived-total">
                {centsToDollarsString(totals.total_cents ?? quote.total_cents ?? 0)}
              </div>
            </div>
            {pricingSummary?.item_count > 0 && (
              <div className="grid grid-cols-[1fr_120px] gap-2 pt-2 border-t items-baseline" data-testid="quote-pricing-summary">
                <div className="text-xs text-muted-foreground text-right">Est. production cost</div>
                <div className="text-right tabular-nums text-xs">{centsToDollarsString(pricingSummary.total_estimated_cost_cents ?? 0)}</div>
                <div className="text-xs text-muted-foreground text-right">Est. profit / margin</div>
                <div className="text-right tabular-nums text-xs">
                  {centsToDollarsString(pricingSummary.estimated_total_profit_cents ?? 0)} ({pricingSummary.estimated_margin_percent ?? 0}%)
                </div>
                {pricingSummary.items_with_warnings_count > 0 && (
                  <>
                    <div className="text-xs text-amber-700 text-right">Warnings to review</div>
                    <div className="text-right tabular-nums text-xs text-amber-700" data-testid="quote-pricing-warnings-count">{pricingSummary.items_with_warnings_count}</div>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>

      <LineItemDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        mode="add"
        entryMode="detailed"
        entityLabel="Quote"
        onSubmit={addItem}
      />
      <LineItemDialog
        open={!!editing}
        onOpenChange={(v) => !v && setEditing(null)}
        mode="edit"
        entryMode="detailed"
        initial={editing}
        entityLabel="Quote"
        onSubmit={(payload) => updateItem(editing.id, payload)}
        onRecalculatePreview={editing ? async (categoryInputs) => (
          await api.post(`/quotes/${quoteId}/line-items/${editing.id}/recalculate-preview`, { category_inputs: categoryInputs })
        ).data : undefined}
      />

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent data-testid="revision-warning-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Editing will create a new revision</AlertDialogTitle>
            <AlertDialogDescription>
              This quote has already been sent. Continuing will snapshot the current state as an immutable revision
              and increase the current revision number. Prior revisions remain viewable.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="revision-warning-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => { pendingOp?.(); setConfirmOpen(false); }} data-testid="revision-warning-confirm">
              Continue and create revision
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}

// ------------- main page -------------

export default function QuoteDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { hasPerm } = useAuth();

  const { data: qResp, isLoading, isError, error } = useQuery({
    queryKey: ["quote", id],
    queryFn: async () => (await api.get(`/quotes/${id}`)).data,
  });
  const q = qResp?.quote || qResp;
  const lineItems = qResp?.line_items || [];
  const wrapLineItem = lineItems.find(isWrapLineItem);
  const totals = qResp?.totals || {};
  const pricingSummary = qResp?.pricing_summary || {};
  const { data: audit } = useQuery({ queryKey: ["audit-quote", id], queryFn: async () => (await api.get(`/audit`, { params: { entity_type: "quote", entity_id: id } })).data, enabled: !!id });
  const { data: customer } = useQuery({ queryKey: ["customer", q?.customer_id], queryFn: async () => (await api.get(`/customers/${q.customer_id}`)).data, enabled: !!q?.customer_id });
  const { data: revs } = useQuery({ queryKey: ["quote-revs", id], queryFn: async () => (await api.get(`/quotes/${id}/revisions`)).data, enabled: !!id });
  const { data: quoteRooms } = useQuery({
    queryKey: ["quote-decision-rooms", id],
    queryFn: async () => (await api.get("/decision-rooms", { params: { quote_id: id } })).data,
    enabled: !!id && hasPerm("decision_room:read"),
  });
  const { data: publicPreview } = useQuery({
    queryKey: ["quote-public-preview", id],
    queryFn: async () => (await api.get(`/quotes/${id}/public-preview`)).data,
    enabled: !!id,
  });

  const [form, setForm] = useState({});
  useWorkspaceDirty(Object.keys(form).length > 0);
  const [revisionConfirm, setRevisionConfirm] = useState(false);
  const [pendingSave, setPendingSave] = useState(null);

  const save = useMutation({
    mutationFn: async (payload) => (await api.patch(`/quotes/${id}`, payload)).data,
    onSuccess: () => {
      toast.success("Saved");
      qc.invalidateQueries({ queryKey: ["quote", id] });
      qc.invalidateQueries({ queryKey: ["quote-revs", id] });
      qc.invalidateQueries({ queryKey: ["audit-quote", id] });
      setForm({});
    },
    onError: (e) => toast.error(extractError(e)),
  });
  const setStatus = useMutation({
    mutationFn: async (payload) => (await api.post(`/quotes/${id}/status`, payload)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quote", id] });
      qc.invalidateQueries({ queryKey: ["audit-quote", id] });
      qc.invalidateQueries({ queryKey: ["approval-history", "quote", id] });
      qc.invalidateQueries({ queryKey: ["quote-timeline", id] });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  function requestSave() {
    if (!Object.keys(form).length) return;
    if (isSentOrLater(q?.status)) {
      setPendingSave(form);
      setRevisionConfirm(true);
    } else {
      save.mutate(form);
    }
  }

  function requestStatusChange(status) {
    if (status === "declined") {
      const reason = window.prompt("Reason for declining this quote");
      if (!reason?.trim()) return;
      setStatus.mutate({ status, reason: reason.trim(), source: "staff" });
      return;
    }
    setStatus.mutate({ status, source: "staff" });
  }

  if (isLoading) return <div className="text-sm text-muted-foreground" data-testid="quote-loading">Loading quote…</div>;
  if (isError) return <div className="text-sm text-destructive" data-testid="quote-error">{extractError(error)}</div>;
  if (!q) return <div className="text-sm text-muted-foreground">Quote not found.</div>;

  const editable = !["converted", "void"].includes(q.status);
  const canWrite = hasPerm("quote:write");
  const canConvert = hasPerm("quote:convert") && q.status !== "converted" && q.status !== "void" && q.status !== "declined";
  const edit = { ...q, ...form };
  const approvalRoom = (quoteRooms?.items || []).find((room) => !["archived", "closed", "expired"].includes(room.status));
  const refreshQuoteAuthority = () => {
    qc.invalidateQueries({ queryKey: ["quote", id] });
    qc.invalidateQueries({ queryKey: ["audit-quote", id] });
    qc.invalidateQueries({ queryKey: ["approval-history", "quote", id] });
    qc.invalidateQueries({ queryKey: ["approval-center-authority-queue"] });
    qc.invalidateQueries({ queryKey: ["quote-timeline", id] });
  };

  return (
    <div className="space-y-4" data-testid="quote-detail-page">
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="icon"><Link to="/quotes"><ArrowLeft className="size-4" /></Link></Button>
        <PageHeader
          title={<span><span className="mono text-muted-foreground text-lg mr-2">Q-{q.number}</span>{q.job_name}</span>}
          subtitle={<span>
            Customer: <Link className="link-underline" to={`/customers/${q.customer_id}`}>{customer?.name || "…"}</Link>
            {" · Revision "}<span data-testid="quote-current-revision">#{q.revision_number || 1}</span>
            {q.expired && <span className="ml-2 text-amber-600 font-medium" data-testid="quote-expired-badge">Expired</span>}
          </span>}
          actions={(
            <div className="flex items-center gap-2 flex-wrap">
              <AIContextualActions contextType="quote" contextId={id} actions={[
                { label: "AI Quote Email", tool: "email_draft_assistant", mode: "quote_follow_up" },
                { label: "AI Proposal", tool: "proposal_builder", mode: "proposal" },
                { label: "Pricing Advisor", tool: "pricing_profitability", mode: "pricing_advisor" },
              ]} />
              {hasPerm("email:send") && customer?.email && (
                <ComposeEmailDialog
                  defaultTemplate="quote_sent"
                  toEmail={customer.email}
                  customerId={customer.id}
                  relatedType="quote"
                  relatedId={q.id}
                  suggestedSubject={`Quote Q-${q.number} — ${q.job_name}`}
                  suggestedBody={`Hi ${customer.name},\n\nHere's your quote for ${q.job_name}.\nTotal: ${centsToDollarsString(totals.total_cents ?? q.total_cents ?? 0)}`}
                  trigger={<Button variant="outline" size="sm" data-testid="quote-email-button"><Mail className="size-4 mr-1" />Email quote</Button>}
                />
              )}
              {hasPerm("schedule:manage") && q.customer_id && (
                <Button asChild variant="outline" size="sm" data-testid="quote-schedule-customer-button">
                  <Link to={buildShopScheduleUrl({
                    create: true,
                    customerId: q.customer_id,
                    eventType: "customer_meeting",
                    title: `${q.job_name} appointment`,
                  })}>
                    <CalendarDays className="size-4 mr-1" />Schedule
                  </Link>
                </Button>
              )}
              {hasPerm("wrap_lab:read") && (
                <Button asChild variant="outline" size="sm" data-testid="quote-open-wrap-lab-button">
                  <Link to={`/wrap-lab?quote_id=${q.id}${q.customer_id ? `&customer_id=${q.customer_id}` : ""}${wrapLineItem?.id ? `&quote_line_item_id=${wrapLineItem.id}` : ""}`}>
                    <Truck className="size-4 mr-1" />Wrap Lab
                  </Link>
                </Button>
              )}
              {hasPerm("decision_room:read") && (
                <Button asChild variant="outline" size="sm" data-testid="quote-approval-work-button">
                  <Link to={approvalRoom ? `/decision-rooms/${approvalRoom.id}` : buildApprovalCenterUrl({
                    create: true,
                    targetType: "quote",
                    targetId: q.id,
                    customerId: q.customer_id,
                    title: `Q-${q.number} ${q.job_name}`,
                  })}>
                    <ClipboardCheck className="size-4 mr-1" />
                    {approvalRoom ? "Open approval work" : "Approval work"}
                  </Link>
                </Button>
              )}
              {canConvert && (
                <ConvertToOrderDialog quote={q} onConverted={(d) => navigate(`/orders/${d.order.id}`)} />
              )}
              <Button asChild variant="outline" size="sm" data-testid="quote-public-preview-link">
                <a href={`/api/quotes/${q.id}/artifact`} target="_blank" rel="noreferrer">
                  <Eye className="size-4 mr-1" /> Preview artifact
                </a>
              </Button>
              <Button asChild variant="outline" size="sm" data-testid="quote-download-link">
                <a href={`/api/quotes/${q.id}/download`}>
                  <Download className="size-4 mr-1" /> Download
                </a>
              </Button>
              {q.status === "converted" && q.converted_order_id && (
                <Button asChild size="sm" variant="outline" data-testid="quote-open-order">
                  <Link to={`/orders/${q.converted_order_id}`}>Open order</Link>
                </Button>
              )}
            </div>
          )}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        <Tabs defaultValue="line-items" data-testid="detail-tabs">
          <TabsList>
            <TabsTrigger value="line-items" data-testid="detail-tab-line-items">Line items ({lineItems.length})</TabsTrigger>
            <TabsTrigger value="details" data-testid="detail-tab-details">Details</TabsTrigger>
            <TabsTrigger value="revisions" data-testid="detail-tab-revisions">Revisions ({revs?.items?.length || 0})</TabsTrigger>
            <TabsTrigger value="assets" data-testid="detail-tab-assets">Assets</TabsTrigger>
            <TabsTrigger value="activity" data-testid="detail-tab-activity">Activity</TabsTrigger>
          </TabsList>

          <TabsContent value="line-items" className="space-y-2">
            <LineItemsPanel quoteId={id} quote={q} lineItems={lineItems} totals={totals} pricingSummary={pricingSummary} canWrite={canWrite} />
          </TabsContent>

          <TabsContent value="details" className="space-y-4">
            <Card>
              <CardHeader><CardTitle>Quote</CardTitle></CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label>Project name</Label>
                  <Input value={edit.job_name || ""} disabled={!editable || !canWrite} onChange={(e) => setForm((f) => ({ ...f, job_name: e.target.value }))} data-testid="quote-detail-job-name-input" />
                </div>
                <div className="grid gap-1.5">
                  <Label>Expires at</Label>
                  <Input type="date" value={(edit.expires_at || "").slice(0, 10)} disabled={!editable || !canWrite} onChange={(e) => setForm((f) => ({ ...f, expires_at: e.target.value || null }))} data-testid="quote-expires-at" />
                </div>
                <div className="md:col-span-2 grid gap-1.5">
                  <Label>Customer notes</Label>
                  <Textarea rows={3} value={edit.notes_customer || ""} disabled={!editable || !canWrite} onChange={(e) => setForm((f) => ({ ...f, notes_customer: e.target.value }))} data-testid="quote-notes-customer" />
                </div>
                <div className="md:col-span-2 grid gap-1.5">
                  <Label>Internal notes</Label>
                  <Textarea rows={3} value={edit.notes_internal || edit.notes || ""} disabled={!editable || !canWrite} onChange={(e) => setForm((f) => ({ ...f, notes_internal: e.target.value }))} data-testid="quote-notes-internal" />
                </div>
                {editable && canWrite && Object.keys(form).length > 0 && (
                  <div className="md:col-span-2">
                    <Button onClick={requestSave} disabled={save.isPending} data-testid="quote-save-button">
                      <Save className="size-4 mr-1" />
                      {isSentOrLater(q.status) ? "Save (creates revision)" : "Save"}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="revisions" className="space-y-2" data-testid="quote-revisions-tab">
            <Card>
              <CardHeader><CardTitle className="text-base">Revision history</CardTitle></CardHeader>
              <CardContent>
                <div className="text-xs text-muted-foreground mb-2">Current revision: <span className="font-medium">{revs?.current_revision || q.revision_number || 1}</span></div>
                {(revs?.items || []).length === 0 ? (
                  <div className="text-sm text-muted-foreground">No prior revisions. Editing a sent quote creates one automatically.</div>
                ) : (
                  <div className="space-y-2">
                    {(revs?.items || []).map((r) => (
                      <div key={r.id} className="flex items-center justify-between border-b py-1 text-sm" data-testid={`quote-revision-row-${r.revision_number}`}>
                        <div>
                          <div className="font-medium">Revision #{r.revision_number}</div>
                          <div className="text-xs text-muted-foreground">
                            {r.actor_email} · {r.reason || "edited"} · {r.line_items?.length ?? 0} items
                          </div>
                        </div>
                        <div className="tabular-nums">{centsToDollarsString(r.total_cents)}</div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="assets" className="space-y-2">
            <QuoteAssetsPanel quoteId={id} />
          </TabsContent>

          <TabsContent value="activity" className="space-y-4">
            <QuoteLifecycleTimeline quoteId={id} />
            <AuditTimeline events={audit?.items || []} />
          </TabsContent>
        </Tabs>

        <aside className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Status</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2"><StatusPill kind="quote" value={q.status} /></div>
              {editable && canWrite && (
                <div className="grid grid-cols-2 gap-2">
                  {["draft", "sent", "void"].filter((s) => s !== q.status).map((s) => (
                    <Button key={s} size="sm" variant="outline" onClick={() => requestStatusChange(s)} disabled={setStatus.isPending} data-testid={`quote-set-status-${s}`}>
                      <span className="capitalize">{s}</span>
                    </Button>
                  ))}
                  {["sent", "viewed"].includes(q.status) && (
                    <>
                      <StaffApprovalDialog
                        quoteId={q.id}
                        action="approve"
                        onDone={refreshQuoteAuthority}
                        trigger={<Button type="button" size="sm" variant="outline" data-testid="quote-staff-approve-button">Approve</Button>}
                      />
                      <StaffApprovalDialog
                        quoteId={q.id}
                        action="decline"
                        onDone={refreshQuoteAuthority}
                        trigger={<Button type="button" size="sm" variant="outline" data-testid="quote-staff-decline-button">Decline</Button>}
                      />
                    </>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
          <Card data-testid="quote-public-preview-summary">
            <CardHeader><CardTitle className="text-base">Customer-safe preview</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div>Published revision: <span className="font-medium">{publicPreview?.snapshot?.published_revision || q.revision_number || 1}</span></div>
              <div>Total: <span className="font-medium">{centsToDollarsString(publicPreview?.totals?.total_cents ?? totals.total_cents ?? q.total_cents ?? 0)}</span></div>
              <div className="text-xs text-muted-foreground">Internal notes, cost, margin, and draft revision data are excluded.</div>
            </CardContent>
          </Card>
          <QuoteSharePanel quote={q} />
          <Card data-testid="quote-decision-room-panel">
            <CardHeader><CardTitle className="text-base">Decision Room work</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {(quoteRooms?.items || []).length === 0 ? (
                <div className="text-sm text-muted-foreground">No Decision Room is linked to this quote yet.</div>
              ) : (quoteRooms?.items || []).map((room) => (
                <div key={room.id} className="rounded-md border p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="font-medium">{room.title}</div>
                      <div className="text-xs text-muted-foreground">Status: {room.status}</div>
                    </div>
                    <Button asChild size="sm" variant="outline">
                      <Link to={`/decision-rooms/${room.id}`}><ExternalLink className="size-4 mr-1" />Open</Link>
                    </Button>
                  </div>
                </div>
              ))}
              <Button asChild variant="outline" size="sm" data-testid="quote-decision-room-create-link">
                <Link to={buildApprovalCenterUrl({
                  create: true,
                  targetType: "quote",
                  targetId: q.id,
                  customerId: q.customer_id,
                  title: `Q-${q.number} ${q.job_name}`,
                })}>
                  <FileText className="size-4 mr-1" /> Create approval work
                </Link>
              </Button>
            </CardContent>
          </Card>
          {hasPerm("decision_room:read") && (
            <>
              <ApprovalHistoryPanel sourceType="quote" sourceId={q.id} />
              {approvalRoom && <DecisionRoomSharePanel roomId={approvalRoom.id} />}
            </>
          )}
        </aside>
      </div>

      <AlertDialog open={revisionConfirm} onOpenChange={setRevisionConfirm}>
        <AlertDialogContent data-testid="revision-warning-detail-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Editing will create a new revision</AlertDialogTitle>
            <AlertDialogDescription>
              This quote has already been sent to the customer. Saving these changes will create an immutable
              revision snapshot before the edits are applied.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => { if (pendingSave) save.mutate(pendingSave); setRevisionConfirm(false); }} data-testid="revision-warning-detail-confirm">
              Continue and create revision
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
