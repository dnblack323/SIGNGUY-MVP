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
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import StatusPill from "@/components/common/StatusPill";
import MoneyInput from "@/components/forms/MoneyInput";
import { centsToDollarsString } from "@/lib/format";
import { ArrowLeft, ArrowRightCircle, Save, Mail } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import ComposeEmailDialog from "@/components/email/ComposeEmailDialog";

export default function QuoteDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { hasPerm } = useAuth();

  const { data: qResp } = useQuery({ queryKey: ["quote", id], queryFn: async () => (await api.get(`/quotes/${id}`)).data });
  const q = qResp?.quote || qResp; // backwards compat
  const lineItems = qResp?.line_items || [];
  const totals = qResp?.totals || {};
  const { data: audit } = useQuery({ queryKey: ["audit-quote", id], queryFn: async () => (await api.get(`/audit`, { params: { entity_type: "quote", entity_id: id } })).data, enabled: !!id });
  const { data: customer } = useQuery({ queryKey: ["customer", q?.customer_id], queryFn: async () => (await api.get(`/customers/${q.customer_id}`)).data, enabled: !!q?.customer_id });
  const { data: revs } = useQuery({ queryKey: ["quote-revs", id], queryFn: async () => (await api.get(`/quotes/${id}/revisions`)).data, enabled: !!id });

  const [form, setForm] = useState({});
  const edit = { ...q, ...form };

  const save = useMutation({
    mutationFn: async (payload) => (await api.patch(`/quotes/${id}`, payload)).data,
    onSuccess: () => { toast.success("Saved"); qc.invalidateQueries({ queryKey: ["quote", id] }); setForm({}); qc.invalidateQueries({ queryKey: ["audit-quote", id] }); },
    onError: (e) => toast.error(extractError(e)),
  });

  const setStatus = useMutation({
    mutationFn: async (status) => (await api.post(`/quotes/${id}/status`, { status })).data,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["quote", id] }); qc.invalidateQueries({ queryKey: ["audit-quote", id] }); },
    onError: (e) => toast.error(extractError(e)),
  });

  const convert = useMutation({
    mutationFn: async () => (await api.post(`/quotes/${id}/convert-to-order`)).data,
    onSuccess: (data) => {
      toast.success(data.already_converted ? `Already converted to O-${data.order.number}` : `Converted to O-${data.order.number}`);
      qc.invalidateQueries({ queryKey: ["quote", id] });
      navigate(`/orders/${data.order.id}`);
    },
    onError: (e) => toast.error(extractError(e)),
  });

  if (!q) return <div className="text-sm text-muted-foreground">Loading…</div>;
  const editable = q.status !== "converted";

  return (
    <div className="space-y-4" data-testid="quote-detail-page">
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="icon"><Link to="/quotes"><ArrowLeft className="size-4" /></Link></Button>
        <PageHeader
          title={<span><span className="mono text-muted-foreground text-lg mr-2">Q-{q.number}</span>{q.job_name}</span>}
          subtitle={<span>Customer: <Link className="link-underline" to={`/customers/${q.customer_id}`}>{customer?.name || "…"}</Link></span>}
          actions={(
            <div className="flex items-center gap-2">
              {hasPerm("email:send") && customer?.email && (
                <ComposeEmailDialog
                  defaultTemplate="quote_sent"
                  toEmail={customer.email}
                  customerId={customer.id}
                  relatedType="quote"
                  relatedId={q.id}
                  suggestedSubject={`Quote Q-${q.number} — ${q.job_name}`}
                  suggestedBody={`Hi ${customer.name},\n\nHere’s your quote for ${q.job_name}.\nTotal: ${centsToDollarsString(q.total_cents)}\n\nLet us know if you have any questions.`}
                  trigger={<Button variant="outline" size="sm" data-testid="quote-email-button"><Mail className="size-4 mr-1" />Email quote</Button>}
                />
              )}
              {hasPerm("quote:convert") && q.status !== "converted" && (
                <Button size="sm" onClick={() => convert.mutate()} disabled={convert.isPending} data-testid="quote-convert-button">
                  <ArrowRightCircle className="size-4 mr-1" /> {convert.isPending ? "Converting…" : "Convert to order"}
                </Button>
              )}
              {q.status === "converted" && q.converted_order_id && (
                <Button asChild size="sm" variant="outline"><Link to={`/orders/${q.converted_order_id}`}>Open order</Link></Button>
              )}
            </div>
          )}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        <Tabs defaultValue="details" data-testid="detail-tabs">
          <TabsList>
            <TabsTrigger value="details" data-testid="detail-tab-details">Details</TabsTrigger>
            <TabsTrigger value="line-items" data-testid="detail-tab-line-items">Line items ({lineItems.length})</TabsTrigger>
            <TabsTrigger value="revisions" data-testid="detail-tab-revisions">Revisions ({revs?.items?.length || 0})</TabsTrigger>
            <TabsTrigger value="activity" data-testid="detail-tab-activity">Activity</TabsTrigger>
          </TabsList>
          <TabsContent value="details" className="space-y-4">
            <Card>
              <CardHeader><CardTitle>Quote</CardTitle></CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                <div className="grid gap-1.5"><Label>Job name</Label><Input value={edit.job_name || ""} disabled={!editable} onChange={(e) => setForm((f) => ({ ...f, job_name: e.target.value }))} data-testid="quote-detail-job-name-input" /></div>
                <div className="grid gap-1.5"><Label>Total</Label><MoneyInput disabled={!editable} value={edit.total_cents} onChange={(v) => setForm((f) => ({ ...f, total_cents: v }))} testId="quote-detail-total-input" /></div>
                <div className="md:col-span-2 grid gap-1.5"><Label>Notes</Label><Textarea disabled={!editable} rows={4} value={edit.notes || ""} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} data-testid="quote-detail-notes-input" /></div>
                {editable && hasPerm("quote:write") && Object.keys(form).length > 0 && (
                  <div className="md:col-span-2"><Button onClick={() => save.mutate(form)} disabled={save.isPending} data-testid="quote-save-button"><Save className="size-4 mr-1" />Save</Button></div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="line-items" className="space-y-2" data-testid="quote-line-items-tab">
            <Card>
              <CardHeader><CardTitle className="text-base">Line items</CardTitle></CardHeader>
              <CardContent>
                {lineItems.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No line items yet. Backend totals derive from these.</div>
                ) : (
                  <div className="space-y-2">
                    {lineItems.map((li) => (
                      <div key={li.id} className="flex items-center justify-between border-b py-1 text-sm" data-testid={`line-item-row-${li.id}`}>
                        <div>
                          <div className="font-medium">{li.description}</div>
                          <div className="text-xs text-muted-foreground">
                            {li.category || "—"} · qty {li.quantity} · unit {centsToDollarsString(li.unit_price_cents)}
                          </div>
                        </div>
                        <div className="tabular-nums font-medium">{centsToDollarsString(li.line_total_cents)}</div>
                      </div>
                    ))}
                    <div className="flex items-center justify-between pt-2 border-t">
                      <div className="text-sm text-muted-foreground">Total</div>
                      <div className="tabular-nums font-semibold" data-testid="quote-derived-total">
                        {centsToDollarsString(totals.total_cents ?? q.total_cents ?? 0)}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="revisions" className="space-y-2" data-testid="quote-revisions-tab">
            <Card>
              <CardHeader><CardTitle className="text-base">Revision history</CardTitle></CardHeader>
              <CardContent>
                <div className="text-xs text-muted-foreground mb-2">Current revision: <span className="font-medium">{revs?.current_revision || 1}</span></div>
                {(revs?.items || []).length === 0 ? (
                  <div className="text-sm text-muted-foreground">No prior revisions. Editing a sent quote creates one automatically.</div>
                ) : (
                  <div className="space-y-2">
                    {(revs?.items || []).map((r) => (
                      <div key={r.id} className="flex items-center justify-between border-b py-1 text-sm" data-testid={`quote-revision-row-${r.revision_number}`}>
                        <div>
                          <div className="font-medium">Revision #{r.revision_number}</div>
                          <div className="text-xs text-muted-foreground">
                            {r.actor_email} · {r.reason || "edited"}
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
              {editable && hasPerm("quote:write") && (
                <div className="grid grid-cols-2 gap-2">
                  {["draft","sent","approved","declined"].filter((s) => s !== q.status).map((s) => (
                    <Button key={s} size="sm" variant="outline" onClick={() => setStatus.mutate(s)} data-testid={`quote-set-status-${s}`}>
                      <span className="capitalize">{s}</span>
                    </Button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
