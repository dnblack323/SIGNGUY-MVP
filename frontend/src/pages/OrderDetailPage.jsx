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
import { toast } from "sonner";
import StatusPill from "@/components/common/StatusPill";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { centsToDollarsString } from "@/lib/format";
import { ArrowLeft, Plus, Pencil, Trash2, Wrench, Receipt, Zap, RefreshCw } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import LineItemDialog from "@/components/commerce/LineItemDialog";
import GenerateWorkOrderDialog, { RegenerateDialog } from "@/components/work-orders/GenerateWorkOrderDialog";

function ItemsPanel({ orderId, items, totals, canWrite, orderStatus }) {
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [addMode, setAddMode] = useState("detailed");
  const [editing, setEditing] = useState(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["order", orderId] });
    qc.invalidateQueries({ queryKey: ["audit-order", orderId] });
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
              <div className="text-sm font-medium text-right">Total</div>
              <div className="text-right tabular-nums font-semibold" data-testid="order-derived-total">
                {centsToDollarsString(totals.total_cents ?? 0)}
              </div>
            </div>
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
      />
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
  const { data: audit } = useQuery({ queryKey: ["audit-order", id], queryFn: async () => (await api.get(`/audit`, { params: { entity_type: "order", entity_id: id } })).data, enabled: !!id });
  const { data: customer } = useQuery({ queryKey: ["customer", data?.order?.customer_id], queryFn: async () => (await api.get(`/customers/${data.order.customer_id}`)).data, enabled: !!data?.order?.customer_id });
  const { data: sourceQuote } = useQuery({
    queryKey: ["quote", data?.order?.source_quote_id || data?.order?.quote_id],
    queryFn: async () => (await api.get(`/quotes/${data.order.source_quote_id || data.order.quote_id}`)).data,
    enabled: !!(data?.order?.source_quote_id || data?.order?.quote_id),
  });

  const [form, setForm] = useState({});
  const [genWOOpen, setGenWOOpen] = useState(false);
  const [regenWOOpen, setRegenWOOpen] = useState(false);

  const order = data?.order;
  const items = data?.items || [];
  const totals = data?.totals || {};

  const { data: workOrders } = useQuery({
    queryKey: ["order-work-orders", id],
    queryFn: async () => (await api.get(`/work-orders`, { params: { order_id: id, current_only: true, limit: 5 } })).data,
    enabled: !!id,
  });
  const activeWO = (workOrders?.items || []).find((w) => w.current_version !== false && !["cancelled", "superseded"].includes(w.production_status));

  const patch = useMutation({
    mutationFn: async (payload) => (await api.patch(`/orders/${id}`, payload)).data,
    onSuccess: () => { toast.success("Saved"); qc.invalidateQueries({ queryKey: ["order", id] }); qc.invalidateQueries({ queryKey: ["audit-order", id] }); setForm({}); },
    onError: (e) => toast.error(extractError(e)),
  });
  const setStatus = useMutation({
    mutationFn: async (status) => (await api.post(`/orders/${id}/status`, { status })).data,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["order", id] }); qc.invalidateQueries({ queryKey: ["audit-order", id] }); },
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
                <Button variant="outline" size="sm" onClick={() => setGenWOOpen(true)} disabled={items.length === 0} data-testid="order-create-workorder-button">
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
        <Tabs defaultValue="items" data-testid="detail-tabs">
          <TabsList>
            <TabsTrigger value="items" data-testid="detail-tab-items">Items</TabsTrigger>
            <TabsTrigger value="details" data-testid="detail-tab-details">Details</TabsTrigger>
            <TabsTrigger value="activity" data-testid="detail-tab-activity">Activity</TabsTrigger>
          </TabsList>
          <TabsContent value="items">
            <ItemsPanel orderId={id} items={items} totals={totals} canWrite={canWrite} orderStatus={order.status} />
          </TabsContent>
          <TabsContent value="details" className="space-y-4">
            <Card>
              <CardHeader><CardTitle>Details</CardTitle></CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                <div className="grid gap-1.5"><Label>Job name</Label><Input value={edit.job_name || ""} disabled={!canWrite} onChange={(e) => setForm((f) => ({ ...f, job_name: e.target.value }))} data-testid="order-job-name" /></div>
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
          <TabsContent value="activity"><AuditTimeline events={audit?.items || []} /></TabsContent>
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
          <Card>
            <CardHeader><CardTitle className="text-base">Totals</CardTitle></CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Items</span><span className="tabular-nums">{items.length}</span></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Subtotal</span><span className="tabular-nums">{centsToDollarsString(totals.subtotal_cents ?? 0)}</span></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Discount</span><span className="tabular-nums">{centsToDollarsString(totals.discount_cents ?? 0)}</span></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Tax</span><span className="tabular-nums">{centsToDollarsString(totals.tax_cents ?? 0)}</span></div>
              <div className="flex items-center justify-between border-t pt-1"><span className="font-medium">Total</span><span className="tabular-nums font-semibold">{centsToDollarsString(totals.total_cents ?? 0)}</span></div>
            </CardContent>
          </Card>
        </aside>
      </div>

      <GenerateWorkOrderDialog
        orderId={id}
        open={genWOOpen}
        onOpenChange={setGenWOOpen}
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
