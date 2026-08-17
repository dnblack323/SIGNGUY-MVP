import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import StatusPill from "@/components/common/StatusPill";
import ProductionTimeline from "@/components/production/ProductionTimeline";
import { centsToDollarsString } from "@/lib/format";
import { buildApprovalCenterUrl } from "@/lib/approvalCenter";
import { buildShopScheduleUrl } from "@/lib/shopScheduleLinks";
import { ArrowLeft, CalendarDays, Plus, Pencil, Trash2, Wrench, Receipt, Zap, RefreshCw, ClipboardCheck, AlertTriangle, CheckCircle2, FileText, Link as LinkIcon, Lock, CreditCard, History, Truck } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import LineItemDialog from "@/components/commerce/LineItemDialog";
import DigitalPrintMinimumAdjustmentRow, { digitalPrintMinimumAdjustmentCents } from "@/components/commerce/DigitalPrintMinimumAdjustmentRow";
import GenerateWorkOrderDialog, { RegenerateDialog } from "@/components/work-orders/GenerateWorkOrderDialog";
import ProofsPanel from "@/components/proofs/ProofsPanel";
import TaskHandoffButton from "@/components/tasks/TaskHandoffButton";
import AIContextualActions from "@/components/ai/AIContextualActions";
import ApprovalHistoryPanel from "@/components/approvals/ApprovalHistoryPanel";
import DecisionRoomSharePanel from "@/components/approvals/DecisionRoomSharePanel";
import { useWorkspaceDirty } from "@/context/WorkspaceContext";

