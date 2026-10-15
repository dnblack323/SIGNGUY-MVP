import { Lock } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/AuthContext";
import { BILLING_PATH } from "@/lib/api";

/**
 * F1 — Shown when the shop's trial has ended without a purchase or its
 * subscription is suspended, unpaid or canceled. Records stay readable and
 * exportable; the backend rejects changes until the shop renews.
 */
export default function SubscriptionAccessBanner() {
  const { commercialAccess } = useAuth();
  if (!commercialAccess?.read_only) return null;
  return (
    <div className="flex flex-wrap items-center justify-center gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-950" data-testid="subscription-read-only-banner" role="status">
      <Lock className="size-4 shrink-0" />
      <span>Your SignGuy AI subscription is not active. Your records are read-only until you renew.</span>
      <Button asChild size="sm" variant="outline" className="h-8 border-amber-300 bg-white">
        <Link to={BILLING_PATH} data-testid="subscription-read-only-billing-link">Go to Billing</Link>
      </Button>
    </div>
  );
}
