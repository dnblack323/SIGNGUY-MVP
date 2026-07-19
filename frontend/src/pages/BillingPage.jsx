import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { extractError } from "@/lib/api";
import {
  createBillingPortalSession,
  createSetupPackageCheckout,
  createSubscriptionCheckout,
  ensureBillingAccount,
  getBillingState,
  listCommercialPrices,
  listCommercialProducts,
  scheduleSubscriptionCancellation,
  startExtendedTrialCheckout,
  startFreeTrial,
} from "@/lib/billing";
import { useAuth } from "@/auth/AuthContext";
import { CircleAlert, CreditCard, ExternalLink, RotateCcw, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const SETUP_PACKAGES = [
  { key: "diy", label: "DIY Guided Setup" },
  { key: "founder_kickstart", label: "Founder Kickstart Setup" },
  { key: "standard", label: "Standard Shop Setup" },
  { key: "full", label: "Full Optimization Setup" },
  { key: "white_glove", label: "White-Glove Implementation" },
];

function cents(centsValue, currency = "usd") {
  if (typeof centsValue !== "number") return "Not set";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: currency.toUpperCase() }).format(centsValue / 100);
}

function statusVariant(status) {
  if (["active", "trialing", "paid", "waived", "current"].includes(status)) return "secondary";
  if (["past_due", "restricted", "day_8_14_soft_restriction", "eligible_for_suspension"].includes(status)) return "outline";
  if (["suspended", "unpaid", "canceled"].includes(status)) return "destructive";
  return "outline";
}

function StatusBadge({ value }) {
  if (!value) return <Badge variant="outline">None</Badge>;
  return <Badge variant={statusVariant(value)} className="capitalize">{String(value).replace(/_/g, " ")}</Badge>;
}

function useBillingMutation(fn, successMessage) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: async (data) => {
      toast.success(successMessage);
      await qc.invalidateQueries({ queryKey: ["billing-state"] });
      return data;
    },
    onError: (err) => toast.error(extractError(err)),
  });
}

