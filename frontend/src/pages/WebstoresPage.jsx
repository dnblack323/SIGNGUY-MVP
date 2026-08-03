import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Clock3, Plus, RotateCcw, Store, Users } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { extractError } from "@/lib/api";
import { createWebstore, createWebstoreOwner, listWebstores, sendWebstoreQuestionnaire, uploadWebstoreSetupFile } from "@/lib/webstores";
import api from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { toast } from "sonner";

const WEBSTORE_TYPES = [
  { value: "b2b", label: "B2B" },
  { value: "fundraiser", label: "Fundraiser" },
  { value: "event", label: "Event" },
  { value: "promotional", label: "Promotional" },
  { value: "general", label: "General" },
];

const INITIAL_FORM = {
  ownerMode: "new",
  customerId: "",
  ownerName: "",
  ownerEmail: "",
  storeName: "",
  storeType: "general",
  purpose: "",
  visibility: "public",
  openingDate: "",
  closingDate: "",
  primaryColor: "#0f172a",
  accentColor: "#2563eb",
  greeting: "",
  startingProducts: "",
  logo: null,
  banner: null,
};

function statusTone(status) {
  if (status === "live") return "secondary";
  if (["closed", "archived"].includes(status)) return "destructive";
  return "outline";
}

function formatLabel(value) {
  return String(value || "").replace(/_/g, " ");
}

function typeLabel(value) {
  return WEBSTORE_TYPES.find((type) => type.value === value)?.label || formatLabel(value || "general");
}

function actionForStore(store) {
  if (store.manager_action_required) return store.manager_action_required;
  const status = store.setup_state || store.status;
  if (["questionnaire_sent", "waiting_on_store_owner"].includes(status)) return "Waiting on owner questionnaire";
  if (status === "questionnaire_submitted") return "Review answers and apply setup fields";
  if (["products_selected", "ai_setup_ready", "artwork_needs_review"].includes(status)) return "Finish product setup and mockups";
  if (["store_packet_generated", "sent_for_approval"].includes(status)) return "Review owner approval packet";
  if (store.status === "live") return store.checkout_enabled ? "Live and accepting orders" : "Live but checkout is off";
  if (!store.checkout_enabled && ["launch_ready", "owner_approved"].includes(store.status)) return "Payment setup incomplete";
  return "Continue setup";
}

