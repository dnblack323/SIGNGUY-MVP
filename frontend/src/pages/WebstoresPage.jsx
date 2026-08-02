import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Clock3, Mail, RotateCcw, Store, Users } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { extractError } from "@/lib/api";
import { createWebstore, createWebstoreOwner, listWebstores, sendWebstoreQuestionnaire } from "@/lib/webstores";
import { useAuth } from "@/auth/AuthContext";
import { toast } from "sonner";

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
  const status = store.setup_state || store.status;
  if (["questionnaire_sent", "waiting_on_store_owner"].includes(status)) return "Waiting on owner questionnaire";
  if (status === "questionnaire_submitted") return "Review answers and apply setup fields";
  if (["products_selected", "ai_setup_ready", "artwork_needs_review"].includes(status)) return "Finish product setup and mockups";
  if (["store_packet_generated", "sent_for_approval"].includes(status)) return "Review owner approval packet";
  if (store.status === "live") return store.checkout_enabled ? "Live and accepting orders" : "Live but checkout is off";
  if (!store.checkout_enabled && ["launch_ready", "owner_approved"].includes(store.status)) return "Payment setup incomplete";
  return "Continue setup";
}

const WEBSTORE_TYPES = [
  { value: "b2b", label: "B2B" },
  { value: "fundraiser", label: "Fundraiser" },
  { value: "event", label: "Event" },
  { value: "promotional", label: "Promotional" },
  { value: "employee", label: "Employee" },
  { value: "general", label: "General" },
];

