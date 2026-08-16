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
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import StatusPill from "@/components/common/StatusPill";
import TaskHandoffButton from "@/components/tasks/TaskHandoffButton";
import AIContextualActions from "@/components/ai/AIContextualActions";
import { centsToDollarsString, relativeTime } from "@/lib/format";
import { buildShopScheduleUrl } from "@/lib/shopScheduleLinks";
import { Archive, ArchiveRestore, ArrowLeft, CalendarDays, Save } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { useWorkspaceDirty } from "@/context/WorkspaceContext";

function Field({ label, value, onChange, textarea, type = "text", testId }) {
  const Comp = textarea ? Textarea : Input;
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Comp value={value || ""} onChange={(e) => onChange(e.target.value)} type={type} data-testid={testId} />
    </div>
  );
}

function emptyContact(customer) {
  return { name: customer?.name || "", email: "", phone: "", role: "other", is_primary: false };
}

function emptyAddress() {
  return { label: "", line1: "", line2: "", city: "", state: "", postal_code: "", country: "", purposes: ["other"], is_default: false };
}

function RelatedList({ title, items = [], getLabel, getUrl, getMeta, statusKind }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        {items.length ? (
          <ul className="divide-y">
            {items.map((item) => {
              const url = getUrl?.(item) || item.source_url;
              return (
                <li key={item.id} className="py-2 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    {url ? <Link className="text-sm font-medium hover:underline" to={url}>{getLabel(item)}</Link> : <div className="text-sm font-medium">{getLabel(item)}</div>}
                    {getMeta?.(item) && <div className="text-xs text-muted-foreground truncate">{getMeta(item)}</div>}
                  </div>
                  {(item.status || item.production_status || item.document_status) && <StatusPill kind={statusKind || "generic"} value={item.status || item.production_status || item.document_status} />}
                </li>
              );
            })}
          </ul>
        ) : <div className="text-sm text-muted-foreground">No linked records.</div>}
      </CardContent>
    </Card>
  );
}