function NewWebstoreDialog({ open, onOpenChange, onCreated, user }) {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(INITIAL_FORM);
  const [storeNameAutoFilled, setStoreNameAutoFilled] = useState(true);
  const [customers, setCustomers] = useState([]);
  const [customersLoading, setCustomersLoading] = useState(false);
  const [error, setError] = useState("");

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const suggestedStoreName = (ownerName) => ownerName.trim() ? `${ownerName.trim()} Store` : "";
  const selectedCustomer = customers.find((customer) => customer.id === form.customerId);
  const effectiveOwnerName = form.ownerMode === "self" ? user?.full_name || user?.name || user?.email || "" : form.ownerMode === "customer" ? selectedCustomer?.name || "" : form.ownerName;
  const effectiveOwnerEmail = form.ownerMode === "self" ? user?.email || "" : form.ownerMode === "customer" ? selectedCustomer?.email || "" : form.ownerEmail;
  const canContinue = step === 0
    ? Boolean(form.storeType)
    : step === 1
      ? Boolean(effectiveOwnerName && effectiveOwnerEmail)
      : step === 2
        ? Boolean(form.storeName.trim())
        : true;

  const loadCustomers = async () => {
    if (customers.length || customersLoading) return;
    setCustomersLoading(true);
    try {
      const response = await api.get("/customers", { params: { limit: 200 } });
      setCustomers(response.data?.items || []);
    } catch (loadError) {
      setError(extractError(loadError));
    } finally {
      setCustomersLoading(false);
    }
  };

  const reset = () => {
    setStep(0);
    setForm(INITIAL_FORM);
    setStoreNameAutoFilled(true);
    setError("");
  };

  const createFlow = useMutation({
    mutationFn: async () => {
      const owner = await createWebstoreOwner({
        name: effectiveOwnerName,
        email: effectiveOwnerEmail,
        customer_id: form.ownerMode === "customer" ? form.customerId : undefined,
        create_portal_identity: false,
      });
      const accessMode = form.visibility === "private" ? "restricted" : "open";
      const store = await createWebstore({
        owner_id: owner.id,
        name: form.storeName,
        store_type: form.storeType,
        description: form.purpose || undefined,
        target_launch_at: form.openingDate || undefined,
        deadline_at: form.closingDate || undefined,
        setup_profile: {
          store_purpose: form.purpose || "",
          starting_products: form.startingProducts.split(",").map((item) => item.trim()).filter(Boolean),
          open_to_product_suggestions: true,
        },
        store_settings: {
          access_policy: { mode: accessMode },
          fulfillment: { method: "decide_later" },
        },
        branding: {
          colors_fonts: { primary_color: form.primaryColor, accent_color: form.accentColor },
          store_information: { welcome_heading: form.greeting || form.purpose || "" },
        },
        idempotency_key: `webstore-create-${effectiveOwnerEmail}-${form.storeName}`.toLowerCase(),
        send_owner_invitation: false,
      });
      const uploads = [];
      for (const [category, file] of [["logo", form.logo], ["banner", form.banner]]) {
        if (!file) continue;
        const formData = new FormData();
        formData.append("category", category);
        formData.append("file", file);
        uploads.push(await uploadWebstoreSetupFile(store.id, formData));
      }
      const questionnaire = await sendWebstoreQuestionnaire(store.id, { email: effectiveOwnerEmail, name: effectiveOwnerName });
      return { store, questionnaire, uploads };
    },
    onSuccess: ({ store, questionnaire }) => {
      if (questionnaire?.email_sent) toast.success("Webstore created and questionnaire sent");
      else if (questionnaire) toast.error(`Webstore created, but the questionnaire email was not sent (${questionnaire.delivery_error || "delivery unavailable"}). The link is available on the Webstore page.`);
      else toast.success("Webstore created; questionnaire link is ready");
      onOpenChange(false);
      onCreated(store, questionnaire);
      reset();
    },
    onError: (mutationError) => setError(extractError(mutationError)),
  });

  const close = (nextOpen) => {
    if (!nextOpen && !createFlow.isPending) {
      onOpenChange(false);
      reset();
    } else {
      onOpenChange(nextOpen);
    }
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[680px]" data-testid="new-webstore-dialog">
        <DialogHeader>
          <DialogTitle>Create a Webstore</DialogTitle>
          <DialogDescription>This short setup creates the draft and sends the type-specific questionnaire. Finish products, approval, and launch from the Webstore page.</DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2 text-xs text-muted-foreground" data-testid="webstore-guided-steps">
          {["Type", "Owner", "Basics", "Branding & products"].map((label, index) => (
            <div key={label} className={`flex min-w-0 flex-1 items-center gap-2 ${index === step ? "font-semibold text-sky-800" : ""}`}>
              <span className={`flex size-6 shrink-0 items-center justify-center rounded-full border ${index === step ? "border-sky-700 bg-sky-700 text-white" : index < step ? "border-emerald-600 bg-emerald-50 text-emerald-700" : "bg-slate-50"}`}>{index + 1}</span>
              <span className="truncate">{label}</span>
            </div>
          ))}
        </div>

        {step === 0 && (
          <div className="grid gap-3" data-testid="webstore-setup-type-step">
            <div className="grid gap-1.5"><Label>What kind of Webstore are you creating?</Label><Select value={form.storeType} onValueChange={(value) => update("storeType", value)}><SelectTrigger data-testid="webstore-type"><SelectValue /></SelectTrigger><SelectContent>{WEBSTORE_TYPES.map((type) => <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>)}</SelectContent></Select></div>
            <p className="text-sm text-muted-foreground">This sets sensible starting defaults and only shows the questions that apply to this type later.</p>
          </div>
        )}

        {step === 1 && (
          <div className="grid gap-3" data-testid="webstore-setup-owner-step">
            <div className="grid gap-2 sm:grid-cols-3">
              {[{ value: "new", label: "Add a new owner" }, { value: "customer", label: "Use an existing customer" }, { value: "self", label: "Create it for my business" }].map((option) => (
                <Button key={option.value} type="button" variant={form.ownerMode === option.value ? "default" : "outline"} className="h-auto justify-start whitespace-normal p-3 text-left" onClick={() => { update("ownerMode", option.value); if (option.value === "customer") loadCustomers(); }} data-testid={`webstore-owner-mode-${option.value}`}>{option.label}</Button>
              ))}
            </div>
            {form.ownerMode === "customer" ? <div className="grid gap-1.5"><Label>Customer</Label><Select value={form.customerId} onValueChange={(value) => update("customerId", value)}><SelectTrigger data-testid="webstore-customer-select"><SelectValue placeholder={customersLoading ? "Loading customers..." : "Select a customer"} /></SelectTrigger><SelectContent>{customers.map((customer) => <SelectItem key={customer.id} value={customer.id}>{customer.name}{customer.email ? ` - ${customer.email}` : ""}</SelectItem>)}</SelectContent></Select>{selectedCustomer && !selectedCustomer.email && <p className="text-xs text-rose-700">This customer needs an email before an owner questionnaire can be sent.</p>}</div> : form.ownerMode === "self" ? <Alert><AlertTitle>{effectiveOwnerName || "Your account"}</AlertTitle><AlertDescription>{effectiveOwnerEmail || "Your account email will be used as the owner contact."}</AlertDescription></Alert> : <div className="grid gap-3 sm:grid-cols-2"><div className="grid gap-1.5"><Label>Owner name</Label><Input value={form.ownerName} onChange={(event) => { const ownerName = event.target.value; update("ownerName", ownerName); if (storeNameAutoFilled) update("storeName", suggestedStoreName(ownerName)); }} placeholder="Name or organization" data-testid="webstore-owner-name" /></div><div className="grid gap-1.5"><Label>Owner email</Label><Input type="email" value={form.ownerEmail} onChange={(event) => update("ownerEmail", event.target.value)} data-testid="webstore-owner-email" /></div></div>}
          </div>
        )}

        {step === 2 && (
          <div className="grid gap-3" data-testid="webstore-setup-basic-step">
            <div className="grid gap-1.5"><Label>What should the Webstore be called?</Label><Input value={form.storeName} onChange={(event) => { setStoreNameAutoFilled(false); update("storeName", event.target.value); }} placeholder="Team Store" data-testid="webstore-name" /></div>
            <div className="grid gap-1.5"><Label>Brief description or welcome message</Label><Textarea rows={3} value={form.purpose} onChange={(event) => update("purpose", event.target.value)} placeholder="A short message for the store owner and shoppers." data-testid="webstore-purpose" /></div>
            <div className="grid gap-3 sm:grid-cols-2"><div className="grid gap-1.5"><Label>Opening date</Label><Input type="date" value={form.openingDate} onChange={(event) => update("openingDate", event.target.value)} /></div><div className="grid gap-1.5"><Label>Closing date</Label><Input type="date" value={form.closingDate} onChange={(event) => update("closingDate", event.target.value)} /></div></div>
          </div>
        )}

        {step === 3 && (
          <div className="grid gap-4" data-testid="webstore-setup-content-step">
            <div className="grid gap-3 sm:grid-cols-2"><div className="grid gap-1.5"><Label>Logo (optional)</Label><Input type="file" accept="image/*" onChange={(event) => update("logo", event.target.files?.[0] || null)} /></div><div className="grid gap-1.5"><Label>Banner image (optional)</Label><Input type="file" accept="image/*" onChange={(event) => update("banner", event.target.files?.[0] || null)} /></div></div>
            <div className="grid gap-1.5"><Label>Store color</Label><Input type="color" value={form.primaryColor} onChange={(event) => update("primaryColor", event.target.value)} aria-label="Store color" /><p className="text-xs text-muted-foreground">The shop can refine the full palette later in Storefront.</p></div>
            <div className="grid gap-1.5"><Label>Product types wanted</Label><Input value={form.startingProducts} onChange={(event) => update("startingProducts", event.target.value)} placeholder="Shirts, hats, signs" data-testid="webstore-starting-products" /><p className="text-xs text-muted-foreground">These names stay visible under Products as starting ideas until the shop configures them.</p></div>
            <p className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">After you create the draft, the existing questionnaire for this Webstore type is sent to the owner automatically.</p>
          </div>
        )}

        {error && <Alert variant="destructive"><AlertTitle>Webstore was not created</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
        <DialogFooter className="gap-2 sm:justify-between">
          <Button type="button" variant="ghost" onClick={() => step > 0 ? setStep(step - 1) : close(false)} disabled={createFlow.isPending}>{step > 0 ? "Back" : "Cancel"}</Button>
          {step < 3 ? <Button type="button" onClick={() => setStep(step + 1)} disabled={!canContinue} data-testid="webstore-setup-next">Continue</Button> : <Button type="button" onClick={() => createFlow.mutate()} disabled={createFlow.isPending || !canContinue} data-testid="webstore-create">{createFlow.isPending ? "Creating draft..." : "Create and Send Questionnaire"}</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function WebstoresPage() {
  const { hasPerm, user } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);
  const canRead = hasPerm("webstore:read");
  const canManage = hasPerm("webstore:manage");
  const stores = useQuery({ queryKey: ["webstores"], queryFn: () => listWebstores(), enabled: canRead });
  const storeItems = stores.data?.items || [];
  const ownerWaitingCount = storeItems.filter((store) => ["questionnaire_sent", "waiting_on_store_owner"].includes(store.setup_state || store.status)).length;
  const submittedCount = storeItems.filter((store) => (store.setup_state || store.status) === "questionnaire_submitted").length;
  const checkoutBlockedCount = storeItems.filter((store) => !store.checkout_enabled && ["launch_ready", "owner_approved", "live"].includes(store.status)).length;

  const handleCreated = async (store, questionnaire) => {
    await qc.invalidateQueries({ queryKey: ["webstores"] });
    navigate(`/webstores/${store.id}`, { state: { questionnaireDelivery: questionnaire } });
  };

  if (!canRead) return <div className="space-y-4" data-testid="webstores-page"><PageHeader title="Webstores" subtitle="Tenant Webstores are available to authorized owner and admin accounts." /><Alert><Store className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account does not include Webstores access.</AlertDescription></Alert></div>;

  return (
    <div className="space-y-4" data-testid="webstores-page">
      <PageHeader title="Webstores" subtitle="Create and manage customer Webstores from intake through launch." actions={<div className="flex flex-wrap gap-2">{canManage && <Button onClick={() => setCreateOpen(true)} data-testid="new-webstore-button"><Plus className="size-4 mr-2" />New Webstore</Button>}<Button variant="outline" size="sm" onClick={() => stores.refetch()}><RotateCcw className="size-4 mr-2" />Refresh</Button></div>} />
      <NewWebstoreDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={handleCreated} user={user} />

      <div className="grid gap-3 md:grid-cols-4" data-testid="webstores-dashboard-cards">
        <Card className="border-sky-200 bg-sky-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><Store className="size-8 rounded-md bg-sky-700 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-sky-900">Current Webstores</div><div className="text-2xl font-semibold">{storeItems.length}</div></div></CardContent></Card>
        <Card className="border-amber-200 bg-amber-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><Clock3 className="size-8 rounded-md bg-amber-600 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-amber-900">Waiting On Owner</div><div className="text-2xl font-semibold">{ownerWaitingCount}</div></div></CardContent></Card>
        <Card className="border-emerald-200 bg-emerald-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><Users className="size-8 rounded-md bg-emerald-700 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-emerald-900">Answers Ready</div><div className="text-2xl font-semibold">{submittedCount}</div></div></CardContent></Card>
        <Card className="border-rose-200 bg-rose-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><AlertCircle className="size-8 rounded-md bg-rose-700 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-rose-900">Payment Blockers</div><div className="text-2xl font-semibold">{checkoutBlockedCount}</div></div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Current Webstores</CardTitle></CardHeader>
        <CardContent className="p-0"><div className="divide-y">
          {storeItems.map((store) => <Link key={store.id} to={`/webstores/${store.id}`} className="grid grid-cols-1 gap-3 p-4 text-sm hover:bg-slate-50 md:grid-cols-[minmax(0,1fr)_180px_180px]" data-testid={`webstore-row-${store.id}`}><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><div className="font-medium">{store.name}</div>{store.status === "live" && <CheckCircle2 className="size-4 text-emerald-700" />}</div><div className="mt-1 text-xs text-muted-foreground">Type: {typeLabel(store.store_type)} - Setup: {formatLabel(store.setup_state || "not_started")}</div><div className="mt-2 text-xs font-medium text-sky-900">{actionForStore(store)}</div></div><div className="flex items-start md:justify-end"><Badge variant={statusTone(store.status)} className="w-fit capitalize">{formatLabel(store.status)}</Badge></div><div className="text-xs text-muted-foreground md:text-right"><div>{store.checkout_enabled ? "Checkout on" : "Checkout off"}</div>{!store.checkout_enabled && store.checkout_unavailable_reason && <div className="mt-1">{store.checkout_unavailable_reason}</div>}</div></Link>)}
          {stores.isLoading && <div className="p-4 text-sm text-muted-foreground">Loading...</div>}
          {!stores.isLoading && storeItems.length === 0 && <div className="p-8 text-center text-sm text-muted-foreground">No Webstores yet. Select New Webstore to create your first draft.</div>}
        </div></CardContent>
      </Card>
    </div>
  );
}
