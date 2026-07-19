import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { getAICreditAccount, listAIAlerts, listAICreditLedger, listAIHistory } from "@/lib/aiGateway";
import { CircleAlert, Coins, History, RotateCcw, ShieldCheck } from "lucide-react";

function formatStatus(value) {
  if (!value) return "None";
  return String(value).replace(/_/g, " ");
}

function StatusBadge({ value }) {
  const status = String(value || "none");
  const variant = ["active", "succeeded", "final", "grant", "commit"].includes(status) ? "secondary" : "outline";
  return <Badge variant={variant} className="capitalize">{formatStatus(status)}</Badge>;
}

export default function AICreditsPage() {
  const { hasPerm } = useAuth();
  const canRead = hasPerm("ai_credit:read");
  const canReadHistory = hasPerm("ai_history:read");
  const [account, setAccount] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [history, setHistory] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canRead) return;
    setLoading(true);
    setError("");
    try {
      const [acct, ledgerRows, alertRows, historyRows] = await Promise.all([
        getAICreditAccount(),
        listAICreditLedger(50),
        listAIAlerts("open"),
        canReadHistory ? listAIHistory(50) : Promise.resolve([]),
      ]);
      setAccount(acct);
      setLedger(ledgerRows);
      setAlerts(alertRows);
      setHistory(historyRows);
    } catch (err) {
      setError(extractError(err, "Unable to load AI credit data"));
    } finally {
      setLoading(false);
    }
  }, [canRead, canReadHistory]);

  useEffect(() => { load(); }, [load]);

  if (!canRead) {
    return (
      <div className="space-y-4" data-testid="ai-credits-page">
        <PageHeader title="AI Credits" subtitle="Shared AI credit and usage metering." />
        <Alert>
          <ShieldCheck className="size-4" />
          <AlertTitle>Access required</AlertTitle>
          <AlertDescription>Your account does not include AI credit read access.</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="ai-credits-page">
      <PageHeader
        title="AI Credits"
        subtitle="Tenant AI balances, ledger activity, alerts, and metered gateway history."
        actions={(
          <Button size="sm" variant="outline" onClick={load} disabled={loading} data-testid="ai-credits-refresh">
            <RotateCcw className="size-4 mr-2" />Refresh
          </Button>
        )}
      />

      {error && (
        <Alert variant="destructive" data-testid="ai-credits-error">
          <CircleAlert className="size-4" />
          <AlertTitle>Unable to load AI credits</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Available</CardTitle></CardHeader>
          <CardContent className="flex items-end justify-between gap-3">
            <div>
              <div className="text-3xl font-semibold" data-testid="ai-available-credits">{account?.available_credits ?? 0}</div>
              <div className="text-sm text-muted-foreground">credits</div>
            </div>
            <Coins className="size-7 text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Included</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{account?.included_balance_credits ?? 0}</div>
            <div className="text-sm text-muted-foreground">billing-cycle credits</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Purchased</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{account?.purchased_balance_credits ?? 0}</div>
            <div className="text-sm text-muted-foreground">top-up credits</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Reserved</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{account?.reserved_credits ?? 0}</div>
            <div className="text-sm text-muted-foreground">pending completion</div>
          </CardContent>
        </Card>
      </div>

      {alerts.length > 0 && (
        <Alert data-testid="ai-credit-alerts">
          <CircleAlert className="size-4" />
          <AlertTitle>Open AI alerts</AlertTitle>
          <AlertDescription>{alerts.length} alert{alerts.length === 1 ? "" : "s"} require review.</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader><CardTitle className="text-base">Credit Ledger</CardTitle></CardHeader>
        <CardContent>
          {ledger.length === 0 ? (
            <div className="text-sm text-muted-foreground" data-testid="ai-ledger-empty">No AI credit ledger activity yet.</div>
          ) : (
            <Table data-testid="ai-ledger-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Included</TableHead>
                  <TableHead>Purchased</TableHead>
                  <TableHead>Reserved</TableHead>
                  <TableHead>Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ledger.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell><StatusBadge value={entry.entry_type} /></TableCell>
                    <TableCell>{entry.amount_credits}</TableCell>
                    <TableCell>{entry.balance_after_included_credits}</TableCell>
                    <TableCell>{entry.balance_after_purchased_credits}</TableCell>
                    <TableCell>{entry.reserved_after_credits}</TableCell>
                    <TableCell className="max-w-[260px] truncate">{entry.reason || "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base flex items-center gap-2"><History className="size-4" />Gateway History</CardTitle></CardHeader>
        <CardContent>
          {!canReadHistory ? (
            <div className="text-sm text-muted-foreground" data-testid="ai-history-denied">AI history read access is required.</div>
          ) : history.length === 0 ? (
            <div className="text-sm text-muted-foreground" data-testid="ai-history-empty">No metered AI gateway requests yet.</div>
          ) : (
            <Table data-testid="ai-history-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Capability</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Credits</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="mono text-sm">{item.capability_key}</TableCell>
                    <TableCell><StatusBadge value={item.status} /></TableCell>
                    <TableCell>{item.provider_key || "-"}</TableCell>
                    <TableCell>{item.model_key || "-"}</TableCell>
                    <TableCell>{item.credit_charge_credits}</TableCell>
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
