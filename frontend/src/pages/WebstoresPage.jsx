import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Clock3, Plus, RotateCcw, Store, Truck, Users } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api, { extractError } from "@/lib/api";
import { listWebstores } from "@/lib/webstores";
import { useAuth } from "@/auth/AuthContext";
import WebstoreFulfillmentSettingsDialog from "@/components/webstores/WebstoreFulfillmentSettingsDialog";
import WebstoreRequestDialog, { WEBSTORE_REQUEST_TYPES } from "@/components/webstores/WebstoreRequestDialog";

function stageTone(stage) {
  if (stage === "live") return "secondary";
  if (["closed", "archived"].includes(stage)) return "destructive";
  return "outline";
}

function formatLabel(value) {
  return String(value || "").replace(/_/g, " ");
}

function typeLabel(value) {
  return WEBSTORE_REQUEST_TYPES.find((type) => type.value === value)?.label || formatLabel(value || "general");
}

function formatUpdated(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
}

// The stage filter uses the backend stage labels; the list carries them on each row.
const ALL = "all";

export default function WebstoresPage() {
  const { hasPerm, user } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);
  const [fulfillmentOpen, setFulfillmentOpen] = useState(false);
  const [stageFilter, setStageFilter] = useState(ALL);
  const [needsMe, setNeedsMe] = useState(false);
  const canRead = hasPerm("webstore:read");
  const canManage = hasPerm("webstore:manage");
  const stores = useQuery({ queryKey: ["webstores"], queryFn: () => listWebstores(), enabled: canRead });
  const { mutate: recoverTasks, isPending: recovering, data: recovery, error: recoveryError } = useMutation({
    mutationFn: async () => (await api.post("/webstores/reconcile-next-actions")).data,
    onSettled: async () => {
      await qc.invalidateQueries({ queryKey: ["webstores"] });
      await qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
  useEffect(() => { if (canManage) recoverTasks(); }, [canManage, recoverTasks]);
  const users = useQuery({ queryKey: ["users"], queryFn: async () => (await api.get("/users")).data, enabled: canRead });
  const userItems = Array.isArray(users.data) ? users.data : users.data?.items || [];
  const userName = (userId) => {
    const match = userItems.find((u) => u.id === userId);
    return match ? match.name || match.email : userId ? "Team member" : "Unassigned";
  };
  const storeItems = stores.data?.items || [];
  // Counts come from the one backend next action, not from frontend status rules.
  const ownerWaitingCount = storeItems.filter((store) => store.next_action?.actor === "owner").length;
  const submittedCount = storeItems.filter((store) => store.next_action?.key === "review_questionnaire").length;
  const checkoutBlockedCount = storeItems.filter((store) => store.next_action?.key === "payment_ready").length;
  const stageOptions = [...new Map(storeItems.filter((store) => store.stage).map((store) => [store.stage.key, store.stage.staff_label])).entries()];
  const needsMeStore = (store) =>
    store.next_action?.actor === "shop" && store.next_action?.requires_staff_task !== false && (!store.assignee_user_id || store.assignee_user_id === user?.id);
  const visibleStores = storeItems.filter(
    (store) => (stageFilter === ALL || store.stage?.key === stageFilter) && (!needsMe || needsMeStore(store)),
  );

  const handleCreated = async (store) => {
    await qc.invalidateQueries({ queryKey: ["webstores"] });
    navigate(`/webstores/${store.id}`);
  };

  if (!canRead) return <div className="space-y-4" data-testid="webstores-page"><PageHeader title="Webstores" subtitle="Tenant Webstores are available to authorized owner and admin accounts." /><Alert><Store className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account does not include Webstores access.</AlertDescription></Alert></div>;

  return (
    <div className="space-y-4" data-testid="webstores-page">
      <PageHeader title="Webstores" subtitle="Create and manage customer Webstores from intake through launch." actions={<div className="flex flex-wrap gap-2">{canManage && <Button onClick={() => setCreateOpen(true)} data-testid="new-webstore-button"><Plus className="size-4 mr-2" />New Webstore request</Button>}{canManage && <Button variant="outline" size="sm" onClick={() => setFulfillmentOpen(true)} data-testid="webstore-fulfillment-settings-button"><Truck className="size-4 mr-2" />Fulfillment settings</Button>}<Button variant="outline" size="sm" disabled={recovering} onClick={() => canManage ? recoverTasks() : stores.refetch()}><RotateCcw className="size-4 mr-2" />Refresh</Button></div>} />
      {(recoveryError || recovery?.failed || recovery?.pending) ? <Alert data-testid="webstore-recovery-warning"><AlertCircle className="size-4" /><AlertTitle>Some Webstore tasks still need to refresh</AlertTitle><AlertDescription>{recoveryError ? extractError(recoveryError) : "A task update is pending or could not finish. Select Refresh to retry."}</AlertDescription></Alert> : null}
      <WebstoreRequestDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={handleCreated} />
      <WebstoreFulfillmentSettingsDialog open={fulfillmentOpen} onOpenChange={setFulfillmentOpen} />

      <div className="grid gap-3 md:grid-cols-4" data-testid="webstores-dashboard-cards">
        <Card className="border-sky-200 bg-sky-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><Store className="size-8 rounded-md bg-sky-700 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-sky-900">Current Webstores</div><div className="text-2xl font-semibold">{storeItems.length}</div></div></CardContent></Card>
        <Card className="border-amber-200 bg-amber-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><Clock3 className="size-8 rounded-md bg-amber-600 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-amber-900">Waiting On Owner</div><div className="text-2xl font-semibold">{ownerWaitingCount}</div></div></CardContent></Card>
        <Card className="border-emerald-200 bg-emerald-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><Users className="size-8 rounded-md bg-emerald-700 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-emerald-900">Answers Ready</div><div className="text-2xl font-semibold">{submittedCount}</div></div></CardContent></Card>
        <Card className="border-rose-200 bg-rose-50/60"><CardContent className="flex items-center gap-3 p-4 text-sm"><AlertCircle className="size-8 rounded-md bg-rose-700 p-1.5 text-white" /><div><div className="text-xs font-medium uppercase text-rose-900">Payment Blockers</div><div className="text-2xl font-semibold">{checkoutBlockedCount}</div></div></CardContent></Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-base">Current Webstores</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={stageFilter} onValueChange={setStageFilter}>
              <SelectTrigger className="h-8 w-48" data-testid="webstores-stage-filter"><SelectValue placeholder="All stages" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All stages</SelectItem>
                {stageOptions.map(([key, label]) => <SelectItem key={key} value={key}>{label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button variant={needsMe ? "default" : "outline"} size="sm" aria-pressed={needsMe} onClick={() => setNeedsMe((on) => !on)} data-testid="webstores-needs-me">Needs me</Button>
          </div>
        </CardHeader>
        <CardContent className="p-0"><div className="divide-y">
          <div className="hidden gap-3 px-4 py-2 text-xs font-medium uppercase text-muted-foreground md:grid md:grid-cols-[minmax(0,1.2fr)_160px_minmax(0,1.4fr)_150px_100px]"><div>Webstore</div><div>Stage</div><div>Next action</div><div>Assignee</div><div className="text-right">Updated</div></div>
          {visibleStores.map((store) => <Link key={store.id} to={`/webstores/${store.id}`} className="grid grid-cols-1 gap-3 p-4 text-sm hover:bg-slate-50 md:grid-cols-[minmax(0,1.2fr)_160px_minmax(0,1.4fr)_150px_100px]" data-testid={`webstore-row-${store.id}`}><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><div className="font-medium">{store.name}</div>{store.stage?.key === "live" && <CheckCircle2 className="size-4 text-emerald-700" />}</div><div className="mt-1 text-xs text-muted-foreground">{typeLabel(store.store_type)}{store.checkout_enabled ? " - Checkout on" : ""}</div></div><div><Badge variant={stageTone(store.stage?.key)} className="w-fit" data-testid={`webstore-row-stage-${store.id}`}>{store.stage?.staff_label || "Request received"}</Badge></div><div className="min-w-0"><div className={`text-xs font-medium ${store.next_action?.actor === "owner" ? "text-amber-800" : "text-sky-900"}`} data-testid={`webstore-row-next-${store.id}`}>{store.next_action?.actor === "owner" ? "Waiting on owner: " : ""}{store.next_action?.staff_text}</div></div><div className="text-xs text-muted-foreground" data-testid={`webstore-row-assignee-${store.id}`}>{userName(store.assignee_user_id)}</div><div className="text-xs text-muted-foreground md:text-right">{formatUpdated(store.updated_at || store.created_at)}</div></Link>)}
          {stores.isLoading && <div className="p-4 text-sm text-muted-foreground">Loading...</div>}
          {!stores.isLoading && storeItems.length === 0 && <div className="p-8 text-center text-sm text-muted-foreground">No Webstores yet. Select New Webstore request to record your first one.</div>}
          {!stores.isLoading && storeItems.length > 0 && visibleStores.length === 0 && <div className="p-8 text-center text-sm text-muted-foreground" data-testid="webstores-filter-empty">No Webstores match these filters.</div>}
        </div></CardContent>
      </Card>
    </div>
  );
}
