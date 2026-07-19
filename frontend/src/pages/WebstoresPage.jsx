import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Store, Plus, RotateCcw } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { extractError } from "@/lib/api";
import { createWebstore, createWebstoreOwner, listWebstores } from "@/lib/webstores";
import { useAuth } from "@/auth/AuthContext";
import { toast } from "sonner";

function statusTone(status) {
  if (status === "live") return "secondary";
  if (["closed", "archived"].includes(status)) return "destructive";
  return "outline";
}

export default function WebstoresPage() {
  const { hasPerm } = useAuth();
  const qc = useQueryClient();
  const canRead = hasPerm("webstore:read");
  const canManage = hasPerm("webstore:manage");
  const [form, setForm] = useState({ ownerName: "", ownerEmail: "", storeName: "", slug: "" });
  const stores = useQuery({ queryKey: ["webstores"], queryFn: () => listWebstores(), enabled: canRead });
  const createFlow = useMutation({
    mutationFn: async () => {
      const owner = await createWebstoreOwner({ name: form.ownerName, email: form.ownerEmail });
      return createWebstore({
        owner_id: owner.id,
        name: form.storeName,
        slug: form.slug || undefined,
        store_type: "fundraiser",
      });
    },
    onSuccess: async () => {
      toast.success("Webstore created");
      setForm({ ownerName: "", ownerEmail: "", storeName: "", slug: "" });
      await qc.invalidateQueries({ queryKey: ["webstores"] });
    },
    onError: (err) => toast.error(extractError(err)),
  });

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
        <Card>
          <CardHeader><CardTitle className="text-base">New Webstore</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
            <div className="grid gap-1.5"><Label>Owner name</Label><Input value={form.ownerName} onChange={(e) => setForm({ ...form, ownerName: e.target.value })} data-testid="webstore-owner-name" /></div>
            <div className="grid gap-1.5"><Label>Owner email</Label><Input type="email" value={form.ownerEmail} onChange={(e) => setForm({ ...form, ownerEmail: e.target.value })} data-testid="webstore-owner-email" /></div>
            <div className="grid gap-1.5"><Label>Store name</Label><Input value={form.storeName} onChange={(e) => setForm({ ...form, storeName: e.target.value })} data-testid="webstore-name" /></div>
            <div className="grid gap-1.5"><Label>Slug</Label><Input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} data-testid="webstore-slug" /></div>
            <Button disabled={createFlow.isPending || !form.ownerName || !form.ownerEmail || !form.storeName} onClick={() => createFlow.mutate()} data-testid="webstore-create">
              <Plus className="size-4 mr-2" />Create
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="rounded border bg-white divide-y">
        {(stores.data?.items || []).map((store) => (
          <Link key={store.id} to={`/webstores/${store.id}`} className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-2 p-3 text-sm hover:bg-slate-50" data-testid={`webstore-row-${store.id}`}>
            <div>
              <div className="font-medium">{store.name}</div>
              <div className="text-xs text-muted-foreground">/{store.slug} · {store.store_type}</div>
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
