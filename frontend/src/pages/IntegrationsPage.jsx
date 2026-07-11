import { useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, CircleAlert, CircleX } from "lucide-react";
import api from "@/lib/api";

function StatusBadge({ report }) {
  if (report.ok) {
    return (
      <Badge variant="secondary" className="text-emerald-700" data-testid={`integration-status-${report.name}`}>
        <CheckCircle2 className="size-3 mr-1" /> Ready
      </Badge>
    );
  }
  if (report.enabled && !report.configured) {
    return (
      <Badge variant="destructive" data-testid={`integration-status-${report.name}`}>
        <CircleX className="size-3 mr-1" /> Missing config
      </Badge>
    );
  }
  return (
    <Badge variant="outline" data-testid={`integration-status-${report.name}`}>
      <CircleAlert className="size-3 mr-1" /> Disabled
    </Badge>
  );
}

export default function IntegrationsPage() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/integrations/status").then((r) => setData(r.data)).catch(() => setData({ integrations: [] }));
  }, []);

  return (
    <div className="space-y-4" data-testid="integrations-page">
      <PageHeader
        title="Integrations"
        subtitle="Third-party services connected to your shop. Secrets are configured via environment; this view never exposes them."
      />
      {data && (
        <div className="text-xs text-muted-foreground">Environment: <span className="mono">{data.env}</span></div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data?.integrations?.map((intg) => (
          <Card key={intg.name} data-testid={`integration-card-${intg.name}`}>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base capitalize">{intg.name.replace(/_/g, " ")}</CardTitle>
              <StatusBadge report={intg} />
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-1">
              <div>Enabled: <span className="mono">{String(intg.enabled)}</span></div>
              <div>Configured: <span className="mono">{String(intg.configured)}</span></div>
              {intg.missing_secrets?.length > 0 && (
                <div>Missing: <span className="mono">{intg.missing_secrets.join(", ")}</span></div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
