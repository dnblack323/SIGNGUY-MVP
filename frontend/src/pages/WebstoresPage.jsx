import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Store, Mail, RotateCcw } from "lucide-react";
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
    targetLaunchAt: "",
    deadlineAt: "",
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
        target_launch_at: form.targetLaunchAt || undefined,
        deadline_at: form.deadlineAt || undefined,
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
        subtitle="Manage storefront setup, launch readiness, buyer orders, and owner approval."
        actions={<Button variant="outline" size="sm" onClick={() => stores.refetch()}><RotateCcw className="size-4 mr-2" />Refresh</Button>}
      />

      {canManage && (
        <Card className="border-sky-200 bg-sky-50/40">
          <CardHeader><CardTitle className="text-base">New Webstore Wizard</CardTitle></CardHeader>
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

      <div className="rounded border bg-white divide-y">
        {(stores.data?.items || []).map((store) => (
          <Link key={store.id} to={`/webstores/${store.id}`} className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-2 p-3 text-sm hover:bg-slate-50" data-testid={`webstore-row-${store.id}`}>
            <div>
              <div className="font-medium">{store.name}</div>
              <div className="text-xs text-muted-foreground">/{store.slug} - {store.store_type} - setup: {store.setup_state || "not_started"}</div>
            </div>
            <Badge variant={statusTone(store.status)} className="w-fit capitalize">{String(store.status).replace(/_/g, " ")}</Badge>
            <div className="text-xs text-muted-foreground md:text-right">{store.checkout_enabled ? "Checkout on" : "Checkout off"}</div>
          </Link>
        ))}
        {stores.isLoading && <div className="p-4 text-sm text-muted-foreground">Loading...</div>}
        {!stores.isLoading && (stores.data?.items || []).length === 0 && <div className="p-4 text-sm text-muted-foreground">No Webstores yet.</div>}
      </div>
    </div>
  );
}
