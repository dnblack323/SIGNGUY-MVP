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
import { ArrowLeft, ArrowRightCircle, Save, Mail, Plus, Pencil, Trash2, AlertTriangle } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import ComposeEmailDialog from "@/components/email/ComposeEmailDialog";
import LineItemDialog from "@/components/commerce/LineItemDialog";
import AIContextualActions from "@/components/ai/AIContextualActions";

// ------------- helpers -------------

function isSentOrLater(status) {
  return status && !["draft"].includes(status);
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
  const totals = qResp?.totals || {};
  const pricingSummary = qResp?.pricing_summary || {};
  const { data: audit } = useQuery({ queryKey: ["audit-quote", id], queryFn: async () => (await api.get(`/audit`, { params: { entity_type: "quote", entity_id: id } })).data, enabled: !!id });
  const { data: customer } = useQuery({ queryKey: ["customer", q?.customer_id], queryFn: async () => (await api.get(`/customers/${q.customer_id}`)).data, enabled: !!q?.customer_id });
  const { data: revs } = useQuery({ queryKey: ["quote-revs", id], queryFn: async () => (await api.get(`/quotes/${id}/revisions`)).data, enabled: !!id });

  const [form, setForm] = useState({});
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
    mutationFn: async (status) => (await api.post(`/quotes/${id}/status`, { status })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quote", id] });
      qc.invalidateQueries({ queryKey: ["audit-quote", id] });
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

  if (isLoading) return <div className="text-sm text-muted-foreground" data-testid="quote-loading">Loading quote…</div>;
  if (isError) return <div className="text-sm text-destructive" data-testid="quote-error">{extractError(error)}</div>;
  if (!q) return <div className="text-sm text-muted-foreground">Quote not found.</div>;

  const editable = !["converted", "void"].includes(q.status);
  const canWrite = hasPerm("quote:write");
  const canConvert = hasPerm("quote:convert") && q.status !== "converted" && q.status !== "void" && q.status !== "declined";
  const edit = { ...q, ...form };

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
              {canConvert && (
                <ConvertToOrderDialog quote={q} onConverted={(d) => navigate(`/orders/${d.order.id}`)} />
              )}
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
                  <Label>Job name</Label>
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

          <TabsContent value="activity"><AuditTimeline events={audit?.items || []} /></TabsContent>
        </Tabs>

        <aside className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Status</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2"><StatusPill kind="quote" value={q.status} /></div>
              {editable && canWrite && (
                <div className="grid grid-cols-2 gap-2">
                  {["draft", "sent", "approved", "declined", "void"].filter((s) => s !== q.status).map((s) => (
                    <Button key={s} size="sm" variant="outline" onClick={() => setStatus.mutate(s)} disabled={setStatus.isPending} data-testid={`quote-set-status-${s}`}>
                      <span className="capitalize">{s}</span>
                    </Button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
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
