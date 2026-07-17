import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import StatusPill from "@/components/common/StatusPill";
import TaskHandoffButton from "@/components/tasks/TaskHandoffButton";
import { centsToDollarsString, relativeTime } from "@/lib/format";
import { ArrowLeft, Save } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";

function Field({ label, value, onChange, textarea, type = "text", testId }) {
  const Comp = textarea ? Textarea : Input;
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Comp value={value || ""} onChange={(e) => onChange(e.target.value)} type={type} data-testid={testId} />
    </div>
  );
}

export default function CustomerDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("customer:write");

  const { data: c, isLoading } = useQuery({
    queryKey: ["customer", id],
    queryFn: async () => (await api.get(`/customers/${id}`)).data,
  });
  const { data: rel } = useQuery({
    queryKey: ["customer-related", id],
    queryFn: async () => (await api.get(`/customers/${id}/related`)).data,
    enabled: !!id,
  });
  const { data: audit } = useQuery({
    queryKey: ["customer-audit", id],
    queryFn: async () => (await api.get(`/audit`, { params: { entity_type: "customer", entity_id: id, limit: 50 } })).data,
    enabled: !!id,
  });

  const [form, setForm] = useState({});
  const editForm = { ...c, ...form };

  const save = useMutation({
    mutationFn: async (payload) => (await api.patch(`/customers/${id}`, payload)).data,
    onSuccess: () => {
      toast.success("Customer updated");
      qc.invalidateQueries({ queryKey: ["customer", id] });
      qc.invalidateQueries({ queryKey: ["customer-audit", id] });
      setForm({});
    },
    onError: (e) => toast.error(extractError(e)),
  });

  if (isLoading || !c) return <div className="text-sm text-muted-foreground">Loading…</div>;

  return (
    <div className="space-y-4" data-testid="customer-detail-page">
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="icon"><Link to="/customers"><ArrowLeft className="size-4" /></Link></Button>
        <PageHeader
          title={c.name}
          subtitle={c.company || c.email || "Customer"}
          actions={(
            <div className="flex flex-wrap gap-2">
              <TaskHandoffButton sourceType="customer" sourceId={id} defaults={{ title: `Follow up with ${c.name}`, task_type: "customer_followup" }} />
              {canWrite && Object.keys(form).length > 0 && (
                <Button onClick={() => save.mutate(form)} disabled={save.isPending} data-testid="customer-save-button">
                  <Save className="size-4 mr-1" /> Save changes
                </Button>
              )}
            </div>
          )}
        />
      </div>

      <Tabs defaultValue="details" data-testid="detail-tabs">
        <TabsList>
          <TabsTrigger value="details" data-testid="detail-tab-details">Details</TabsTrigger>
          <TabsTrigger value="linked" data-testid="detail-tab-linked">Linked records</TabsTrigger>
          <TabsTrigger value="activity" data-testid="detail-tab-activity">Activity</TabsTrigger>
        </TabsList>
        <TabsContent value="details" className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Contact</CardTitle></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <Field label="Name" value={editForm.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} testId="customer-detail-name-input" />
              <Field label="Company" value={editForm.company} onChange={(v) => setForm((f) => ({ ...f, company: v }))} testId="customer-detail-company-input" />
              <Field label="Email" type="email" value={editForm.email} onChange={(v) => setForm((f) => ({ ...f, email: v }))} testId="customer-detail-email-input" />
              <Field label="Phone" value={editForm.phone} onChange={(v) => setForm((f) => ({ ...f, phone: v }))} testId="customer-detail-phone-input" />
              <Field label="Address 1" value={editForm.address_line1} onChange={(v) => setForm((f) => ({ ...f, address_line1: v }))} />
              <Field label="Address 2" value={editForm.address_line2} onChange={(v) => setForm((f) => ({ ...f, address_line2: v }))} />
              <Field label="City" value={editForm.city} onChange={(v) => setForm((f) => ({ ...f, city: v }))} />
              <Field label="State" value={editForm.state} onChange={(v) => setForm((f) => ({ ...f, state: v }))} />
              <Field label="Postal code" value={editForm.postal_code} onChange={(v) => setForm((f) => ({ ...f, postal_code: v }))} />
              <Field label="Country" value={editForm.country} onChange={(v) => setForm((f) => ({ ...f, country: v }))} />
              <div className="md:col-span-2"><Field label="Notes" textarea value={editForm.notes} onChange={(v) => setForm((f) => ({ ...f, notes: v }))} /></div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="linked" className="space-y-4" data-testid="customer-linked">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader><CardTitle>Quotes</CardTitle></CardHeader>
              <CardContent>
                {rel?.quotes?.length ? (
                  <ul className="divide-y">
                    {rel.quotes.map((q) => (
                      <li key={q.id} className="py-2 flex items-center justify-between">
                        <Link className="text-sm hover:underline" to={`/quotes/${q.id}`}><span className="mono text-xs text-muted-foreground mr-2">Q-{q.number}</span>{q.job_name}</Link>
                        <div className="flex items-center gap-2"><span className="text-sm tabular-nums">{centsToDollarsString(q.total_cents)}</span><StatusPill kind="quote" value={q.status} /></div>
                      </li>
                    ))}
                  </ul>
                ) : <div className="text-sm text-muted-foreground">No quotes.</div>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Orders</CardTitle></CardHeader>
              <CardContent>
                {rel?.orders?.length ? (
                  <ul className="divide-y">
                    {rel.orders.map((o) => (
                      <li key={o.id} className="py-2 flex items-center justify-between">
                        <Link className="text-sm hover:underline" to={`/orders/${o.id}`}><span className="mono text-xs text-muted-foreground mr-2">O-{o.number}</span>{o.job_name}</Link>
                        <StatusPill kind="order" value={o.status} />
                      </li>
                    ))}
                  </ul>
                ) : <div className="text-sm text-muted-foreground">No orders.</div>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Work orders</CardTitle></CardHeader>
              <CardContent>
                {rel?.work_orders?.length ? (
                  <ul className="divide-y">
                    {rel.work_orders.map((w) => (
                      <li key={w.id} className="py-2 flex items-center justify-between">
                        <Link className="text-sm hover:underline" to={`/work-orders/${w.id}`}><span className="mono text-xs text-muted-foreground mr-2">W-{w.number}</span>Order {w.order_id.slice(0, 8)}…</Link>
                        <StatusPill kind="production" value={w.production_status} />
                      </li>
                    ))}
                  </ul>
                ) : <div className="text-sm text-muted-foreground">No work orders.</div>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Invoices</CardTitle></CardHeader>
              <CardContent>
                {rel?.invoices?.length ? (
                  <ul className="divide-y">
                    {rel.invoices.map((inv) => (
                      <li key={inv.id} className="py-2 flex items-center justify-between">
                        <Link className="text-sm hover:underline" to={`/invoices/${inv.id}`}><span className="mono text-xs text-muted-foreground mr-2">I-{inv.number}</span>{inv.title}</Link>
                        <div className="flex items-center gap-2"><span className="text-sm tabular-nums">{centsToDollarsString(inv.total_cents)}</span><StatusPill kind="invoice" value={inv.status} /></div>
                      </li>
                    ))}
                  </ul>
                ) : <div className="text-sm text-muted-foreground">No invoices.</div>}
              </CardContent>
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader><CardTitle>Emails</CardTitle></CardHeader>
              <CardContent>
                {rel?.emails?.length ? (
                  <ul className="divide-y">
                    {rel.emails.map((e) => (
                      <li key={e.id} className="py-2 flex items-center justify-between gap-2">
                        <div className="min-w-0"><div className="text-sm truncate">{e.subject}</div><div className="text-xs text-muted-foreground">to {e.to_email} · {relativeTime(e.created_at)}</div></div>
                        <StatusPill kind="email" value={e.status} />
                      </li>
                    ))}
                  </ul>
                ) : <div className="text-sm text-muted-foreground">No emails yet.</div>}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="activity">
          <AuditTimeline events={audit?.items || []} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