function ItemsPanel({ orderId, items, totals, pricingSummary, canWrite, orderStatus }) {
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [addMode, setAddMode] = useState("detailed");
  const [editing, setEditing] = useState(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["order", orderId] });
    qc.invalidateQueries({ queryKey: ["production-timeline"] });
  };

  async function addItem(payload) {
    await api.post(`/orders/${orderId}/items`, payload);
    toast.success("Item added");
    invalidate();
  }
  async function updateItem(itemId, payload) {
    await api.patch(`/orders/${orderId}/items/${itemId}`, payload);
    toast.success("Item updated");
    invalidate();
  }
  async function deleteItem(itemId) {
    await api.delete(`/orders/${orderId}/items/${itemId}`);
    toast.success("Item removed");
    invalidate();
  }

  const disabled = !canWrite || ["archived", "cancelled", "completed"].includes(orderStatus);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Order items ({items.length})</CardTitle>
        {!disabled && (
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => { setAddMode("quick"); setAddOpen(true); }} data-testid="order-item-quick-add">
              <Zap className="size-4 mr-1" /> Quick add
            </Button>
            <Button size="sm" onClick={() => { setAddMode("detailed"); setAddOpen(true); }} data-testid="order-item-detailed-add">
              <Plus className="size-4 mr-1" /> Add item
            </Button>
          </div>
        )}
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-sm text-muted-foreground" data-testid="order-items-empty">
            No items yet. Add items — server totals derive from these.
          </div>
        ) : (
          <div>
            <div className="grid grid-cols-[1fr_100px_80px_120px_120px_80px] gap-2 px-2 py-1 text-xs text-muted-foreground font-medium">
              <div>Description</div><div>Production</div><div className="text-right">Qty</div>
              <div className="text-right">Unit</div><div className="text-right">Line total</div><div />
            </div>
            {items.map((it) => (
              <div key={it.id} className="grid grid-cols-[1fr_100px_80px_120px_120px_80px] gap-2 items-center px-2 py-1 border-t text-sm" data-testid={`order-item-row-${it.id}`}>
                <div>
                  <div className="font-medium">{it.description}</div>
                  <div className="text-xs text-muted-foreground">
                    {it.category || "—"}{it.width_inches && it.height_inches ? ` · ${it.width_inches}×${it.height_inches}in` : ""}
                    {it.manual_override_reason ? ` · override: ${it.manual_override_reason}` : ""}
                  </div>
                </div>
                <div>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${it.production_required ? "bg-emerald-100 text-emerald-700" : "bg-muted text-muted-foreground"}`} data-testid={`order-item-prodreq-${it.id}`}>
                    {it.production_required ? "yes" : "no"}
                  </span>
                </div>
                <div className="text-right tabular-nums">{it.quantity}</div>
                <div className="text-right tabular-nums">{centsToDollarsString(it.unit_price_cents)}</div>
                <div className="text-right tabular-nums font-medium">{centsToDollarsString(it.line_total_cents)}</div>
                <div className="flex items-center gap-1 justify-end">
                  {!disabled && (
                    <>
                      <Button variant="ghost" size="icon" onClick={() => setEditing(it)} aria-label="Edit" data-testid={`order-item-edit-${it.id}`}>
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => deleteItem(it.id)} aria-label="Remove" data-testid={`order-item-delete-${it.id}`}>
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
              <div className="text-right tabular-nums font-semibold" data-testid="order-derived-total">
                {centsToDollarsString(totals.total_cents ?? 0)}
              </div>
            </div>
            {pricingSummary?.item_count > 0 && (
              <div className="grid grid-cols-[1fr_120px] gap-2 pt-2 border-t items-baseline" data-testid="order-pricing-summary">
                <div className="text-xs text-muted-foreground text-right">Est. production cost</div>
                <div className="text-right tabular-nums text-xs">{centsToDollarsString(pricingSummary.total_estimated_cost_cents ?? 0)}</div>
                <div className="text-xs text-muted-foreground text-right">Est. profit / margin</div>
                <div className="text-right tabular-nums text-xs">
                  {centsToDollarsString(pricingSummary.estimated_total_profit_cents ?? 0)} ({pricingSummary.estimated_margin_percent ?? 0}%)
                </div>
                {pricingSummary.items_with_warnings_count > 0 && (
                  <>
                    <div className="text-xs text-amber-700 text-right">Warnings to review</div>
                    <div className="text-right tabular-nums text-xs text-amber-700" data-testid="order-pricing-warnings-count">{pricingSummary.items_with_warnings_count}</div>
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
        entryMode={addMode}
        entityLabel="Order"
        allowProductionRequired
        onSubmit={addItem}
      />
      <LineItemDialog
        open={!!editing}
        onOpenChange={(v) => !v && setEditing(null)}
        mode="edit"
        entryMode="detailed"
        initial={editing}
        entityLabel="Order"
        allowProductionRequired
        onSubmit={(payload) => updateItem(editing.id, payload)}
        onRecalculatePreview={editing ? async (categoryInputs) => (
          await api.post(`/orders/${orderId}/items/${editing.id}/recalculate-preview`, { category_inputs: categoryInputs })
        ).data : undefined}
      />
    </Card>
  );
}

function isWrapOrderItem(item) {
  return [item?.category, item?.product_type, item?.description, item?.item_name, item?.material_key].join(" ").toLowerCase().includes("wrap")
    || item?.category === "vehicle_graphics";
}

function ReadinessPanel({ readiness, onHandoff, disabled }) {
  const blockers = readiness?.blockers || [];
  const warnings = readiness?.warnings || [];
  return (
    <Card data-testid="order-readiness-panel">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base flex items-center gap-2">
          {readiness?.ready ? <CheckCircle2 className="size-4 text-emerald-600" /> : <AlertTriangle className="size-4 text-amber-600" />}
          Production readiness
        </CardTitle>
        <Badge variant={readiness?.ready ? "default" : "outline"} data-testid="order-readiness-status">
          {readiness?.ready ? "Ready" : "Not ready"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="rounded border p-2"><div className="text-muted-foreground">Items</div><div className="font-medium">{readiness?.summary?.item_count ?? 0}</div></div>
          <div className="rounded border p-2"><div className="text-muted-foreground">Production</div><div className="font-medium">{readiness?.summary?.production_required_count ?? 0}</div></div>
          <div className="rounded border p-2"><div className="text-muted-foreground">Approvals</div><div className="font-medium">{readiness?.summary?.approval_count ?? 0}</div></div>
        </div>
        {blockers.length === 0 ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-emerald-900" data-testid="order-readiness-clear">
            No production blockers found by the server readiness check.
          </div>
        ) : (
          <div className="space-y-2" data-testid="order-readiness-blockers">
            {blockers.map((blocker, index) => (
              <div key={`${blocker.code}-${index}`} className="rounded-md border p-3">
                <div className="font-medium">{blocker.label}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  Source: {blocker.source}{blocker.source_id ? ` ${blocker.source_id}` : ""} · Owner: {blocker.owner}
                </div>
                <div className="text-xs mt-1">Next action: {blocker.required_action}</div>
              </div>
            ))}
          </div>
        )}
        {warnings.length > 0 && (
          <div className="space-y-1" data-testid="order-readiness-warnings">
            {warnings.map((warning, index) => (
              <div key={`${warning.code}-${index}`} className="text-xs text-amber-700">{warning.label}</div>
            ))}
          </div>
        )}
        <Button size="sm" className="w-full" onClick={onHandoff} disabled={disabled} data-testid="order-readiness-handoff-button">
          <Wrench className="size-4 mr-1" />Production handoff
        </Button>
      </CardContent>
    </Card>
  );
}

function FinancialPanel({ financial, canSeeFinancials, onCreateInvoice, invoicePending }) {
  if (!canSeeFinancials || financial?.restricted) {
    return (
      <Card data-testid="order-financial-restricted">
        <CardHeader><CardTitle className="text-base flex items-center gap-2"><Lock className="size-4" />Financial status</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Financial details are restricted by role. Production-only users can still see readiness blockers without invoice totals.
        </CardContent>
      </Card>
    );
  }
  const invoices = financial?.invoices || [];
  return (
    <Card data-testid="order-financial-summary">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base flex items-center gap-2"><CreditCard className="size-4" />Invoice and deposit status</CardTitle>
        <Button size="sm" onClick={onCreateInvoice} disabled={invoicePending} data-testid="order-financial-create-invoice">
          <Receipt className="size-4 mr-1" />Create/open invoice
        </Button>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded border p-2"><div className="text-muted-foreground text-xs">Invoiced</div><div className="font-medium">{centsToDollarsString(financial?.total_invoiced_cents ?? 0)}</div></div>
          <div className="rounded border p-2"><div className="text-muted-foreground text-xs">Paid</div><div className="font-medium">{centsToDollarsString(financial?.amount_paid_cents ?? 0)}</div></div>
          <div className="rounded border p-2"><div className="text-muted-foreground text-xs">Remaining</div><div className="font-medium">{centsToDollarsString(financial?.balance_due_cents ?? 0)}</div></div>
        </div>
        {invoices.length === 0 ? (
          <div className="text-muted-foreground">No invoice has been created for this Order.</div>
        ) : invoices.map((invoice) => (
          <div key={invoice.id} className="rounded-md border p-3 flex items-center justify-between gap-3" data-testid={`order-invoice-row-${invoice.id}`}>
            <div>
              <div className="font-medium">I-{invoice.number} · {invoice.title}</div>
              <div className="text-xs text-muted-foreground">{invoice.document_status || "draft"} · {invoice.financial_status || invoice.status || "unpaid"}</div>
            </div>
            <Button asChild variant="outline" size="sm"><Link to={`/invoices/${invoice.id}`}>Open</Link></Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function LinkedAssetsPanel({ linkedAssets }) {
  const files = linkedAssets?.files || [];
  const documents = linkedAssets?.documents || [];
  const attachments = linkedAssets?.attachments || [];
  return (
    <Card data-testid="order-linked-assets">
      <CardHeader><CardTitle className="text-base flex items-center gap-2"><FileText className="size-4" />Files, artwork, and documents</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="rounded border p-2"><div className="text-muted-foreground">Files</div><div className="font-medium">{files.length}</div></div>
          <div className="rounded border p-2"><div className="text-muted-foreground">Documents</div><div className="font-medium">{documents.length}</div></div>
          <div className="rounded border p-2"><div className="text-muted-foreground">Attachments</div><div className="font-medium">{attachments.length}</div></div>
        </div>
        {[...files, ...documents].length === 0 ? (
          <div className="text-muted-foreground">No linked files or Library documents found for this Order or its Items.</div>
        ) : (
          <div className="space-y-2">
            {files.map((file) => <div key={file.id} className="rounded border p-2" data-testid={`order-file-row-${file.id}`}>{file.filename || file.name || file.id}</div>)}
            {documents.map((doc) => <div key={doc.id} className="rounded border p-2" data-testid={`order-document-row-${doc.id}`}>{doc.title || doc.name || doc.id}</div>)}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ApprovalDecisionSummary({ approvals, rooms, proofs }) {
  return (
    <Card data-testid="order-approval-decision-summary">
      <CardHeader><CardTitle className="text-base flex items-center gap-2"><ClipboardCheck className="size-4" />Approvals and customer decisions</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="rounded border p-2"><div className="text-muted-foreground">Approvals</div><div className="font-medium">{(approvals || []).length}</div></div>
          <div className="rounded border p-2"><div className="text-muted-foreground">Decision Rooms</div><div className="font-medium">{(rooms || []).length}</div></div>
          <div className="rounded border p-2"><div className="text-muted-foreground">Proofs</div><div className="font-medium">{(proofs || []).length}</div></div>
        </div>
        {(rooms || []).length === 0 ? (
          <div className="text-muted-foreground">No linked Decision Rooms yet.</div>
        ) : rooms.map((room) => (
          <div key={room.id} className="rounded border p-2 flex items-center justify-between gap-3" data-testid={`order-decision-room-row-${room.id}`}>
            <div><div className="font-medium">{room.title || "Decision Room"}</div><div className="text-xs text-muted-foreground">{room.status}</div></div>
            <Button asChild size="sm" variant="outline"><Link to={`/decision-rooms/${room.id}`}><LinkIcon className="size-3 mr-1" />Open</Link></Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function OrderLifecycleTimeline({ order, readiness, financial, approvals, rooms, proofs, workOrders }) {
  const events = [];
  const add = (at, label, source) => { if (at) events.push({ at, label, source }); };
  add(order.created_at, `Order O-${order.number} created`, "Order");
  add(order.updated_at, "Order updated", "Order");
  add(order.archived_at, "Order archived", "Order");
  (financial?.invoices || []).forEach((invoice) => add(invoice.created_at, `Invoice I-${invoice.number} created`, "Invoice"));
  (financial?.payments || []).forEach((payment) => add(payment.created_at, `Payment ${centsToDollarsString(payment.amount_cents || 0)} recorded`, "Payment"));
  (approvals || []).forEach((approval) => add(approval.created_at, `Approval ${approval.action}`, "Approval"));
  (rooms || []).forEach((room) => add(room.updated_at || room.created_at, `Decision Room ${room.status}`, "Decision Room"));
  (proofs || []).forEach((proof) => add(proof.updated_at || proof.created_at, `Proof ${proof.status}`, "Proof"));
  (workOrders || []).forEach((wo) => add(wo.created_at, `Work Order W-${wo.number} created`, "Work Order"));
  add(readiness?.evaluated_at, `Readiness ${readiness?.ready ? "passed" : "blocked"}`, "Readiness");
  events.sort((a, b) => String(a.at).localeCompare(String(b.at)));
  return (
    <Card data-testid="order-lifecycle-timeline">
      <CardHeader><CardTitle className="text-base flex items-center gap-2"><History className="size-4" />Order lifecycle timeline</CardTitle></CardHeader>
      <CardContent>
        {events.length === 0 ? <div className="text-sm text-muted-foreground">No lifecycle events yet.</div> : (
          <ul className="divide-y text-sm">
            {events.map((event, index) => (
              <li key={`${event.source}-${event.at}-${index}`} className="py-2" data-testid="order-lifecycle-event">
                <div className="font-medium">{event.label}</div>
                <div className="text-xs text-muted-foreground">{event.source} · {String(event.at).slice(0, 16)}</div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default function OrderDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("order:write");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["order", id],
    queryFn: async () => (await api.get(`/orders/${id}`)).data,
  });
  const { data: customer } = useQuery({ queryKey: ["customer", data?.order?.customer_id], queryFn: async () => (await api.get(`/customers/${data.order.customer_id}`)).data, enabled: !!data?.order?.customer_id });
  const { data: sourceQuote } = useQuery({
    queryKey: ["quote", data?.order?.source_quote_id || data?.order?.quote_id],
    queryFn: async () => (await api.get(`/quotes/${data.order.source_quote_id || data.order.quote_id}`)).data,
    enabled: !!(data?.order?.source_quote_id || data?.order?.quote_id),
  });
  const { data: orderRooms } = useQuery({
    queryKey: ["order-decision-rooms", id],
    queryFn: async () => (await api.get("/decision-rooms", { params: { order_id: id } })).data,
    enabled: !!id && hasPerm("decision_room:read"),
  });

  const [form, setForm] = useState({});
  useWorkspaceDirty(Object.keys(form).length > 0);
  const [genWOOpen, setGenWOOpen] = useState(false);
  const [regenWOOpen, setRegenWOOpen] = useState(false);

  const order = data?.order;
  const items = data?.items || [];
  const wrapOrderItem = items.find(isWrapOrderItem);
  const totals = data?.totals || {};
  const digitalPrintAdjustmentCents = digitalPrintMinimumAdjustmentCents(totals);
  const pricingSummary = data?.pricing_summary || {};
  const readiness = data?.readiness;
  const financialSummary = data?.financial_summary || {};
  const linkedAssets = data?.linked_assets || {};
  const approvals = data?.approvals || [];
  const decisionRooms = data?.decision_rooms || orderRooms?.items || [];
  const proofs = data?.proofs || [];
  const canSeeFinancials = data?.permissions?.financials_visible ?? (hasPerm("invoice:read") || hasPerm("payment:read"));

  const { data: workOrders } = useQuery({
    queryKey: ["order-work-orders", id],
    queryFn: async () => (await api.get(`/work-orders`, { params: { order_id: id, current_only: true, limit: 5 } })).data,
    enabled: !!id,
  });
  const activeWO = (workOrders?.items || []).find((w) => w.current_version !== false && !["cancelled", "superseded"].includes(w.production_status));

  const patch = useMutation({
    mutationFn: async (payload) => (await api.patch(`/orders/${id}`, payload)).data,
    onSuccess: () => { toast.success("Saved"); qc.invalidateQueries({ queryKey: ["order", id] }); qc.invalidateQueries({ queryKey: ["production-timeline"] }); setForm({}); },
    onError: (e) => toast.error(extractError(e)),
  });
  const setStatus = useMutation({
    mutationFn: async (status) => (await api.post(`/orders/${id}/status`, { status })).data,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["order", id] }); qc.invalidateQueries({ queryKey: ["production-timeline"] }); },
    onError: (e) => toast.error(extractError(e)),
  });

  const createInvoice = useMutation({
    mutationFn: async () => (await api.post(`/invoices`, {
      order_id: id, title: order?.job_name || "Invoice",
      total_cents: totals.total_cents ?? 0,
    })).data,
    onSuccess: (res) => { toast.success(res.already_exists ? "Invoice already exists" : `Invoice I-${res.invoice.number} created`); navigate(`/invoices/${res.invoice.id}`); },
    onError: (e) => toast.error(extractError(e)),
  });

  if (isLoading) return <div className="text-sm text-muted-foreground" data-testid="order-loading">Loading order…</div>;
  if (isError) return <div className="text-sm text-destructive" data-testid="order-error">{extractError(error)}</div>;
  if (!order) return <div className="text-sm text-muted-foreground">Order not found.</div>;

  const edit = { ...order, ...form };
  const approvalRoom = (decisionRooms || []).find((room) => !["archived", "closed", "expired"].includes(room.status));

  return (
    <div className="space-y-4" data-testid="order-detail-page">
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="icon"><Link to="/orders"><ArrowLeft className="size-4" /></Link></Button>
        <PageHeader
          title={<span><span className="mono text-muted-foreground text-lg mr-2">O-{order.number}</span>{order.job_name}</span>}
          subtitle={
            <span>
              Customer: <Link className="link-underline" to={`/customers/${order.customer_id}`}>{customer?.name || "…"}</Link>
              {(order.source_quote_id || order.quote_id) && (
                <>
                  {" · from Quote "}
                  <Link className="link-underline" to={`/quotes/${order.source_quote_id || order.quote_id}`} data-testid="order-source-quote-link">
                    Q-{sourceQuote?.quote?.number || sourceQuote?.number || "…"}
                  </Link>
                  {order.source_quote_revision != null && (
                    <span className="text-muted-foreground" data-testid="order-source-quote-revision"> (rev #{order.source_quote_revision})</span>
                  )}
                </>
              )}
            </span>
          }
          actions={canWrite && (
            <div className="flex items-center gap-2 flex-wrap">
              <AIContextualActions contextType="order" contextId={id} actions={[
                { label: "Status Email", tool: "email_draft_assistant", mode: "job_update" },
                { label: "Marketing Post", tool: "social_post_builder", mode: "completed_work_showcase" },
              ]} />
              <TaskHandoffButton sourceType="order" sourceId={id} defaults={{ title: `Follow up on O-${order.number}`, task_type: "order_followup" }} />
              {hasPerm("schedule:manage") && (
                <Button asChild variant="outline" size="sm" data-testid="order-schedule-button">
                  <Link to={buildShopScheduleUrl({
                    create: true,
                    customerId: order.customer_id,
                    orderId: id,
                    workOrderId: activeWO?.id,
                    eventType: "installation",
                    title: `${order.job_name} appointment`,
                  })}>
                    <CalendarDays className="size-4 mr-1" />Schedule
                  </Link>
                </Button>
              )}
              {hasPerm("wrap_lab:read") && (
                <Button asChild variant="outline" size="sm" data-testid="order-open-wrap-lab-button">
                  <Link to={`/wrap-lab?order_id=${order.id}&customer_id=${order.customer_id}${wrapOrderItem?.id ? `&order_item_id=${wrapOrderItem.id}` : ""}`}>
                    <Truck className="size-4 mr-1" />Wrap Lab
                  </Link>
                </Button>
              )}
              {hasPerm("decision_room:read") && (
                <Button asChild variant="outline" size="sm" data-testid="order-approval-work-button">
                  <Link to={approvalRoom ? `/decision-rooms/${approvalRoom.id}` : buildApprovalCenterUrl({
                    create: true,
                    targetType: "order",
                    targetId: order.id,
                    customerId: order.customer_id,
                    title: `O-${order.number} ${order.job_name}`,
                  })}>
                    <ClipboardCheck className="size-4 mr-1" />
                    {approvalRoom ? "Open approval work" : "Approval work"}
                  </Link>
                </Button>
              )}
              {activeWO ? (
                <>
                  <Button asChild variant="outline" size="sm" data-testid="order-open-workorder-button">
                    <Link to={`/work-orders/${activeWO.id}`}>
                      <Wrench className="size-4 mr-1" />Work order W-{activeWO.number}
                    </Link>
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setRegenWOOpen(true)} data-testid="order-regenerate-workorder-button">
                    <RefreshCw className="size-4 mr-1" />Regenerate
                  </Button>
                </>
              ) : (
                <Button variant="outline" size="sm" onClick={() => setGenWOOpen(true)} disabled={items.length === 0 || !readiness} data-testid="order-create-workorder-button">
                  <Wrench className="size-4 mr-1" />Generate work order
                </Button>
              )}
              <Button size="sm" onClick={() => createInvoice.mutate()} disabled={createInvoice.isPending || items.length === 0} data-testid="order-create-invoice-button">
                <Receipt className="size-4 mr-1" />Create invoice
              </Button>
            </div>
          )}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        <Tabs defaultValue="overview" data-testid="detail-tabs">
          <TabsList>
            <TabsTrigger value="overview" data-testid="detail-tab-overview">Overview</TabsTrigger>
            <TabsTrigger value="items" data-testid="detail-tab-items">Order Items</TabsTrigger>
            <TabsTrigger value="production" data-testid="detail-tab-production">Production</TabsTrigger>
            <TabsTrigger value="documents-approvals" data-testid="detail-tab-documents-approvals">Documents & Approvals</TabsTrigger>
            <TabsTrigger value="files-artwork" data-testid="detail-tab-files-artwork">Files & Artwork</TabsTrigger>
            <TabsTrigger value="financial" data-testid="detail-tab-financial">Financial</TabsTrigger>
            <TabsTrigger value="activity" data-testid="detail-tab-activity">Activity</TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className="space-y-4">
            <ReadinessPanel readiness={readiness} onHandoff={() => setGenWOOpen(true)} disabled={!canWrite || items.length === 0} />
            <Card>
              <CardHeader><CardTitle>Overview</CardTitle></CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                <div className="text-sm"><span className="text-muted-foreground">Customer</span><div><Link className="link-underline" to={`/customers/${order.customer_id}`}>{customer?.name || "Loading..."}</Link></div></div>
                <div className="text-sm"><span className="text-muted-foreground">Status</span><div><StatusPill kind="order" value={order.status} /></div></div>
                <div className="text-sm"><span className="text-muted-foreground">Due date</span><div>{order.due_date || "Not set"}</div></div>
                <div className="text-sm"><span className="text-muted-foreground">Order Items</span><div>{items.length}</div></div>
                {digitalPrintAdjustmentCents != null && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Digital Print order minimum adjustment</span>
                    <div data-testid="digital-print-order-minimum-adjustment">{centsToDollarsString(digitalPrintAdjustmentCents)}</div>
                  </div>
                )}
                <div className="text-sm">
                  <span className="text-muted-foreground">Total</span>
                  <div data-testid="order-derived-total">{centsToDollarsString(totals.total_cents ?? 0)}</div>
                </div>
                <div className="md:col-span-2 text-sm"><span className="text-muted-foreground">Notes</span><div>{order.notes_customer || order.notes_internal || order.notes || "No notes."}</div></div>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="items">
            <ItemsPanel orderId={id} items={items} totals={totals} pricingSummary={pricingSummary} canWrite={canWrite} orderStatus={order.status} />
          </TabsContent>
          <TabsContent value="production" className="space-y-4">
            <ReadinessPanel readiness={readiness} onHandoff={() => setGenWOOpen(true)} disabled={!canWrite || items.length === 0} />
            <Card>
              <CardHeader><CardTitle>Production</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {activeWO ? (
                  <Button asChild variant="outline" size="sm" data-testid="order-production-workorder-link">
                    <Link to={`/work-orders/${activeWO.id}`}>Open Work Order Summary W-{activeWO.number}</Link>
                  </Button>
                ) : (
                  <div className="text-sm text-muted-foreground">No current Work Order Summary has been generated for this order.</div>
                )}
                <ProductionTimeline scope="order" orderId={id} />
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="documents-approvals" className="space-y-4">
            <ApprovalDecisionSummary approvals={approvals} rooms={decisionRooms} proofs={proofs} />
            <ProofsPanel orderId={id} customerId={order?.customer_id} />
            {hasPerm("decision_room:read") && (
              <>
                <ApprovalHistoryPanel sourceType="order" sourceId={order.id} />
                {approvalRoom && <DecisionRoomSharePanel roomId={approvalRoom.id} />}
              </>
            )}
          </TabsContent>
          <TabsContent value="files-artwork" className="space-y-4">
            <LinkedAssetsPanel linkedAssets={linkedAssets} />
          </TabsContent>
          <TabsContent value="financial" className="space-y-4">
            <FinancialPanel
              financial={financialSummary}
              canSeeFinancials={canSeeFinancials}
              onCreateInvoice={() => createInvoice.mutate()}
              invoicePending={createInvoice.isPending}
            />
            <Card>
              <CardHeader><CardTitle>Financial</CardTitle></CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                <div className="grid gap-1.5"><Label>Project name</Label><Input value={edit.job_name || ""} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, job_name: e.target.value }))} data-testid="order-job-name" /></div>
                <div className="grid gap-1.5"><Label>Due date</Label><Input type="date" value={(edit.due_date || "").slice(0, 10)} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value || null }))} data-testid="order-due-date" /></div>
                <div className="md:col-span-2 grid gap-1.5"><Label>Customer notes</Label><Textarea rows={3} value={edit.notes_customer || ""} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, notes_customer: e.target.value }))} data-testid="order-notes-customer" /></div>
                <div className="md:col-span-2 grid gap-1.5"><Label>Internal notes</Label><Textarea rows={3} value={edit.notes_internal || edit.notes || ""} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, notes_internal: e.target.value }))} data-testid="order-notes-internal" /></div>
                {canWrite && Object.keys(form).length > 0 && (
                  <div className="md:col-span-2">
                    <Button onClick={() => patch.mutate(form)} disabled={patch.isPending} data-testid="order-save-button">Save</Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="activity" className="space-y-4">
            <OrderLifecycleTimeline order={order} readiness={readiness} financial={financialSummary} approvals={approvals} rooms={decisionRooms} proofs={proofs} workOrders={workOrders?.items || data?.work_orders || []} />
            <ProductionTimeline scope="order" orderId={id} />
          </TabsContent>
        </Tabs>

        <aside className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Status</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <StatusPill kind="order" value={order.status} />
              {canWrite && (
                <div className="grid grid-cols-2 gap-2">
                  {["draft", "confirmed", "in_production", "ready", "completed", "cancelled"].filter((s) => s !== order.status).map((s) => (
                    <Button key={s} size="sm" variant="outline" onClick={() => setStatus.mutate(s)} disabled={setStatus.isPending} data-testid={`order-set-status-${s}`}>
                      <span className="capitalize">{s.replace("_", " ")}</span>
                    </Button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          <ReadinessPanel readiness={readiness} onHandoff={() => setGenWOOpen(true)} disabled={!canWrite || items.length === 0} />
          <Card>
            <CardHeader><CardTitle className="text-base">Totals</CardTitle></CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Items</span><span className="tabular-nums">{items.length}</span></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Subtotal</span><span className="tabular-nums">{centsToDollarsString(totals.subtotal_cents ?? 0)}</span></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Discount</span><span className="tabular-nums">{centsToDollarsString(totals.discount_cents ?? 0)}</span></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Tax</span><span className="tabular-nums">{centsToDollarsString(totals.tax_cents ?? 0)}</span></div>
              {digitalPrintAdjustmentCents != null && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Digital Print order minimum adjustment</span>
                  <span className="tabular-nums" data-testid="order-summary-digital-print-order-minimum-adjustment">{centsToDollarsString(digitalPrintAdjustmentCents)}</span>
                </div>
              )}
              <div className="flex items-center justify-between border-t pt-1"><span className="font-medium">Total</span><span className="tabular-nums font-semibold">{centsToDollarsString(totals.total_cents ?? 0)}</span></div>
              {pricingSummary?.item_count > 0 && (
                <div className="border-t pt-1 space-y-1" data-testid="order-summary-pricing-block">
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Est. production cost</span><span className="tabular-nums">{centsToDollarsString(pricingSummary.total_estimated_cost_cents ?? 0)}</span></div>
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Manual-price items total</span><span className="tabular-nums">{centsToDollarsString(pricingSummary.total_manual_price_amount_cents ?? 0)}</span></div>
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Suggested-price items total</span><span className="tabular-nums">{centsToDollarsString(pricingSummary.total_suggested_price_amount_cents ?? 0)}</span></div>
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Est. profit</span><span className="tabular-nums">{centsToDollarsString(pricingSummary.estimated_total_profit_cents ?? 0)}</span></div>
                  <div className="flex items-center justify-between"><span className="text-muted-foreground">Est. margin</span><span className="tabular-nums">{pricingSummary.estimated_margin_percent ?? 0}%</span></div>
                  {pricingSummary.items_with_warnings_count > 0 && (
                    <div className="flex items-center justify-between text-amber-700" data-testid="order-summary-warnings-count">
                      <span>Items needing review</span><span className="tabular-nums font-medium">{pricingSummary.items_with_warnings_count}</span>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>

      <GenerateWorkOrderDialog
        orderId={id}
        open={genWOOpen}
        onOpenChange={setGenWOOpen}
        useHandoff
        readiness={readiness}
        onCreated={(wo) => { qc.invalidateQueries({ queryKey: ["order-work-orders", id] }); if (!wo.already_exists) navigate(`/work-orders/${wo.id}`); }}
      />
      {activeWO && (
        <RegenerateDialog
          workOrderId={activeWO.id}
          open={regenWOOpen}
          onOpenChange={setRegenWOOpen}
          onDone={(wo) => { qc.invalidateQueries({ queryKey: ["order-work-orders", id] }); navigate(`/work-orders/${wo.id}`); }}
        />
      )}
    </div>
  );
}
