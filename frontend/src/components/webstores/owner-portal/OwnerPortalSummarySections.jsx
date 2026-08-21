import { FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { centsToDollarsString } from "@/lib/format";

export function SetupProgressCard({ data, progress }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Setup Progress</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Badge variant="outline" data-testid="portal-webstore-setup-state">
          {progress?.setup_state || data.webstore.setup_state || "not_started"}
        </Badge>
        {(progress?.steps || []).map((step) => (
          <div key={step.key} className="flex justify-between gap-3">
            <span>{step.label}</span>
            <span className="text-muted-foreground">{step.status}</span>
          </div>
        ))}
        {progress?.type_requirements && (
          <div
            className="rounded border p-3"
            data-testid="portal-webstore-type-requirements"
          >
            <div className="font-medium">
              {progress.type_requirements.label} requirements
            </div>
            <div className="mt-2 grid gap-2">
              {(progress.type_requirements.items || []).map((item) => (
                <div key={item.key} className="flex justify-between gap-3">
                  <span>{item.owner_wording || item.label}</span>
                  <span className="text-muted-foreground">{item.status}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function CommerceSummaryCard({ summary }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Commerce</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
        <div>
          <div className="text-xs text-muted-foreground">Orders</div>
          <div className="font-semibold">{summary?.order_count || 0}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Sales</div>
          <div className="font-semibold">
            {centsToDollarsString(summary?.gross_sales_cents || 0)}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Refunds</div>
          <div className="font-semibold">
            {centsToDollarsString(summary?.refund_total_cents || 0)}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Payouts</div>
          <div className="font-semibold">
            {centsToDollarsString(summary?.payout_total_cents || 0)}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Disputes</div>
          <div className="font-semibold">
            {centsToDollarsString(summary?.dispute_hold_cents || 0)}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function TermsCard({ data, onAcceptTerms }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Terms</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="rounded border p-3" data-testid="portal-terms-version">
          <div className="font-medium">
            Version {data.current_terms_version || "webstore_terms_2026_07"}
          </div>
          <div className="text-xs text-muted-foreground">
            {data.terms_acceptance
              ? `Accepted ${new Date(data.terms_acceptance.accepted_at).toLocaleString()}`
              : "Terms acceptance is separate from packet approval."}
          </div>
        </div>
        <Button
          disabled={!!data.terms_acceptance}
          onClick={onAcceptTerms}
          data-testid="portal-accept-terms"
        >
          <FileText className="size-4 mr-2" />
          Accept current Terms
        </Button>
      </CardContent>
    </Card>
  );
}

export function ChangeRequestHistoryCard({ requests }) {
  if ((requests || []).length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Change Request History</CardTitle>
      </CardHeader>
      <CardContent
        className="rounded border divide-y p-0"
        data-testid="portal-change-request-history"
      >
        {requests.map((request) => (
          <div key={request.id} className="p-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium capitalize">{request.category}</span>
              <Badge variant="outline">{request.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {request.owner_comment}
            </div>
            {(request.owner_visible_history || [])
              .slice(-2)
              .map((item, index) => (
                <div key={`${request.id}-${index}`} className="mt-1 text-xs">
                  {item.message}
                </div>
              ))}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
