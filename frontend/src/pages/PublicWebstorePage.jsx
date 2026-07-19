import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { centsToDollarsString } from "@/lib/format";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PublicWebstorePage() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [cart, setCart] = useState({});
  const [buyer, setBuyer] = useState({ buyer_name: "", buyer_email: "", buyer_phone: "" });
  const [done, setDone] = useState(null);
  useEffect(() => {
    axios.get(`${API}/public/webstores/${slug}`).then((r) => setData(r.data)).catch((e) => setErr(e?.response?.data?.detail || "This Webstore is not available."));
  }, [slug]);
  const total = useMemo(() => (data?.products || []).reduce((sum, p) => sum + (cart[p.id] || 0) * (p.selling_price_cents || 0), 0), [cart, data]);
  async function checkout() {
    try {
      const line_items = Object.entries(cart).filter(([, quantity]) => quantity > 0).map(([product_id, quantity]) => ({ product_id, quantity }));
      const r = await axios.post(`${API}/public/webstores/${slug}/buyer-orders`, { ...buyer, line_items, idempotency_key: crypto.randomUUID() });
      setDone(r.data.buyer_order);
      toast.success("Order received");
    } catch (e) { toast.error(e?.response?.data?.detail || "Checkout failed"); }
  }
  if (err) return <div className="min-h-screen grid place-items-center p-6 text-sm text-rose-700" data-testid="public-webstore-error">{err}</div>;
  if (!data) return <div className="min-h-screen grid place-items-center p-6 text-sm text-muted-foreground">Loading...</div>;
  if (done) return <div className="min-h-screen grid place-items-center p-6"><Card><CardHeader><CardTitle>Order received</CardTitle></CardHeader><CardContent>Reference: <span className="font-mono">{done.id}</span></CardContent></Card></div>;
  return (
    <div className="min-h-screen bg-slate-50" data-testid="public-webstore-page">
      <header className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 py-5">
          <h1 className="text-3xl font-semibold">{data.webstore.name}</h1>
          <p className="text-sm text-muted-foreground mt-1">{data.webstore.description || "Select products and submit your order."}</p>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {(data.products || []).map((p) => (
            <Card key={p.id}>
              <CardHeader><CardTitle className="text-base">{p.name}</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground min-h-10">{p.description || p.product_type}</p>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold">{centsToDollarsString(p.selling_price_cents)}</span>
                  <Input className="w-24" type="number" min="0" value={cart[p.id] || 0} onChange={(e) => setCart({ ...cart, [p.id]: Math.max(0, Number(e.target.value) || 0) })} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        <Card className="h-fit">
          <CardHeader><CardTitle className="text-base">Checkout</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-1.5"><Label>Name</Label><Input value={buyer.buyer_name} onChange={(e) => setBuyer({ ...buyer, buyer_name: e.target.value })} /></div>
            <div className="grid gap-1.5"><Label>Email</Label><Input type="email" value={buyer.buyer_email} onChange={(e) => setBuyer({ ...buyer, buyer_email: e.target.value })} /></div>
            <div className="grid gap-1.5"><Label>Phone</Label><Input value={buyer.buyer_phone} onChange={(e) => setBuyer({ ...buyer, buyer_phone: e.target.value })} /></div>
            <div className="flex items-center justify-between border-t pt-3"><span className="text-sm text-muted-foreground">Subtotal</span><span className="font-semibold">{centsToDollarsString(total)}</span></div>
            <Button className="w-full" disabled={!buyer.buyer_name || !buyer.buyer_email || total <= 0} onClick={checkout}><ShoppingCart className="size-4 mr-2" />Submit order</Button>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
