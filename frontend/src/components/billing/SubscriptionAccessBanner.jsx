import { useEffect, useState } from "react";
import { Lock, X } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/AuthContext";
import { ACCESS_CHANGED_EVENT, BILLING_PATH } from "@/lib/api";

/**
 * F1 — Billing path for restricted access, without forced navigation.
 *
 * - Read-only shop (trial ended without a purchase, or subscription suspended,
 *   unpaid or canceled): persistent banner. Records stay readable and
 *   exportable; the backend rejects changes until the shop renews.
 * - Paying shop that tried a paid add-on it does not hold (402
 *   `feature_not_entitled`): dismissible notice with the same Billing action.
 */
export default function SubscriptionAccessBanner() {
  const { commercialAccess } = useAuth();
  const [addOnNotice, setAddOnNotice] = useState(false);

  useEffect(() => {
    const onAccessChanged = (event) => {
      if (event?.detail?.code === "feature_not_entitled") setAddOnNotice(true);
    };
    window.addEventListener(ACCESS_CHANGED_EVENT, onAccessChanged);
    return () => window.removeEventListener(ACCESS_CHANGED_EVENT, onAccessChanged);
  }, []);

  const readOnly = !!commercialAccess?.read_only;
  if (!readOnly && !addOnNotice) return null;

  return (
    <div
      className="flex flex-wrap items-center justify-center gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-950"
      data-testid={readOnly ? "subscription-read-only-banner" : "subscription-add-on-notice"}
      role="status"
    >
      <Lock className="size-4 shrink-0" />
      <span>
        {readOnly
          ? "Your SignGuy AI subscription is not active. Your records are read-only until you renew."
          : "That feature is not included in your current subscription."}
      </span>
      <Button asChild size="sm" variant="outline" className="h-8 border-amber-300 bg-white">
        <Link to={BILLING_PATH} data-testid="subscription-read-only-billing-link">Go to Billing</Link>
      </Button>
      {!readOnly && (
        <Button type="button" size="sm" variant="ghost" className="h-8 px-2" aria-label="Dismiss" onClick={() => setAddOnNotice(false)}>
          <X className="size-4" />
        </Button>
      )}
    </div>
  );
}
