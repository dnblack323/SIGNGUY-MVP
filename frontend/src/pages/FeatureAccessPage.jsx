import { useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { listEntitlements } from "@/lib/entitlements";

export default function FeatureAccessPage() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    listEntitlements().then((r) => setItems(r.items || [])).catch(() => setItems([]));
  }, []);

  return (
    <div className="space-y-4" data-testid="feature-access-page">
      <PageHeader
        title="Feature Access"
        subtitle="Features enabled for your shop. Subscription-driven changes appear here once configured by SignGuy AI."
      />
      <Card>
        <CardHeader><CardTitle>Entitlements</CardTitle></CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <div data-testid="feature-access-empty" className="text-sm text-muted-foreground">
              No features enabled yet. Included features will appear here.
            </div>
          ) : (
            <Table data-testid="entitlements-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Feature</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Quota</TableHead>
                  <TableHead>Expires</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((e) => (
                  <TableRow key={e.id} data-testid={`entitlement-row-${e.feature_key}`}>
                    <TableCell className="mono text-sm">{e.feature_key}</TableCell>
                    <TableCell>
                      {e.enabled
                        ? <Badge variant="secondary" className="text-emerald-700">Enabled</Badge>
                        : <Badge variant="outline">Disabled</Badge>}
                    </TableCell>
                    <TableCell className="text-sm">
                      {e.quota == null ? "Unlimited" : `${e.quota_used || 0} / ${e.quota}`}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {e.expires_at ? new Date(e.expires_at).toLocaleDateString() : "—"}
                    </TableCell>
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
