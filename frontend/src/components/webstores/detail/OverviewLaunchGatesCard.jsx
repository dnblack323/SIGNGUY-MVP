import {
  Lock,
  Mail,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function OverviewLaunchGatesCard({ model }) {
  const {
    activePacket,
    detail,
    formatDateTime,
    launch,
    markLaunchReady,
    packet,
    paymentProvider,
    paymentProviderAction,
    readiness,
    store,
  } = model;

return (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Launch Gates</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  {(
                    readiness.data?.gates ||
                    Object.entries(readiness.data?.checks || {}).map(
                      ([key, ok]) => ({
                        key,
                        state: ok ? "ready" : "blocked",
                        reason: ok ? "Ready" : "Missing",
                        blocking: !ok,
                      }),
                    )
                  ).map((gate) => (
                    <div
                      className="rounded border p-3"
                      key={gate.key}
                      data-testid={`webstore-readiness-gate-${gate.key}`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="capitalize font-medium">
                          {gate.key.replace(/_/g, " ")}
                        </span>
                        <Badge
                          variant={!gate.blocking ? "secondary" : "outline"}
                        >
                          {gate.state || (!gate.blocking ? "ready" : "blocked")}
                        </Badge>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {gate.reason || gate.owner_wording}
                      </div>
                      {gate.action && (
                        <div className="mt-1 text-xs text-slate-700">
                          {gate.action}
                        </div>
                      )}
                    </div>
                  ))}
                  <div
                    className="rounded border bg-slate-50 px-3 py-2 text-xs"
                    data-testid="webstore-terms-readiness"
                  >
                    <div className="font-medium">
                      Terms version:{" "}
                      {readiness.data?.current_terms_version ||
                        detail.data?.current_terms_version ||
                        "webstore_terms_2026_07"}
                    </div>
                    <div>
                      {readiness.data?.terms_acceptance
                        ? `Accepted ${formatDateTime(readiness.data.terms_acceptance.accepted_at)}`
                        : "Waiting on separate Store Owner Terms acceptance."}
                    </div>
                  </div>
                  <div
                    className="rounded border bg-amber-50 px-3 py-2 text-xs text-amber-800"
                    data-testid="webstore-payment-readiness"
                  >
                    <div className="font-medium">
                      Payment readiness:{" "}
                      {(readiness.data?.payment_readiness?.state || "").replace(
                        "not_configured",
                        "Not connected",
                      ) ||
                        (readiness.data?.checks?.payment_ready
                          ? "Ready"
                          : "Not connected")}
                    </div>
                    <div>
                      {readiness.data?.payment_unavailable_reason ||
                        "Real verified provider checkout is not connected yet."}
                    </div>
                  </div>
                  <div
                    className="rounded border p-3 space-y-3"
                    data-testid="webstore-stripe-status"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium">Stripe Connect</div>
                      <Badge variant="outline">
                        {paymentProvider.data?.status?.label ||
                          "Not configured"}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {paymentProvider.data?.status?.reason ||
                        "Stripe integration is disabled for this foundation build."}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={paymentProviderAction.isPending}
                        onClick={() => paymentProviderAction.mutate("connect")}
                      >
                        <Mail className="size-4 mr-2" />
                        Open Stripe Connect setup
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={paymentProviderAction.isPending}
                        onClick={() =>
                          paymentProviderAction.mutate("refresh_status")
                        }
                      >
                        <RotateCcw className="size-4 mr-2" />
                        Refresh status
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={paymentProviderAction.isPending}
                        onClick={() =>
                          paymentProviderAction.mutate("resume_onboarding")
                        }
                      >
                        Resume onboarding
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={paymentProviderAction.isPending}
                        onClick={() =>
                          paymentProviderAction.mutate("view_requirements")
                        }
                      >
                        View requirements
                      </Button>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Provider authority is required before checkout or launch.
                      Checkout remains blocked until the connected account and
                      webhook verification are complete.
                    </div>
                  </div>
                  <div
                    className="rounded border bg-slate-50 px-3 py-2 text-xs"
                    data-testid="webstore-qr-preview"
                  >
                    <div className="font-medium">QR preview</div>
                    <div>
                      {activePacket?.snapshot?.qr_reference?.destination ||
                        store.public_url ||
                        "Generate a packet to prepare the QR destination."}
                    </div>
                    <div className="text-muted-foreground">
                      QR destination opens the public Webstore when the
                      lifecycle status is live.
                    </div>
                  </div>
                  <Button
                    className="w-full"
                    disabled={
                      !readiness.data?.ready || markLaunchReady.isPending
                    }
                    onClick={() => markLaunchReady.mutate()}
                    data-testid="webstore-launch-ready"
                  >
                    <ShieldCheck className="size-4 mr-2" />
                    Mark ready to launch
                  </Button>
                  <Button
                    className="w-full"
                    variant="outline"
                    disabled
                    onClick={() => launch.mutate()}
                    data-testid="webstore-launch"
                  >
                    <Lock className="size-4 mr-2" />
                    Public commerce waits for Stage 6/7
                  </Button>
                </CardContent>
              </Card>
  );
}