export default function BillingPage() {
  const { user, hasPerm } = useAuth();
  const [selectedPriceId, setSelectedPriceId] = useState("");
  const [selectedSetup, setSelectedSetup] = useState("diy");
  const returnUrl = typeof window === "undefined" ? "https://app.example/settings/subscriptions" : `${window.location.origin}/settings/subscriptions`;
  const canRead = hasPerm("subscription:read");
  const canManage = hasPerm("subscription:manage") && ["owner", "admin"].includes(user?.role);

  const billing = useQuery({ queryKey: ["billing-state"], queryFn: getBillingState, enabled: canRead });
  const products = useQuery({ queryKey: ["commercial-products"], queryFn: listCommercialProducts, enabled: canRead });
  const prices = useQuery({ queryKey: ["commercial-prices"], queryFn: listCommercialPrices, enabled: canRead });

  const productById = useMemo(() => {
    const map = new Map();
    for (const product of products.data || []) map.set(product.id, product);
    return map;
  }, [products.data]);

  const purchasablePrices = useMemo(() => {
    return (prices.data || []).filter((price) => {
      const product = productById.get(price.product_id);
      return product?.status === "active" && product?.publishable && price.is_active && price.is_public && price.approved_by_owner;
    });
  }, [prices.data, productById]);

  const ensureAccount = useBillingMutation(() => ensureBillingAccount({ terms_version: "2026-07" }), "Billing account created");
  const freeTrial = useBillingMutation(startFreeTrial, "Free trial started");
  const extendedTrial = useBillingMutation(
    () => startExtendedTrialCheckout({ successUrl: returnUrl, cancelUrl: returnUrl }),
    "Extended trial checkout created",
  );
  const checkout = useBillingMutation(
    () => createSubscriptionCheckout({ priceId: selectedPriceId, successUrl: returnUrl, cancelUrl: returnUrl }),
    "Subscription checkout created",
  );
  const setupCheckout = useBillingMutation(
    () => createSetupPackageCheckout({ packageKey: selectedSetup, successUrl: returnUrl, cancelUrl: returnUrl }),
    "Setup checkout created",
  );
  const cancel = useBillingMutation(
    () => scheduleSubscriptionCancellation(billing.data?.subscription?.id, "Tenant owner requested cancellation"),
    "Cancellation scheduled",
  );
  const portal = useMutation({
    mutationFn: () => createBillingPortalSession(returnUrl),
    onSuccess: (data) => {
      toast.success("Billing portal session created");
      if (data?.portal_url) window.location.assign(data.portal_url);
    },
    onError: (err) => toast.error(extractError(err)),
  });

  if (!canRead) {
    return (
      <div className="space-y-4" data-testid="billing-page">
        <PageHeader title="Subscriptions" subtitle="Commercial billing is available to subscription-enabled owner and admin accounts." />
        <Alert>
          <ShieldCheck className="size-4" />
          <AlertTitle>Access required</AlertTitle>
          <AlertDescription>Your account does not include subscription read access.</AlertDescription>
        </Alert>
      </div>
    );
  }

  const account = billing.data?.billing_account;
  const subscription = billing.data?.subscription;
  const trial = billing.data?.trial;
  const setupPurchases = billing.data?.setup_purchases || [];

  return (
    <div className="space-y-4" data-testid="billing-page">
      <PageHeader
        title="Subscriptions"
        subtitle="Tenant commercial billing, trials, setup purchases, and access state."
        actions={(
          <Button
            variant="outline"
            size="sm"
            onClick={() => billing.refetch()}
            disabled={billing.isFetching}
            data-testid="billing-refresh-button"
          >
            <RotateCcw className="size-4 mr-2" />Refresh
          </Button>
        )}
      />

      {!account && (
        <Alert data-testid="billing-account-empty">
          <CircleAlert className="size-4" />
          <AlertTitle>No billing account</AlertTitle>
          <AlertDescription>
            Owner or admin action is required before trials, checkout, and portal sessions can be created.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Billing Account</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Status</span>
              <StatusBadge value={account?.status} />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Billing email</span>
              <span className="truncate">{account?.billing_email || "Not set"}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Stripe customer</span>
              <span className="mono text-xs truncate">{account?.stripe_customer_id || "Not linked"}</span>
            </div>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button size="sm" disabled={!canManage || ensureAccount.isPending || !!account} onClick={() => ensureAccount.mutate()} data-testid="billing-create-account-button">
                Create account
              </Button>
              <Button size="sm" variant="outline" disabled={!canManage || !account || portal.isPending} onClick={() => portal.mutate()} data-testid="billing-portal-button">
                <ExternalLink className="size-4 mr-2" />Portal
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Subscription</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Status</span>
              <StatusBadge value={subscription?.status} />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Dunning</span>
              <StatusBadge value={subscription?.dunning_state} />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Period ends</span>
              <span>{subscription?.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : "Not active"}</span>
            </div>
            <div className="grid gap-2 pt-2">
              <Label htmlFor="billing-price-select">Plan price</Label>
              <Select value={selectedPriceId} onValueChange={setSelectedPriceId}>
                <SelectTrigger id="billing-price-select" data-testid="billing-price-select">
                  <SelectValue placeholder={purchasablePrices.length ? "Select a published price" : "No published prices"} />
                </SelectTrigger>
                <SelectContent>
                  {purchasablePrices.map((price) => {
                    const product = productById.get(price.product_id);
                    return (
                      <SelectItem key={price.id} value={price.id}>
                        {product?.name || price.price_key} - {cents(price.amount_cents, price.currency)} / {price.billing_interval}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  disabled={!canManage || !account || !selectedPriceId || checkout.isPending}
                  onClick={() => checkout.mutate()}
                  data-testid="billing-checkout-button"
                >
                  <CreditCard className="size-4 mr-2" />Checkout
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!canManage || !subscription?.id || subscription?.cancel_at_period_end || cancel.isPending}
                  onClick={() => cancel.mutate()}
                  data-testid="billing-cancel-button"
                >
                  Schedule cancel
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Trials</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Current trial</span>
              <StatusBadge value={trial?.status} />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Credits</span>
              <span>{trial?.credit_allotment ?? "None"}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Ends</span>
              <span>{trial?.ends_at ? new Date(trial.ends_at).toLocaleString() : "Not active"}</span>
            </div>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button size="sm" disabled={!canManage || !account || freeTrial.isPending} onClick={() => freeTrial.mutate()} data-testid="billing-free-trial-button">
                Start free trial
              </Button>
              <Button size="sm" variant="outline" disabled={!canManage || !account || extendedTrial.isPending} onClick={() => extendedTrial.mutate()} data-testid="billing-extended-trial-button">
                Extended trial
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Setup Packages</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 max-w-sm">
            <Label htmlFor="setup-package-select">Package</Label>
            <Select value={selectedSetup} onValueChange={setSelectedSetup}>
              <SelectTrigger id="setup-package-select" data-testid="billing-setup-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SETUP_PACKAGES.map((pkg) => <SelectItem key={pkg.key} value={pkg.key}>{pkg.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              className="w-fit"
              disabled={!canManage || !account || setupCheckout.isPending}
              onClick={() => setupCheckout.mutate()}
              data-testid="billing-setup-checkout-button"
            >
              Create setup checkout
            </Button>
          </div>

          {setupPurchases.length === 0 ? (
            <div className="text-sm text-muted-foreground" data-testid="billing-setup-empty">No setup package purchases yet.</div>
          ) : (
            <Table data-testid="billing-setup-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Package</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>EC19 handoff</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {setupPurchases.map((purchase) => (
                  <TableRow key={purchase.id}>
                    <TableCell className="capitalize">{purchase.package_key.replace(/_/g, " ")}</TableCell>
                    <TableCell><StatusBadge value={purchase.status} /></TableCell>
                    <TableCell>{cents(purchase.amount_cents, purchase.currency)}</TableCell>
                    <TableCell><Badge variant="outline">{purchase.ec19_handoff_status}</Badge></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

