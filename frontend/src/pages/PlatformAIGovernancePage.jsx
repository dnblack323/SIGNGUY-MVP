import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { getPlatformAIDashboard, listAICreditLedger, listAIModels, listAIProviders, listGovernancePolicies } from "@/lib/aiGateway";
import { CircleAlert, RotateCcw, ShieldCheck } from "lucide-react";

function isPlatformAIAdmin(user) {
  return !!(user?.platform_admin || ["admin", "owner"].includes(user?.platform_role));
}

export default function PlatformAIGovernancePage() {
  const { user } = useAuth();
  const allowed = isPlatformAIAdmin(user);
  const [dashboard, setDashboard] = useState(null);
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!allowed) return;
    setLoading(true);
    setError("");
    try {
      const [dash, providerRows, modelRows, policyRows, ledgerRows] = await Promise.all([
        getPlatformAIDashboard(),
        listAIProviders(),
        listAIModels(),
        listGovernancePolicies(),
        listAICreditLedger(25).catch(() => []),
      ]);
      setDashboard(dash);
      setProviders(providerRows);
      setModels(modelRows);
      setPolicies(policyRows);
      setLedger(ledgerRows);
    } catch (err) {
      setError(extractError(err, "Unable to load platform AI governance"));
    } finally {
      setLoading(false);
    }
  }, [allowed]);

  useEffect(() => { load(); }, [load]);

  if (!allowed) {
    return (
      <div className="space-y-4" data-testid="platform-ai-governance-page">
        <PageHeader title="AI Governance" subtitle="Platform AI cost, provider, and policy controls." />
        <Alert>
          <ShieldCheck className="size-4" />
          <AlertTitle>Platform access required</AlertTitle>
          <AlertDescription>This surface is available only to platform AI administrators.</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="platform-ai-governance-page">
      <PageHeader
        title="AI Governance"
        subtitle="Provider boundary, usage telemetry, budget alerts, and governance policy visibility."
        actions={<Button size="sm" variant="outline" onClick={load} disabled={loading}><RotateCcw className="size-4 mr-2" />Refresh</Button>}
      />

      {error && (
        <Alert variant="destructive">
          <CircleAlert className="size-4" />
          <AlertTitle>Unable to load AI governance</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        <Card><CardHeader><CardTitle className="text-base">Tenants</CardTitle></CardHeader><CardContent><div className="text-2xl font-semibold">{dashboard?.tenant_credit_accounts ?? 0}</div></CardContent></Card>
        <Card><CardHeader><CardTitle className="text-base">Requests</CardTitle></CardHeader><CardContent><div className="text-2xl font-semibold">{dashboard?.action_requests ?? 0}</div></CardContent></Card>
        <Card><CardHeader><CardTitle className="text-base">Usage Rows</CardTitle></CardHeader><CardContent><div className="text-2xl font-semibold">{dashboard?.usage_events ?? 0}</div></CardContent></Card>
        <Card><CardHeader><CardTitle className="text-base">Open Alerts</CardTitle></CardHeader><CardContent><div className="text-2xl font-semibold">{dashboard?.open_alerts ?? 0}</div></CardContent></Card>
        <Card><CardHeader><CardTitle className="text-base">Provider Calls</CardTitle></CardHeader><CardContent><div className="text-2xl font-semibold">{dashboard?.external_provider_calls ?? 0}</div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Providers and Models</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Type</TableHead><TableHead>Key</TableHead><TableHead>Status</TableHead><TableHead>Details</TableHead></TableRow></TableHeader>
            <TableBody>
              {providers.map((provider) => (
                <TableRow key={provider.id}>
                  <TableCell>Provider</TableCell>
                  <TableCell className="mono text-sm">{provider.provider_key}</TableCell>
                  <TableCell><Badge variant={provider.status === "active" ? "secondary" : "outline"}>{provider.status}</Badge></TableCell>
                  <TableCell>{provider.credential_mode}</TableCell>
                </TableRow>
              ))}
              {models.map((model) => (
                <TableRow key={model.id}>
                  <TableCell>Model</TableCell>
                  <TableCell className="mono text-sm">{model.model_key}</TableCell>
                  <TableCell><Badge variant={model.status === "active" ? "secondary" : "outline"}>{model.status}</Badge></TableCell>
                  <TableCell>{model.task_category} / {model.intensity}</TableCell>
                </TableRow>
              ))}
              {providers.length === 0 && models.length === 0 && (
                <TableRow><TableCell colSpan={4} className="text-sm text-muted-foreground">No provider boundary records yet.</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Governance Policies</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Scope</TableHead><TableHead>Status</TableHead><TableHead>Requests/day</TableHead><TableHead>Credits/day</TableHead><TableHead>Cost/day</TableHead></TableRow></TableHeader>
            <TableBody>
              {policies.map((policy) => (
                <TableRow key={policy.id}>
                  <TableCell>{policy.scope_type}{policy.capability_key ? `: ${policy.capability_key}` : ""}</TableCell>
                  <TableCell><Badge variant={policy.status === "active" ? "secondary" : "outline"}>{policy.status}</Badge></TableCell>
                  <TableCell>{policy.max_requests_per_day ?? "-"}</TableCell>
                  <TableCell>{policy.max_credits_per_day ?? "-"}</TableCell>
                  <TableCell>{policy.max_cost_micros_per_day ?? "-"}</TableCell>
                </TableRow>
              ))}
              {policies.length === 0 && (
                <TableRow><TableCell colSpan={5} className="text-sm text-muted-foreground">No AI governance policies configured.</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Recent Credit Ledger</CardTitle></CardHeader>
        <CardContent>
          {ledger.length === 0 ? (
            <div className="text-sm text-muted-foreground">No tenant-scoped ledger rows visible for this platform user tenant.</div>
          ) : (
            <Table>
              <TableHeader><TableRow><TableHead>Type</TableHead><TableHead>Amount</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader>
              <TableBody>
                {ledger.map((row) => (
                  <TableRow key={row.id}><TableCell>{row.entry_type}</TableCell><TableCell>{row.amount_credits}</TableCell><TableCell>{row.reason || "-"}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
