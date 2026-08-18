import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { centsToDollarsString } from "@/lib/format";

export default function OverviewReportingCard({ model }) {
  const { reports } = model;

return (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Reporting</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <div className="text-muted-foreground">Orders</div>
                  <div className="text-lg font-semibold">
                    {reports.data?.order_count || 0}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Gross sales</div>
                  <div className="text-lg font-semibold">
                    {centsToDollarsString(reports.data?.gross_sales_cents)}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Platform fee</div>
                  <div className="text-lg font-semibold">
                    {centsToDollarsString(
                      reports.data?.ledger_totals_cents?.platform_usage_fee,
                    )}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Owner share</div>
                  <div className="text-lg font-semibold">
                    {centsToDollarsString(
                      reports.data?.ledger_totals_cents?.store_owner_share,
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
  );
}
