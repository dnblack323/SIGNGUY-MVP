import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle2, Send } from "lucide-react";
import portalApi, { portalExtractError } from "@/portal/portalApi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { centsToDollarsString } from "@/lib/format";
import { toast } from "sonner";

export default function WebstoreOwnerPortalPage() {
  const { webstoreId } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [answers, setAnswers] = useState("");
  function load() {
    portalApi.get(`/portal/webstores/${webstoreId}`).then((r) => setData(r.data)).catch((e) => setErr(portalExtractError(e)));
  }
  useEffect(load, [webstoreId]);
  async function submitQuestionnaire() {
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/questionnaire`, { answers: { notes: answers }, known_products: [] });
      toast.success("Questionnaire submitted");
      load();
    } catch (e) { toast.error(portalExtractError(e)); }
  }
  async function approve() {
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/launch-packets/${data.launch_packet.id}/approve`);
      toast.success("Launch approved");
      load();
    } catch (e) { toast.error(portalExtractError(e)); }
  }
  if (err) return <div className="text-sm text-rose-700" data-testid="webstore-owner-error">{err}</div>;
  if (!data) return <div className="text-sm text-muted-foreground">Loading...</div>;
  return (
    <div className="space-y-4" data-testid="webstore-owner-portal-page">
      <div className="flex items-center justify-between gap-3">
        <div><h1 className="text-2xl font-semibold">{data.webstore.name}</h1><p className="text-sm text-muted-foreground">Review setup, products, and launch approval.</p></div>
        <Badge variant="outline" className="capitalize">{String(data.webstore.status).replace(/_/g, " ")}</Badge>
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Questionnaire</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Textarea rows={4} value={answers} onChange={(e) => setAnswers(e.target.value)} placeholder="Store goals, deadline, product ideas, and missing details" />
          <Button onClick={submitQuestionnaire}><Send className="size-4 mr-2" />Submit</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">Products</CardTitle></CardHeader>
        <CardContent className="rounded border divide-y p-0">
          {(data.products || []).map((p) => (
            <div key={p.id} className="p-3 flex items-center justify-between gap-3 text-sm">
              <div><div className="font-medium">{p.name}</div><div className="text-xs text-muted-foreground">{p.description || p.product_type}</div></div>
              <span className="font-medium">{centsToDollarsString(p.selling_price_cents)}</span>
            </div>
          ))}
        </CardContent>
      </Card>
      {data.launch_packet && (
        <Card>
          <CardHeader><CardTitle className="text-base">Launch Packet</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>{data.launch_packet.promotion_copy || "Launch packet is ready for approval."}</div>
            <Button disabled={data.launch_packet.status === "owner_approved"} onClick={approve}><CheckCircle2 className="size-4 mr-2" />Approve launch</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
