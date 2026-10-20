import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Clock3, Plus, RotateCcw, Store, Truck, Users } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listWebstores } from "@/lib/webstores";
import { useAuth } from "@/auth/AuthContext";
import { webstoreStatusLabel } from "@/components/webstores/detail/WebstoreDetailUtils";
import WebstoreFulfillmentSettingsDialog from "@/components/webstores/WebstoreFulfillmentSettingsDialog";
import WebstoreRequestDialog, { WEBSTORE_REQUEST_TYPES } from "@/components/webstores/WebstoreRequestDialog";

function statusTone(status) {
  if (status === "live") return "secondary";
  if (["closed", "archived"].includes(status)) return "destructive";
  return "outline";
}

function formatLabel(value) {
  return String(value || "").replace(/_/g, " ");
}

function typeLabel(value) {
  return WEBSTORE_REQUEST_TYPES.find((type) => type.value === value)?.label || formatLabel(value || "general");
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

export default function WebstoresPage() {
  const { hasPerm } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);
  const [fulfillmentOpen, setFulfillmentOpen] = useState(false);
  const canRead = hasPerm("webstore:read");
  const canManage = hasPerm("webstore:manage");
  const stores = useQuery({ queryKey: ["webstores"], queryFn: () => listWebstores(), enabled: canRead });
  const storeItems = stores.data?.items || [];
  const ownerWaitingCount = storeItems.filter((store) => ["questionnaire_sent", "waiting_on_store_owner"].includes(store.setup_state || store.status)).length;
  const submittedCount = storeItems.filter((store) => (store.setup_state || store.status) === "questionnaire_submitted").length;
  const checkoutBlockedCount = storeItems.filter((store) => !store.checkout_enabled && ["launch_ready", "owner_approved", "live"].includes(store.status)).length;

  const handleCreated = async (store) => {
    await qc.invalidateQueries({ queryKey: ["webstores"] });
    navigate(`/webstores/${store.id}`);
  };

  if (!canRead) return <div className="space-y-4" data-testid="webstores-page"><PageHeader title="Webstores" subtitle="Tenant Webstores are available to authorized owner and admin accounts." /><Alert><Store className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account does not include Webstores access.</AlertDescription></Alert></div>;

  return (
    <div className="space-y-4" data-testid="webstores-page">
      <PageHeader title="Webstores" subtitle="Create and manage customer Webstores from intake through launch." actions={<div className="flex flex-wrap gap-2">{canManage && <Button onClick={() => setCreateOpen(true)} data-testid="new-webstore-button"><Plus className="size-4 mr-2" />New Webstore request</Button>}{canManage && <Button variant="outline" size="sm" onClick={() => setFulfillmentOpen(true)} data-testid="webstore-fulfillment-settings-button"><Truck className="size-4 mr-2" />Fulfillment settings</Button>}<Button variant="outline" size="sm" onClick={() => stores.refetch()}><RotateCcw className="size-4 mr-2" />Refresh</Button></div>} />
      <WebstoreRequestDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={handleCreated} />
      <WebstoreFulfillmentSettingsDialog open={fulfillmentOpen} onOpenChange={setFulfillmentOpen} />

      <div className="grid gap-3 md:grid-cols-4" data-testid="webstores-dashboard-cards">
        <Card className="border-sky-200 bg-sky-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><Store className="size-8 rounded-md bg-sky-700 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-sky-900">Current Webstores</div><div className="text-2xl font-semibold">{storeItems.length}</div></div></CardContent></Card>
        <Card className="border-amber-200 bg-amber-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><Clock3 className="size-8 rounded-md bg-amber-600 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-amber-900">Waiting On Owner</div><div className="text-2xl font-semibold">{ownerWaitingCount}</div></div></CardContent></Card>
        <Card className="border-emerald-200 bg-emerald-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><Users className="size-8 rounded-md bg-emerald-700 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-emerald-900">Answers Ready</div><div className="text-2xl font-semibold">{submittedCount}</div></div></CardContent></Card>
        <Card className="border-rose-200 bg-rose-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><AlertCircle className="size-8 rounded-md bg-rose-700 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-rose-900">Payment Blockers</div><div className="text-2xl font-semibold">{checkoutBlockedCount}</div></div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Current Webstores</CardTitle></CardHeader>
        <CardContent className="p-0"><div className="divide-y">
          {storeItems.map((store) => <Link key={store.id} to={`/webstores/${store.id}`} className="grid grid-cols-1 gap-3 p-4 text-sm hover:bg-slate-50 md:grid-cols-[minmax(0,1fr)_180px_180px]" data-testid={`webstore-row-${store.id}`}><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><div className="font-medium">{store.name}</div>{store.status === "live" && <CheckCircle2 className="size-4 text-emerald-700" />}</div><div className="mt-1 text-xs text-muted-foreground">Type: {typeLabel(store.store_type)} - Setup: {formatLabel(store.setup_state || "not_started")}</div><div className="mt-2 text-xs font-medium text-sky-900">{actionForStore(store)}</div></div><div className="flex items-start md:justify-end"><Badge variant={statusTone(store.status)} className="w-fit capitalize">{webstoreStatusLabel(store.status)}</Badge></div><div className="text-xs text-muted-foreground md:text-right"><div>{store.checkout_enabled ? "Checkout on" : "Checkout off"}</div>{!store.checkout_enabled && store.checkout_unavailable_reason && <div className="mt-1">{store.checkout_unavailable_reason}</div>}</div></Link>)}
          {stores.isLoading && <div className="p-4 text-sm text-muted-foreground">Loading...</div>}
          {!stores.isLoading && storeItems.length === 0 && <div className="p-8 text-center text-sm text-muted-foreground">No Webstores yet. Select New Webstore request to record your first one.</div>}
        </div></CardContent>
      </Card>
    </div>
  );
}
