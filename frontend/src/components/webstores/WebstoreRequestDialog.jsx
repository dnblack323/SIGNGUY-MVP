import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import api, { extractError } from "@/lib/api";
import { createWebstoreRequest, findWebstoreCustomerMatches } from "@/lib/webstores";

export const WEBSTORE_REQUEST_TYPES = [
  { value: "fundraiser", label: "Fundraiser" },
  { value: "event", label: "Event" },
  { value: "team_school", label: "Team / School" },
  { value: "b2b", label: "Business / B2B" },
  { value: "employee_company", label: "Employee / Company store (business preset)" },
  { value: "promotional", label: "Promotional" },
  { value: "general", label: "General" },
];

const EMPTY = {
  mode: "existing",
  customerId: "",
  search: "",
  newCustomer: { name: "", company: "", email: "", phone: "" },
  confirmNew: false,
  contact: { name: "", email: "", phone: "" },
  storeType: "general",
  storeName: "",
  purpose: "",
  openingDate: "",
  closingDate: "",
  eventDate: "",
  notes: "",
};

/** One-minute Webstore request from the Webstores page, a Customer page, or an Intake. Nothing is emailed here. */
export default function WebstoreRequestDialog({ open, onOpenChange, onCreated, customer = null, intakeId = null, defaults = {} }) {
  const [form, setForm] = useState(EMPTY);
  const [matches, setMatches] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setForm({ ...EMPTY, ...defaults, customerId: customer?.id || "", mode: customer ? "existing" : defaults.mode || "existing" });
      setMatches([]);
      setError("");
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const update = (patch) => setForm((current) => ({ ...current, ...patch }));
  const customers = useQuery({
    queryKey: ["webstore-request-customers", form.search],
    queryFn: async () => (await api.get("/customers", { params: { search: form.search || undefined, limit: 25 } })).data?.items || [],
    enabled: open && !customer && form.mode === "existing",
  });

  const checkDuplicates = async () => {
    const { name, email, phone } = form.newCustomer;
    if (!name && !email && !phone) return;
    try {
      setMatches(await findWebstoreCustomerMatches({ name: name || undefined, email: email || undefined, phone: phone || undefined }));
    } catch {
      setMatches([]);
    }
  };

  const submit = useMutation({
    mutationFn: () => createWebstoreRequest({
      customer_id: form.mode === "existing" ? form.customerId || customer?.id : undefined,
      new_customer: form.mode === "new" ? form.newCustomer : undefined,
      confirm_new_customer: form.confirmNew,
      contact: form.contact,
      store_type: form.storeType,
      store_name: form.storeName || undefined,
      purpose: form.purpose || undefined,
      target_launch_at: form.openingDate || undefined,
      deadline_at: form.closingDate || undefined,
      event_start_at: form.storeType === "event" ? form.eventDate || undefined : undefined,
      notes: form.notes || undefined,
      intake_id: intakeId || undefined,
      idempotency_key: `webstore-request-${form.customerId || form.newCustomer.email || form.newCustomer.name}-${form.storeName}`.toLowerCase(),
    }),
    onSuccess: (data) => {
      onOpenChange(false);
      onCreated?.(data.webstore);
    },
    onError: (err) => setError(extractError(err)),
  });

  const strongMatches = matches.filter((m) => m.strong);
  const hasCustomer = form.mode === "existing" ? Boolean(form.customerId || customer) : Boolean(form.newCustomer.name.trim());
  const blockedByDuplicate = form.mode === "new" && strongMatches.length > 0 && !form.confirmNew;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[640px]" data-testid="webstore-request-dialog">
        <DialogHeader>
          <DialogTitle>New Webstore request</DialogTitle>
          <DialogDescription>Record the request. Next, send the information packet from the Webstore page.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 text-sm">
          {customer ? (
            <Alert><AlertTitle>{customer.name}</AlertTitle><AlertDescription>{customer.email || "No email on file"}</AlertDescription></Alert>
          ) : (
            <div className="grid gap-2">
              <div className="flex gap-2">
                <Button type="button" size="sm" variant={form.mode === "existing" ? "default" : "outline"} onClick={() => update({ mode: "existing" })} data-testid="webstore-request-existing">Existing customer</Button>
                <Button type="button" size="sm" variant={form.mode === "new" ? "default" : "outline"} onClick={() => update({ mode: "new", customerId: "" })} data-testid="webstore-request-new">New customer</Button>
              </div>
              {form.mode === "existing" ? (
                <>
                  <Input placeholder="Search customers" value={form.search} onChange={(e) => update({ search: e.target.value })} data-testid="webstore-request-search" />
                  <Select value={form.customerId} onValueChange={(value) => update({ customerId: value })}>
                    <SelectTrigger data-testid="webstore-request-customer"><SelectValue placeholder={customers.isLoading ? "Loading..." : "Choose a customer"} /></SelectTrigger>
                    <SelectContent>{(customers.data || []).map((c) => <SelectItem key={c.id} value={c.id}>{c.name}{c.email ? ` - ${c.email}` : ""}</SelectItem>)}</SelectContent>
                  </Select>
                </>
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  <Input placeholder="Customer or organization name" value={form.newCustomer.name} onChange={(e) => update({ newCustomer: { ...form.newCustomer, name: e.target.value } })} onBlur={checkDuplicates} data-testid="webstore-request-customer-name" />
                  <Input placeholder="Company (optional)" value={form.newCustomer.company} onChange={(e) => update({ newCustomer: { ...form.newCustomer, company: e.target.value } })} />
                  <Input type="email" placeholder="Email" value={form.newCustomer.email} onChange={(e) => update({ newCustomer: { ...form.newCustomer, email: e.target.value } })} onBlur={checkDuplicates} data-testid="webstore-request-customer-email" />
                  <Input placeholder="Phone" value={form.newCustomer.phone} onChange={(e) => update({ newCustomer: { ...form.newCustomer, phone: e.target.value } })} onBlur={checkDuplicates} />
                </div>
              )}
              {form.mode === "new" && matches.length > 0 && (
                <Alert variant={strongMatches.length ? "destructive" : "default"} data-testid="webstore-request-matches">
                  <AlertTitle>{strongMatches.length ? "This customer may already exist" : "Similar customer name"}</AlertTitle>
                  <AlertDescription className="space-y-2">
                    {matches.map((m) => (
                      <div key={m.customer.id} className="flex flex-wrap items-center gap-2">
                        <span>{m.customer.name}{m.customer.email ? ` - ${m.customer.email}` : ""} ({m.match_reasons.join(", ")})</span>
                        <Button type="button" size="sm" variant="outline" onClick={() => update({ mode: "existing", customerId: m.customer.id, search: m.customer.name })}>Use this customer</Button>
                      </div>
                    ))}
                    {strongMatches.length > 0 && (
                      <label className="flex items-center gap-2"><Checkbox checked={form.confirmNew} onCheckedChange={(v) => update({ confirmNew: Boolean(v) })} />This is a different customer</label>
                    )}
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="grid gap-1"><Label>Contact name</Label><Input value={form.contact.name} onChange={(e) => update({ contact: { ...form.contact, name: e.target.value } })} placeholder="Defaults to customer" /></div>
            <div className="grid gap-1"><Label>Contact email</Label><Input type="email" value={form.contact.email} onChange={(e) => update({ contact: { ...form.contact, email: e.target.value } })} placeholder="Defaults to customer" data-testid="webstore-request-contact-email" /></div>
            <div className="grid gap-1"><Label>Contact phone</Label><Input value={form.contact.phone} onChange={(e) => update({ contact: { ...form.contact, phone: e.target.value } })} /></div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-1"><Label>Store type</Label>
              <Select value={form.storeType} onValueChange={(value) => update({ storeType: value })}>
                <SelectTrigger data-testid="webstore-request-type"><SelectValue /></SelectTrigger>
                <SelectContent>{WEBSTORE_REQUEST_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1"><Label>Proposed store name</Label><Input value={form.storeName} onChange={(e) => update({ storeName: e.target.value })} data-testid="webstore-request-name" /></div>
          </div>
          <div className="grid gap-1"><Label>Purpose</Label><Input value={form.purpose} onChange={(e) => update({ purpose: e.target.value })} placeholder="What is the store for?" /></div>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="grid gap-1"><Label>Opening date</Label><Input type="date" value={form.openingDate} onChange={(e) => update({ openingDate: e.target.value })} /></div>
            <div className="grid gap-1"><Label>Closing date</Label><Input type="date" value={form.closingDate} onChange={(e) => update({ closingDate: e.target.value })} /></div>
            {form.storeType === "event" && <div className="grid gap-1"><Label>Event date</Label><Input type="date" value={form.eventDate} onChange={(e) => update({ eventDate: e.target.value })} /></div>}
          </div>
          <div className="grid gap-1"><Label>Notes</Label><Textarea rows={2} value={form.notes} onChange={(e) => update({ notes: e.target.value })} /></div>
          {error && <Alert variant="destructive"><AlertTitle>Request not saved</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
        </div>
        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={submit.isPending}>Cancel</Button>
          <Button onClick={() => submit.mutate()} disabled={!hasCustomer || blockedByDuplicate || submit.isPending} data-testid="webstore-request-submit">{submit.isPending ? "Saving..." : "Save request"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
