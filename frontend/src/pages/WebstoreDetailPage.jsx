import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, PackagePlus, Send, ShieldCheck } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { centsToDollarsString } from "@/lib/format";
import { extractError } from "@/lib/api";
import {
  createProductFromTemplate,
  generateLaunchPacket,
  getLaunchReadiness,
  getWebstore,
  getWebstoreReports,
  listProductTemplates,
  sendLaunchPacket,
  setWebstoreStatus,
  updateWebstore,
} from "@/lib/webstores";
import { toast } from "sonner";

export default function WebstoreDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [templateId, setTemplateId] = useState("");
  const [promo, setPromo] = useState("");
  const detail = useQuery({ queryKey: ["webstore", id], queryFn: () => getWebstore(id), enabled: !!id });
  const templates = useQuery({ queryKey: ["webstore-product-templates"], queryFn: listProductTemplates });
  const readiness = useQuery({ queryKey: ["webstore-readiness", id], queryFn: () => getLaunchReadiness(id), enabled: !!id });
  const reports = useQuery({ queryKey: ["webstore-reports", id], queryFn: () => getWebstoreReports(id), enabled: !!id });
  const store = detail.data?.webstore;
  const activePacket = useMemo(() => (detail.data?.launch_packets || [])[0], [detail.data]);
  const refresh = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["webstore", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-readiness", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-reports", id] }),
    ]);
  };
  const addProduct = useMutation({
    mutationFn: () => createProductFromTemplate(id, { source_template_id: templateId, status: "active", public: true }),
    onSuccess: async () => { toast.success("Product added"); setTemplateId(""); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const saveGate = useMutation({
    mutationFn: (payload) => updateWebstore(id, payload),
    onSuccess: async () => { toast.success("Readiness updated"); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const packet = useMutation({
    mutationFn: () => generateLaunchPacket(id, { promotion_copy: promo }),
    onSuccess: async () => { toast.success("Launch packet generated"); setPromo(""); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const sendPacket = useMutation({
    mutationFn: () => sendLaunchPacket(id, activePacket.id),
    onSuccess: async () => { toast.success("Launch packet sent"); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const launch = useMutation({
    mutationFn: () => setWebstoreStatus(id, "live"),
    onSuccess: async () => { toast.success("Webstore launched"); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });

  if (detail.isLoading) return <div className="p-6 text-sm text-muted-foreground">Loading...</div>;
  if (!store) return <div className="p-6 text-sm text-rose-700">Webstore not found.</div>;

  return (
    <div className="space-y-4" data-testid="webstore-detail-page">
      <PageHeader
        title={store.name}
        subtitle={`/${store.slug} · ${String(store.status).replace(/_/g, " ")}`}
        actions={<Button asChild variant="outline" size="sm"><Link to={store.public_url || `/p/webstores/${store.slug}`}><ExternalLink className="size-4 mr-2" />Public</Link></Button>}
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Launch Gates</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            {Object.entries(readiness.data?.checks || {}).map(([key, ok]) => (
              <div className="flex items-center justify-between gap-3" key={key}>
                <span className="capitalize text-muted-foreground">{key.replace(/_/g, " ")}</span>
                <Badge variant={ok ? "secondary" : "outline"}>{ok ? "Ready" : "Missing"}</Badge>
              </div>
            ))}
            <div className="flex items-center gap-2 pt-2">
              <Checkbox checked={!!store.terms_fee_acknowledged} onCheckedChange={(checked) => saveGate.mutate({ terms_fee_acknowledged: !!checked })} id="fee-ack" />
              <Label htmlFor="fee-ack">Terms and fees acknowledged</Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox checked={!!store.stripe_payment_ready} onCheckedChange={(checked) => saveGate.mutate({ stripe_payment_ready: !!checked })} id="payment-ready" />
              <Label htmlFor="payment-ready">Payment boundary ready</Label>
            </div>
            <Button className="w-full" disabled={!readiness.data?.ready || launch.isPending} onClick={() => launch.mutate()} data-testid="webstore-launch">
              <ShieldCheck className="size-4 mr-2" />Launch
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Products</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Select value={templateId} onValueChange={setTemplateId}>
                <SelectTrigger data-testid="webstore-template-select"><SelectValue placeholder="Choose template" /></SelectTrigger>
                <SelectContent>{(templates.data || []).map((t) => <SelectItem value={t.id} key={t.id}>{t.template_name}</SelectItem>)}</SelectContent>
              </Select>
              <Button disabled={!templateId || addProduct.isPending} onClick={() => addProduct.mutate()}><PackagePlus className="size-4" /></Button>
            </div>
            <div className="rounded border divide-y">
              {(detail.data?.products || []).map((p) => (
                <div key={p.id} className="p-3 text-sm flex items-center justify-between gap-3">
                  <div><div className="font-medium">{p.name}</div><div className="text-xs text-muted-foreground">{p.status} · {p.public ? "public" : "private"}</div></div>
                  <span className="font-medium">{centsToDollarsString(p.selling_price_cents)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Launch Packet</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-1.5"><Label>Promotion copy</Label><Input value={promo} onChange={(e) => setPromo(e.target.value)} data-testid="webstore-promo" /></div>
            <div className="flex gap-2">
              <Button variant="outline" disabled={packet.isPending} onClick={() => packet.mutate()}><CheckCircle2 className="size-4 mr-2" />Generate</Button>
              <Button disabled={!activePacket || sendPacket.isPending} onClick={() => sendPacket.mutate()}><Send className="size-4 mr-2" />Send</Button>
            </div>
            {activePacket && <Alert><AlertTitle className="capitalize">{activePacket.status.replace(/_/g, " ")}</AlertTitle><AlertDescription>{activePacket.promotion_copy || "Packet snapshot is ready."}</AlertDescription></Alert>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Reporting</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div><div className="text-muted-foreground">Orders</div><div className="text-lg font-semibold">{reports.data?.order_count || 0}</div></div>
          <div><div className="text-muted-foreground">Gross sales</div><div className="text-lg font-semibold">{centsToDollarsString(reports.data?.gross_sales_cents)}</div></div>
          <div><div className="text-muted-foreground">Platform fee</div><div className="text-lg font-semibold">{centsToDollarsString(reports.data?.ledger_totals_cents?.platform_usage_fee)}</div></div>
          <div><div className="text-muted-foreground">Owner share</div><div className="text-lg font-semibold">{centsToDollarsString(reports.data?.ledger_totals_cents?.store_owner_share)}</div></div>
        </CardContent>
      </Card>
    </div>
  );
}
