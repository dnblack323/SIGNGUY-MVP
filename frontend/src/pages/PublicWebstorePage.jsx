import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Minus, Plus, ShoppingCart, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { centsToDollarsString } from "@/lib/format";
import { toast } from "sonner";
import { API_BASE } from "@/lib/apiBase";
import { WebstoreBrandingPreview } from "@/components/webstores/WebstoreBranding";

const API = API_BASE;

function productFulfillment(product) {
  return product.fulfillment_methods || [product.default_fulfillment_method || "pickup"];
}

function lineKey(productId, variant, personalization, fulfillmentMethod) {
  return [productId, JSON.stringify(variant || {}), JSON.stringify(personalization || {}), fulfillmentMethod || ""].join("::");
}

export default function PublicWebstorePage() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [cart, setCart] = useState({});
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [promoCode, setPromoCode] = useState("");
  const [donationCents, setDonationCents] = useState(0);
  const [quote, setQuote] = useState(null);
  const [quoteError, setQuoteError] = useState(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState({});
  const [personalization, setPersonalization] = useState({});
  const [selectedFulfillment, setSelectedFulfillment] = useState("");
  const [productChoiceError, setProductChoiceError] = useState(null);

  useEffect(() => {
    setData(null);
    setErr(null);
    setCart({});
    setQuote(null);
    axios.get(`${API}/public/webstores/${slug}`)
      .then((response) => setData(response.data))
      .catch((error) => setErr(error?.response?.data?.detail || "This Webstore is not available."));
  }, [slug]);

  const products = data?.products || [];
  const cartLines = useMemo(() => Object.values(cart).filter((line) => line.quantity > 0), [cart]);
  const cartPayload = useMemo(() => ({
    line_items: cartLines.map(({ product_id, quantity, variant, personalization, fulfillment_method }) => ({
      product_id,
      quantity,
      variant,
      personalization,
      fulfillment_method,
    })),
    donation_cents: Number(donationCents) || 0,
    promo_code: promoCode.trim() || undefined,
  }), [cartLines, donationCents, promoCode]);

  useEffect(() => {
    if (!data || !cartLines.length) {
      setQuote(null);
      setQuoteError(null);
      return undefined;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setQuoteLoading(true);
      setQuoteError(null);
      try {
        const response = await axios.post(`${API}/public/webstores/${slug}/cart-quote`, cartPayload);
        if (!cancelled) setQuote(response.data);
      } catch (error) {
        if (!cancelled) {
          setQuote(null);
          setQuoteError(error?.response?.data?.detail || "The cart could not be priced.");
        }
      } finally {
        if (!cancelled) setQuoteLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [cartPayload, cartLines.length, data, slug]);

  const openProduct = (product) => {
    const methods = productFulfillment(product);
    setSelectedProduct(product);
    setSelectedVariant(product.variants?.[0] || {});
    setPersonalization({});
    setSelectedFulfillment(product.default_fulfillment_method || (methods.length === 1 ? methods[0] : ""));
    setProductChoiceError(null);
  };
  const setLine = (line) => setCart((current) => ({ ...current, [line.key]: line }));
  const addProduct = (product, choices = {}) => {
    const methods = productFulfillment(product);
    const variant = choices.variant || {};
    const personalizationValues = choices.personalization || {};
    const fulfillmentMethod = choices.fulfillmentMethod || product.default_fulfillment_method || (methods.length === 1 ? methods[0] : "");
    if (product.variants?.length && !variant.id && !variant.name && !variant.sku && !variant.size && !variant.color && !variant.style && !variant.material && !Object.keys(variant.options || {}).length) {
      openProduct(product);
      return;
    }
    const missingFields = (product.personalization_fields || []).filter((field) => field.required && !String(personalizationValues[field.key] || "").trim());
    if (missingFields.length) {
      setProductChoiceError(`Complete: ${missingFields.map((field) => field.label || field.key).join(", ")}`);
      return;
    }
    if (!fulfillmentMethod) {
      openProduct(product);
      return;
    }
    const key = lineKey(product.id, variant, personalizationValues, fulfillmentMethod);
    setLine({ key, product_id: product.id, product, quantity: (cart[key]?.quantity || 0) + 1, variant, personalization: personalizationValues, fulfillment_method: fulfillmentMethod });
    setProductChoiceError(null);
    toast.success(`${product.name} added to cart`);
  };
  const updateQuantity = (line, quantity) => {
    if (quantity <= 0) {
      setCart((current) => { const next = { ...current }; delete next[line.key]; return next; });
      return;
    }
    setLine({ ...line, quantity: Math.min(99, quantity) });
  };

  if (err) return <div className="min-h-screen grid place-items-center p-6 text-sm text-rose-700" data-testid="public-webstore-error">{err}</div>;
  if (!data) return <div className="min-h-screen grid place-items-center p-6 text-sm text-muted-foreground">Loading...</div>;

  const publishedBranding = data.webstore.branding || {};
  const hasPublishedBranding = Object.keys(publishedBranding).length > 0;
  const cartConfig = data.webstore.cart_config || {};
  const selectedMethods = selectedProduct ? productFulfillment(selectedProduct) : [];

  return (
    <div className="min-h-screen bg-slate-50" data-testid="public-webstore-page">
      {hasPublishedBranding ? (
        <div className="max-w-6xl mx-auto px-4 py-4">
          <WebstoreBrandingPreview branding={publishedBranding} webstore={data.webstore} products={products} />
        </div>
      ) : (
        <header className="bg-white border-b">
          <div className="max-w-6xl mx-auto px-4 py-5">
            <h1 className="text-3xl font-semibold">{data.webstore.name}</h1>
            <p className="text-sm text-muted-foreground mt-1">{data.webstore.description || "Browse the approved Webstore catalog."}</p>
          </div>
        </header>
      )}
      {!data.webstore.checkout_enabled && (
        <div className="max-w-6xl mx-auto px-4 pt-3">
          <p className="text-xs text-amber-700" data-testid="webstore-checkout-disabled">{data.webstore.checkout_unavailable_reason || "Payment setup is not available yet."}</p>
        </div>
      )}
      {data.webstore.store_type === "fundraiser" && (data.webstore.fundraiser_progress?.goal_cents || cartConfig.fundraiser_goal_cents) > 0 && (
        <section className="max-w-6xl mx-auto px-4 pt-4" aria-labelledby="fundraiser-progress-heading" data-testid="fundraiser-progress">
          <Card>
            <CardContent className="space-y-2 py-4">
              <div className="flex items-center justify-between gap-3"><h2 id="fundraiser-progress-heading" className="font-semibold">Fundraiser progress</h2><span className="text-sm text-muted-foreground">{centsToDollarsString(data.webstore.fundraiser_progress?.completed_sales_cents || 0)} raised from completed sales</span></div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-emerald-600" role="progressbar" aria-label="Fundraiser progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.min(100, data.webstore.fundraiser_progress?.percent || 0)} style={{ width: `${Math.min(100, data.webstore.fundraiser_progress?.percent || 0)}%` }} /></div>
              <p className="text-xs text-muted-foreground">Goal: {centsToDollarsString(data.webstore.fundraiser_progress?.goal_cents || cartConfig.fundraiser_goal_cents)}. Cart donations are shown as unpaid and do not change this total.</p>
            </CardContent>
          </Card>
        </section>
      )}
      <main className="max-w-6xl mx-auto px-4 py-6 grid grid-cols-1 gap-5 lg:grid-cols-[1fr_360px]">
        <section className="space-y-4" aria-labelledby="public-catalog-heading">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 id="public-catalog-heading" className="text-xl font-semibold">Approved products</h2>
              <p className="text-sm text-muted-foreground">Choose products to add to your cart.</p>
            </div>
            {cartLines.length > 0 && <span className="text-sm text-muted-foreground">{cartLines.reduce((sum, line) => sum + line.quantity, 0)} item(s)</span>}
          </div>
          {!products.length ? (
            <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">Products will appear here when the Webstore is ready.</CardContent></Card>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {products.map((product) => (
                <Card key={product.id} data-testid={`public-product-${product.id}`}>
                  <CardHeader className="pb-3"><CardTitle className="text-base">{product.name}</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    {product.images?.[0]?.url && <img src={product.images[0].url} alt={product.images[0].alt_text || product.name} className="aspect-[4/3] w-full rounded-md object-cover" />}
                    <p className="min-h-10 text-sm text-muted-foreground">{product.description || product.product_type}</p>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-semibold">{centsToDollarsString(product.selling_price_cents)}</span>
                      <div className="flex gap-2">
                        <Button type="button" variant="outline" size="sm" onClick={() => openProduct(product)}>Details</Button>
                        <Button type="button" size="sm" onClick={() => addProduct(product)}><ShoppingCart className="mr-1 size-4" />Add</Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
          {selectedProduct && (
            <Card data-testid="public-product-detail">
              <CardHeader className="flex-row items-start justify-between gap-3"><div><CardTitle>{selectedProduct.name}</CardTitle><p className="mt-1 text-sm text-muted-foreground">{selectedProduct.full_description || selectedProduct.description}</p></div><Button type="button" variant="ghost" size="icon" title="Close product details" onClick={() => setSelectedProduct(null)}><X className="size-4" /></Button></CardHeader>
              <CardContent className="space-y-4">
                {selectedProduct.variants?.length > 0 && (
                  <div className="grid gap-1.5"><Label htmlFor="public-product-variant">Options</Label><Select value={JSON.stringify(selectedVariant)} onValueChange={(value) => setSelectedVariant(JSON.parse(value))}><SelectTrigger id="public-product-variant"><SelectValue /></SelectTrigger><SelectContent>{selectedProduct.variants.map((variant, index) => <SelectItem key={variant.id || index} value={JSON.stringify(variant)}>{variant.name || [variant.size, variant.color, variant.style].filter(Boolean).join(" / ") || `Option ${index + 1}`}</SelectItem>)}</SelectContent></Select></div>
                )}
                {selectedProduct.personalization_fields?.map((field) => <div key={field.key} className="grid gap-1.5"><Label htmlFor={`public-personalization-${field.key}`}>{field.label || field.key}{field.required ? " *" : ""}</Label><Input id={`public-personalization-${field.key}`} value={personalization[field.key] || ""} placeholder={field.placeholder || ""} maxLength={field.max_length || undefined} onChange={(event) => setPersonalization((current) => ({ ...current, [field.key]: event.target.value }))} /></div>)}
                {selectedMethods.length > 1 && <div className="grid gap-1.5"><Label htmlFor="public-fulfillment-method">Fulfillment</Label><Select value={selectedFulfillment} onValueChange={setSelectedFulfillment}><SelectTrigger id="public-fulfillment-method"><SelectValue placeholder="Choose pickup or shipping" /></SelectTrigger><SelectContent>{selectedMethods.map((method) => <SelectItem key={method} value={method}>{method === "pickup" ? "Pickup" : "Shipping"}</SelectItem>)}</SelectContent></Select></div>}
                {selectedProduct.pickup_instructions && selectedFulfillment === "pickup" && <p className="text-sm text-muted-foreground">{selectedProduct.pickup_instructions}</p>}
                {selectedFulfillment === "shipping" && <p className="text-sm text-muted-foreground">Shipping estimate: {centsToDollarsString(selectedProduct.shipping_cost_cents || 0)} per item.</p>}
                {productChoiceError && <p className="text-sm text-rose-700" role="alert">{productChoiceError}</p>}
                <Button type="button" onClick={() => addProduct(selectedProduct, { variant: selectedVariant, personalization, fulfillmentMethod: selectedFulfillment })}><ShoppingCart className="mr-1 size-4" />Add to cart</Button>
              </CardContent>
            </Card>
          )}
        </section>
        <aside className="h-fit lg:sticky lg:top-4" aria-labelledby="public-cart-heading">
          <Card>
            <CardHeader><CardTitle id="public-cart-heading" className="flex items-center gap-2"><ShoppingCart className="size-4" />Cart summary</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {!cartLines.length ? <p className="text-sm text-muted-foreground">Your cart is empty.</p> : (
                <div className="space-y-3">
                  {cartLines.map((line) => <div key={line.key} className="flex items-start gap-2 border-b pb-3"><div className="min-w-0 flex-1"><p className="text-sm font-medium">{line.product.name}</p><p className="text-xs text-muted-foreground">{line.fulfillment_method || "Fulfillment selection needed"}</p><div className="mt-2 flex items-center gap-1"><Button type="button" variant="outline" size="icon" title="Decrease quantity" onClick={() => updateQuantity(line, line.quantity - 1)}><Minus className="size-3" /></Button><Input aria-label={`${line.product.name} quantity`} className="h-8 w-14 text-center" type="number" min="0" max="99" value={line.quantity} onChange={(event) => updateQuantity(line, Number(event.target.value) || 0)} /><Button type="button" variant="outline" size="icon" title="Increase quantity" onClick={() => updateQuantity(line, line.quantity + 1)}><Plus className="size-3" /></Button></div></div><Button type="button" variant="ghost" size="icon" title="Remove item" onClick={() => updateQuantity(line, 0)}><Trash2 className="size-4" /></Button></div>)}
                  {cartConfig.donation_enabled && <div className="grid gap-1.5"><Label htmlFor="public-donation">Optional donation</Label><Input id="public-donation" type="number" min="0" value={donationCents / 100} onChange={(event) => setDonationCents(Math.max(0, Math.round((Number(event.target.value) || 0) * 100)))} /><p className="text-xs text-muted-foreground">Entered in dollars; the server validates the final amount.</p></div>}
                  {cartConfig.promo_codes_enabled && <div className="grid gap-1.5"><Label htmlFor="public-promo">Promo code</Label><Input id="public-promo" value={promoCode} onChange={(event) => setPromoCode(event.target.value)} placeholder="Optional" /></div>}
                  {quoteError && <p className="text-sm text-rose-700" role="alert">{quoteError}</p>}
                  {quoteLoading && <p className="text-xs text-muted-foreground" aria-live="polite">Updating cart total...</p>}
                  {quote && <div className="space-y-1 border-t pt-3 text-sm"><div className="flex justify-between"><span>Merchandise</span><span>{centsToDollarsString(quote.subtotal_cents)}</span></div><div className="flex justify-between"><span>Shipping estimate</span><span>{centsToDollarsString(quote.shipping_cents)}</span></div>{quote.donation_cents > 0 && <div className="flex justify-between"><span>Donation</span><span>{centsToDollarsString(quote.donation_cents)}</span></div>}{quote.discount_cents > 0 && <div className="flex justify-between text-emerald-700"><span>Discount</span><span>-{centsToDollarsString(quote.discount_cents)}</span></div>}<div className="flex justify-between border-t pt-2 font-semibold"><span>Current total</span><span data-testid="public-cart-total">{centsToDollarsString(quote.total_cents)}</span></div><p className="pt-2 text-xs text-muted-foreground">Payment and order creation are unavailable until the later commerce stage.</p></div>}
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </main>
    </div>
  );
}