export default function CustomerDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("customer:write");
  const canSchedule = hasPerm("schedule:manage");

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
  useWorkspaceDirty(Object.keys(form).length > 0);
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
  const archive = useMutation({
    mutationFn: async () => (await api.post(`/customers/${id}/archive`, { reason: "Archived from customer detail" })).data,
    onSuccess: () => {
      toast.success("Customer archived");
      qc.invalidateQueries({ queryKey: ["customer", id] });
      qc.invalidateQueries({ queryKey: ["customer-audit", id] });
    },
    onError: (e) => toast.error(extractError(e)),
  });
  const restore = useMutation({
    mutationFn: async () => (await api.post(`/customers/${id}/restore`, {})).data,
    onSuccess: () => {
      toast.success("Customer restored");
      qc.invalidateQueries({ queryKey: ["customer", id] });
      qc.invalidateQueries({ queryKey: ["customer-audit", id] });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  if (isLoading || !c) return <div className="text-sm text-muted-foreground">Loading…</div>;
  const contacts = editForm.contacts?.length ? editForm.contacts : [{ name: editForm.name || "", email: editForm.email || "", phone: editForm.phone || "", role: "primary", is_primary: true }];
  const addresses = editForm.addresses?.length ? editForm.addresses : (editForm.address_line1 || editForm.city || editForm.state || editForm.postal_code ? [{
    label: "Primary address",
    line1: editForm.address_line1 || "",
    line2: editForm.address_line2 || "",
    city: editForm.city || "",
    state: editForm.state || "",
    postal_code: editForm.postal_code || "",
    country: editForm.country || "",
    purposes: ["billing", "shipping"],
    is_default: true,
  }] : []);
  const setContact = (index, field, value) => setForm((f) => {
    const next = [...contacts].map((item) => ({ ...item }));
    next[index][field] = value;
    if (field === "is_primary" && value) next.forEach((item, idx) => { item.is_primary = idx === index; item.role = idx === index ? "primary" : item.role; });
    return { ...f, contacts: next };
  });
  const setAddress = (index, field, value) => setForm((f) => {
    const next = [...addresses].map((item) => ({ ...item }));
    next[index][field] = value;
    if (field === "is_default" && value) next.forEach((item, idx) => { item.is_default = idx === index; });
    return { ...f, addresses: next };
  });

  return (
    <div className="space-y-4" data-testid="customer-detail-page">
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="icon"><Link to="/customers"><ArrowLeft className="size-4" /></Link></Button>
        <PageHeader
          title={c.name}
          subtitle={c.company || c.email || "Customer"}
          actions={(
            <div className="flex flex-wrap gap-2">
              <AIContextualActions contextType="customer" contextId={id} actions={[
                { label: "Draft Email", tool: "email_draft_assistant", mode: "custom_email" },
                { label: "Create Document", tool: "document_writer", mode: "customer_order_document" },
              ]} />
              <TaskHandoffButton sourceType="customer" sourceId={id} defaults={{ title: `Follow up with ${c.name}`, task_type: "customer_followup" }} />
              {canSchedule && (
                <Button asChild variant="outline" size="sm" data-testid="customer-schedule-button">
                  <Link to={buildShopScheduleUrl({ create: true, customerId: id, title: `Appointment with ${c.name}` })}>
                    <CalendarDays className="size-4 mr-1" />Schedule
                  </Link>
                </Button>
              )}
              {canWrite && Object.keys(form).length > 0 && (
                <Button onClick={() => save.mutate(form)} disabled={save.isPending} data-testid="customer-save-button">
                  <Save className="size-4 mr-1" /> Save changes
                </Button>
              )}
              {canWrite && !c.archived && !c.merged_into && (
                <Button variant="outline" onClick={() => archive.mutate()} disabled={archive.isPending} data-testid="customer-archive-button">
                  <Archive className="size-4 mr-1" />Archive
                </Button>
              )}
              {canWrite && c.archived && !c.merged_into && (
                <Button variant="outline" onClick={() => restore.mutate()} disabled={restore.isPending} data-testid="customer-restore-button">
                  <ArchiveRestore className="size-4 mr-1" />Restore
                </Button>
              )}
            </div>
          )}
        />
      </div>
      {c.archived && (
        <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm" data-testid="customer-archived-banner">
          This customer is {c.merged_into ? <>merged into <Link className="underline" to={`/customers/${c.merged_into}`}>{c.merged_into}</Link></> : "archived"}. Historical records remain linked and reportable.
        </div>
      )}

      <Tabs defaultValue="overview" data-testid="detail-tabs">
        <TabsList>
          <TabsTrigger value="overview" data-testid="detail-tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="contacts" data-testid="detail-tab-contacts">Contacts</TabsTrigger>
          <TabsTrigger value="communications" data-testid="detail-tab-communications">Communications</TabsTrigger>
          <TabsTrigger value="requests" data-testid="detail-tab-requests">Requests</TabsTrigger>
          <TabsTrigger value="quotes" data-testid="detail-tab-quotes">Quotes</TabsTrigger>
          <TabsTrigger value="orders" data-testid="detail-tab-orders">Orders</TabsTrigger>
          <TabsTrigger value="files-forms" data-testid="detail-tab-files-forms">Files & Forms</TabsTrigger>
          <TabsTrigger value="portal" data-testid="detail-tab-portal">Portal</TabsTrigger>
          <TabsTrigger value="activity" data-testid="detail-tab-activity">Activity</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Customer profile</CardTitle></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <Field label="Name" value={editForm.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} testId="customer-detail-name-input" />
              <Field label="Company" value={editForm.company} onChange={(v) => setForm((f) => ({ ...f, company: v }))} testId="customer-detail-company-input" />
              <div className="grid gap-1.5">
                <Label>Type</Label>
                <Select value={editForm.customer_type || "business"} onValueChange={(v) => setForm((f) => ({ ...f, customer_type: v }))}>
                  <SelectTrigger data-testid="customer-detail-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="business">Business</SelectItem>
                    <SelectItem value="individual">Individual</SelectItem>
                    <SelectItem value="organization">Organization</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label>Lifecycle</Label>
                <Select value={editForm.lifecycle_status || "active"} onValueChange={(v) => setForm((f) => ({ ...f, lifecycle_status: v }))}>
                  <SelectTrigger data-testid="customer-detail-lifecycle-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="lead">Lead</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                    <SelectItem value="archived">Archived</SelectItem>
                  </SelectContent>
                </Select>
              </div>
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

        <TabsContent value="contacts" className="space-y-4" data-testid="customer-contacts">
          <Card>
            <CardHeader><CardTitle>Contacts</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {contacts.map((contact, index) => (
                <div key={index} className="rounded-md border p-3 grid gap-3 md:grid-cols-4">
                  <Field label="Name" value={contact.name} onChange={(v) => setContact(index, "name", v)} testId={`customer-contact-name-${index}`} />
                  <Field label="Email" type="email" value={contact.email} onChange={(v) => setContact(index, "email", v)} />
                  <Field label="Phone" value={contact.phone} onChange={(v) => setContact(index, "phone", v)} />
                  <div className="grid gap-1.5">
                    <Label>Role</Label>
                    <Select value={contact.role || "other"} onValueChange={(v) => setContact(index, "role", v)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="primary">Primary</SelectItem>
                        <SelectItem value="billing">Billing</SelectItem>
                        <SelectItem value="production">Production</SelectItem>
                        <SelectItem value="approval">Approval</SelectItem>
                        <SelectItem value="other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button type="button" variant={contact.is_primary ? "default" : "outline"} size="sm" onClick={() => setContact(index, "is_primary", true)} data-testid={`customer-contact-primary-${index}`}>
                    {contact.is_primary ? "Primary contact" : "Make primary"}
                  </Button>
                </div>
              ))}
              {canWrite && <Button type="button" variant="outline" onClick={() => setForm((f) => ({ ...f, contacts: [...contacts, emptyContact(c)] }))}>Add contact</Button>}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Addresses</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {addresses.map((address, index) => (
                <div key={index} className="rounded-md border p-3 grid gap-3 md:grid-cols-3">
                  <Field label="Label" value={address.label} onChange={(v) => setAddress(index, "label", v)} />
                  <Field label="Address 1" value={address.line1} onChange={(v) => setAddress(index, "line1", v)} testId={`customer-address-line1-${index}`} />
                  <Field label="Address 2" value={address.line2} onChange={(v) => setAddress(index, "line2", v)} />
                  <Field label="City" value={address.city} onChange={(v) => setAddress(index, "city", v)} />
                  <Field label="State" value={address.state} onChange={(v) => setAddress(index, "state", v)} />
                  <Field label="Postal code" value={address.postal_code} onChange={(v) => setAddress(index, "postal_code", v)} />
                  <Button type="button" variant={address.is_default ? "default" : "outline"} size="sm" onClick={() => setAddress(index, "is_default", true)} data-testid={`customer-address-default-${index}`}>
                    {address.is_default ? "Default address" : "Make default"}
                  </Button>
                  <div className="flex flex-wrap items-center gap-1 md:col-span-2">
                    {(address.purposes || []).map((purpose) => <Badge key={purpose} variant="outline">{purpose}</Badge>)}
                  </div>
                </div>
              ))}
              {canWrite && <Button type="button" variant="outline" onClick={() => setForm((f) => ({ ...f, addresses: [...addresses, emptyAddress()] }))}>Add address</Button>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="communications" className="space-y-4" data-testid="customer-communications">
          <Card>
            <CardHeader><CardTitle>Communications</CardTitle></CardHeader>
            <CardContent>
              {rel?.emails?.length ? (
                <ul className="divide-y">
                  {rel.emails.map((e) => (
                    <li key={e.id} className="py-2 flex items-center justify-between gap-2">
                      <div className="min-w-0"><div className="text-sm truncate">{e.subject}</div><div className="text-xs text-muted-foreground">to {e.to_email} &middot; {relativeTime(e.created_at)}</div></div>
                      <StatusPill kind="email" value={e.status} />
                    </li>
                  ))}
                </ul>
              ) : <div className="text-sm text-muted-foreground">No communications yet.</div>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="requests" className="space-y-4" data-testid="customer-requests">
          <RelatedList title="Schedule events" items={rel?.schedule_events || []} getLabel={(item) => item.title} getUrl={(item) => `/shop-schedule?event_id=${item.id}`} getMeta={(item) => `${item.start_at || "Unscheduled"} ${item.status || ""}`} statusKind="schedule" />
          <RelatedList title="Decision Rooms" items={rel?.decision_rooms || []} getLabel={(item) => item.title} getUrl={(item) => `/decision-rooms/${item.id}`} getMeta={(item) => item.customer_safe_intro} />
          <RelatedList title="Approval records" items={rel?.approvals || []} getLabel={(item) => item.parent_type?.replace(/_/g, " ") || "Approval"} getUrl={() => "/approval-center"} getMeta={(item) => item.reason || item.action} />
          <RelatedList title="Intake requests" items={[...(rel?.quote_requests || []), ...(rel?.customer_intakes || [])]} getLabel={(item) => item.title || item.project_name || item.id} getUrl={() => "/intake"} getMeta={(item) => item.status} />
        </TabsContent>

        <TabsContent value="quotes" className="space-y-4" data-testid="customer-quotes">
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
              <RelatedList title="Payments" items={rel?.payments || []} getLabel={(item) => item.reference || item.payment_method || "Payment"} getMeta={(item) => centsToDollarsString(item.amount_cents)} />
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="orders" className="space-y-4" data-testid="customer-orders">
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
        </TabsContent>

        <TabsContent value="files-forms" className="space-y-4" data-testid="customer-files-forms">
          <RelatedList title="Documents" items={rel?.documents || []} getLabel={(item) => item.title} getUrl={(item) => `/documents/${item.id}`} getMeta={(item) => item.category} />
          <RelatedList title="Proofs" items={rel?.proofs || []} getLabel={(item) => item.title || `Proof ${item.number || item.id}`} getUrl={(item) => `/proofs/${item.id}`} getMeta={(item) => item.parent_type} />
          <RelatedList title="Files" items={rel?.files || []} getLabel={(item) => item.original_filename} getUrl={(item) => `/files/${item.id}`} getMeta={(item) => item.visibility} />
        </TabsContent>

        <TabsContent value="portal" className="space-y-4" data-testid="customer-portal">
          <RelatedList title="Portal identities" items={rel?.portal_identities || []} getLabel={(item) => item.email || item.display_name || item.id} getUrl={(item) => `/portal-identities/${item.id}`} getMeta={(item) => item.status || item.portal_type} />
          <RelatedList title="Webstores" items={rel?.webstores || []} getLabel={(item) => item.name || item.title || item.id} getUrl={(item) => `/webstores/${item.id}`} getMeta={(item) => item.status} />
          <RelatedList title="Tasks" items={rel?.tasks || []} getLabel={(item) => item.title || item.id} getUrl={(item) => `/team/tasks?task_id=${item.id}`} getMeta={(item) => item.status} />
        </TabsContent>

        <TabsContent value="activity">
          <AuditTimeline events={audit?.items || []} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