export default function WebstoresPage() {
  const { hasPerm } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const canRead = hasPerm("webstore:read");
  const canManage = hasPerm("webstore:manage");
  const emptyForm = {
    ownerName: "",
    ownerEmail: "",
    storeName: "",
    slug: "",
    storeType: "general",
    managerEmails: "",
    additionalOwnerEmails: "",
  };
  const [form, setForm] = useState(emptyForm);
  const [storeNameAutoFilled, setStoreNameAutoFilled] = useState(true);
  const [wizardStep, setWizardStep] = useState(0);
  const stores = useQuery({ queryKey: ["webstores"], queryFn: () => listWebstores(), enabled: canRead });
  const suggestedStoreName = (ownerName) => ownerName.trim() ? `${ownerName.trim()} Store` : "";
  const selectedType = WEBSTORE_TYPES.find((type) => type.value === form.storeType) || WEBSTORE_TYPES[5];
  const canContinueOwner = Boolean(form.ownerName.trim() && form.ownerEmail.trim());
  const canContinueStore = Boolean(form.storeName.trim() && form.storeType);
  const createFlow = useMutation({
    mutationFn: async () => {
      const owner = await createWebstoreOwner({ name: form.ownerName, email: form.ownerEmail, create_portal_identity: false });
      const store = await createWebstore({
        owner_id: owner.id,
        name: form.storeName,
        slug: form.slug || undefined,
        store_type: form.storeType,
        manager_emails: form.managerEmails.split(",").map((e) => e.trim()).filter(Boolean),
        additional_owner_emails: form.additionalOwnerEmails.split(",").map((e) => e.trim()).filter(Boolean),
        idempotency_key: `webstore-create-${form.ownerEmail}-${form.storeName}`.toLowerCase(),
        send_owner_invitation: false,
      });
      const questionnaire = await sendWebstoreQuestionnaire(store.id, { email: form.ownerEmail, name: form.ownerName });
      return { store, questionnaire };
    },
    onSuccess: async ({ store, questionnaire }) => {
      toast.success(questionnaire?.email_sent ? "Webstore created and questionnaire sent" : "Webstore created; questionnaire link is ready");
      setForm(emptyForm);
      setStoreNameAutoFilled(true);
      setWizardStep(0);
      await qc.invalidateQueries({ queryKey: ["webstores"] });
      navigate(`/webstores/${store.id}`);
    },
    onError: (err) => toast.error(extractError(err)),
  });
  const updateOwnerName = (ownerName) => {
    const next = { ...form, ownerName };
    if (storeNameAutoFilled) next.storeName = suggestedStoreName(ownerName);
    setForm(next);
  };
  const storeItems = stores.data?.items || [];
  const ownerWaitingCount = storeItems.filter((store) => ["questionnaire_sent", "waiting_on_store_owner"].includes(store.setup_state || store.status)).length;
  const submittedCount = storeItems.filter((store) => (store.setup_state || store.status) === "questionnaire_submitted").length;
  const checkoutBlockedCount = storeItems.filter((store) => !store.checkout_enabled && ["launch_ready", "owner_approved", "live"].includes(store.status)).length;

  if (!canRead) {
    return (
      <div className="space-y-4" data-testid="webstores-page">
        <PageHeader title="Webstores" subtitle="Tenant Webstores are available to authorized owner and admin accounts." />
        <Alert><Store className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account does not include Webstores access.</AlertDescription></Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="webstores-page">
      <PageHeader
        title="Webstores"
        subtitle="Create and manage customer Webstores from intake through launch."
        actions={<Button variant="outline" size="sm" onClick={() => stores.refetch()}><RotateCcw className="size-4 mr-2" />Refresh</Button>}
      />

      <div className="grid gap-3 md:grid-cols-4" data-testid="webstores-dashboard-cards">
        <Card className="border-sky-200 bg-sky-50/60">
          <CardContent className="flex items-center gap-3 p-4 text-sm">
            <Store className="size-8 rounded-md bg-sky-700 p-1.5 text-white" />
            <div><div className="text-xs font-medium uppercase text-sky-900">Current Webstores</div><div className="text-2xl font-semibold">{storeItems.length}</div></div>
          </CardContent>
        </Card>
        <Card className="border-amber-200 bg-amber-50/60">
          <CardContent className="flex items-center gap-3 p-4 text-sm">
            <Clock3 className="size-8 rounded-md bg-amber-600 p-1.5 text-white" />
            <div><div className="text-xs font-medium uppercase text-amber-900">Waiting On Owner</div><div className="text-2xl font-semibold">{ownerWaitingCount}</div></div>
          </CardContent>
        </Card>
        <Card className="border-emerald-200 bg-emerald-50/60">
          <CardContent className="flex items-center gap-3 p-4 text-sm">
            <Users className="size-8 rounded-md bg-emerald-700 p-1.5 text-white" />
            <div><div className="text-xs font-medium uppercase text-emerald-900">Answers Ready</div><div className="text-2xl font-semibold">{submittedCount}</div></div>
          </CardContent>
        </Card>
        <Card className="border-rose-200 bg-rose-50/60">
          <CardContent className="flex items-center gap-3 p-4 text-sm">
            <AlertCircle className="size-8 rounded-md bg-rose-700 p-1.5 text-white" />
            <div><div className="text-xs font-medium uppercase text-rose-900">Payment Blockers</div><div className="text-2xl font-semibold">{checkoutBlockedCount}</div></div>
          </CardContent>
        </Card>
      </div>

      {canManage && (
        <Card className="border-sky-200 bg-sky-50/40">
          <CardHeader><CardTitle className="text-base">Create Webstore</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2 md:grid-cols-3">
              {["Owner", "Store", "Send"].map((label, index) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => setWizardStep(index)}
                  className={`rounded-md border px-3 py-2 text-left text-sm ${wizardStep === index ? "border-sky-600 bg-sky-700 text-white" : index < wizardStep ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "bg-white text-slate-600"}`}
                >
                  <span className="font-semibold">{index + 1}. {label}</span>
                </button>
              ))}
            </div>

            {wizardStep === 0 && (
              <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
                <div className="grid gap-1.5"><Label>Owner or organization</Label><Input value={form.ownerName} onChange={(e) => updateOwnerName(e.target.value)} placeholder="ABC Boosters" data-testid="webstore-owner-name" /></div>
                <div className="grid gap-1.5"><Label>Owner email</Label><Input type="email" value={form.ownerEmail} onChange={(e) => setForm({ ...form, ownerEmail: e.target.value })} data-testid="webstore-owner-email" /></div>
                <Button className="bg-sky-700 hover:bg-sky-800" disabled={!canContinueOwner} onClick={() => setWizardStep(1)}>Next</Button>
              </div>
            )}

            {wizardStep === 1 && (
              <div className="grid gap-3 lg:grid-cols-[1fr_1fr_1fr_auto] lg:items-end">
                <div className="grid gap-1.5">
                  <Label>Type</Label>
                  <Select value={form.storeType} onValueChange={(storeType) => setForm({ ...form, storeType })}>
                    <SelectTrigger data-testid="webstore-type"><SelectValue /></SelectTrigger>
                    <SelectContent>{WEBSTORE_TYPES.map((type) => <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5"><Label>Store name</Label><Input value={form.storeName} onChange={(e) => { setStoreNameAutoFilled(false); setForm({ ...form, storeName: e.target.value }); }} placeholder="ABC Boosters Store" data-testid="webstore-name" /></div>
                <div className="grid gap-1.5"><Label>Public link ending</Label><Input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} placeholder="auto-created if blank" data-testid="webstore-slug" /></div>
                <Button className="bg-sky-700 hover:bg-sky-800" disabled={!canContinueStore} onClick={() => setWizardStep(2)}>Next</Button>
              </div>
            )}

            {wizardStep === 2 && (
              <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-end">
                <div className="rounded-md border bg-white p-3 text-sm">
                  <div className="font-semibold">{form.storeName || "New Webstore"}</div>
                  <div className="text-muted-foreground">{selectedType.label} for {form.ownerName || "the store owner"}</div>
                  <div className="mt-2 text-xs text-sky-900">
                    After creation, the app emails the {selectedType.label} questionnaire. The owner sees what to expect, submits answers, and the shop gets notified to review/apply answers, add mockups, finish products, and prepare the launch packet.
                  </div>
                </div>
                <Button className="bg-sky-700 hover:bg-sky-800" disabled={createFlow.isPending || !canContinueOwner || !canContinueStore} onClick={() => createFlow.mutate()} data-testid="webstore-create">
                  {createFlow.isPending ? <RotateCcw className="size-4 mr-2 animate-spin" /> : <Mail className="size-4 mr-2" />}Create and Send Questionnaire
                </Button>
                <div className="grid gap-1.5 lg:col-span-2"><Label>Managers</Label><Input value={form.managerEmails} onChange={(e) => setForm({ ...form, managerEmails: e.target.value })} placeholder="optional emails" data-testid="webstore-manager-emails" /></div>
              </div>
            )}

            <div className="text-xs text-sky-900">
              Public link ending means the last part of the store URL. Leave it blank and the app will make one from the store name.
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-base">Current Webstores</CardTitle></CardHeader>
        <CardContent className="p-0">
      <div className="divide-y">
        {storeItems.map((store) => (
          <Link key={store.id} to={`/webstores/${store.id}`} className="grid grid-cols-1 gap-3 p-4 text-sm hover:bg-slate-50 md:grid-cols-[minmax(0,1fr)_180px_180px]" data-testid={`webstore-row-${store.id}`}>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <div className="font-medium">{store.name}</div>
                {store.status === "live" && <CheckCircle2 className="size-4 text-emerald-700" />}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">Link ending: /{store.public_slug || store.slug} - Type: {typeLabel(store.store_type)} - Setup: {formatLabel(store.setup_state || "not_started")}</div>
              <div className="mt-2 text-xs font-medium text-sky-900">{actionForStore(store)}</div>
            </div>
            <div className="flex items-start md:justify-end">
              <Badge variant={statusTone(store.status)} className="w-fit capitalize">{formatLabel(store.status)}</Badge>
            </div>
            <div className="text-xs text-muted-foreground md:text-right">
              <div>{store.checkout_enabled ? "Checkout on" : "Checkout off"}</div>
              {!store.checkout_enabled && store.checkout_unavailable_reason && <div className="mt-1">{store.checkout_unavailable_reason}</div>}
            </div>
          </Link>
        ))}
        {stores.isLoading && <div className="p-4 text-sm text-muted-foreground">Loading...</div>}
        {!stores.isLoading && storeItems.length === 0 && <div className="p-4 text-sm text-muted-foreground">No Webstores yet.</div>}
      </div>
        </CardContent>
      </Card>
    </div>
  );
}
