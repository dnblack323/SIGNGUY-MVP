import { useState } from "react";
import { AlertCircle, CheckCircle2, FileArchive, RotateCcw, Upload } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/auth/AuthContext";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { extractError } from "@/lib/api";
import { confirmSlimImport, previewSlimImport } from "@/lib/slimImport";

const STAGES = [
  "Upload Backup",
  "Enter Passphrase",
  "Validate Backup",
  "Select Empty Target Tenant",
  "Preview Record Mapping",
  "Resolve Users and Assignments",
  "Review Warnings and Blockers",
  "Confirm Import",
  "Import",
  "Final Report",
];

function CountTable({ counts = {} }) {
  return (
    <Table>
      <TableHeader><TableRow><TableHead>Resource</TableHead><TableHead className="text-right">Count</TableHead></TableRow></TableHeader>
      <TableBody>
        {Object.entries(counts).map(([key, value]) => (
          <TableRow key={key}><TableCell>{key}</TableCell><TableCell className="text-right">{value}</TableCell></TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export default function SlimImportPage() {
  const { tenant, user, hasPerm } = useAuth();
  const [file, setFile] = useState(null);
  const [passphrase, setPassphrase] = useState("");
  const [confirmationPhrase, setConfirmationPhrase] = useState("");
  const [importUnassigned, setImportUnassigned] = useState(false);
  const [preview, setPreview] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const canImport = hasPerm("settings:write") && ["owner", "admin"].includes(user?.role);
  const targetTenantId = tenant?.id;
  const blocked = (preview?.blocking_errors || []).length > 0;
  const users = preview?.user_mapping || [];
  const mappedUsers = users.filter((entry) => entry.matched).length;

  async function runPreview(event) {
    event.preventDefault();
    if (!file || !targetTenantId) return;
    setBusy(true);
    setReport(null);
    try {
      const result = await previewSlimImport({ file, passphrase, targetTenantId });
      setPreview(result);
      toast[result.import_permitted ? "success" : "warning"](result.import_permitted ? "Preview ready" : "Preview blocked");
    } catch (err) {
      toast.error(extractError(err, "Unable to validate Slim backup"));
    } finally {
      setBusy(false);
    }
  }

  async function runImport() {
    if (!file || !preview?.import_permitted || !targetTenantId) return;
    setBusy(true);
    try {
      const result = await confirmSlimImport({
        file,
        passphrase,
        targetTenantId,
        confirmationPhrase,
        importUnassigned,
      });
      setReport(result);
      toast.success("Slim import completed");
    } catch (err) {
      toast.error(extractError(err, "Unable to import Slim backup"));
    } finally {
      setBusy(false);
    }
  }

  if (!canImport) {
    return (
      <div className="space-y-4" data-testid="slim-import-page">
        <PageHeader title="Import from SignGuy Slim" subtitle="Owner/admin access required." />
        <Alert><AlertCircle className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account cannot import Slim backups.</AlertDescription></Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="slim-import-page">
      <PageHeader
        title="Import from SignGuy Slim"
        subtitle="Upgrade a validated Slim backup into the current empty full-MVP tenant."
        actions={<Button variant="outline" size="sm" onClick={() => { setPreview(null); setReport(null); }}><RotateCcw className="mr-2 size-4" />Reset</Button>}
      />

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {STAGES.map((stage, index) => (
          <div key={stage} className="rounded-md border bg-white px-3 py-2 text-sm" data-testid={`slim-import-stage-${index + 1}`}>
            <div className="text-xs text-muted-foreground">Step {index + 1}</div>
            <div className="font-medium">{stage}</div>
          </div>
        ))}
      </div>

      <form onSubmit={runPreview} className="grid gap-4 lg:grid-cols-[1fr_0.85fr]">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><FileArchive className="size-4" />Backup Validation</CardTitle></CardHeader>
          <CardContent className="grid gap-3">
            <div className="grid gap-1.5">
              <Label>Slim backup file</Label>
              <Input type="file" accept=".signguy-backup,application/vnd.signguy.backup" onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); setReport(null); }} data-testid="slim-import-file-input" />
            </div>
            <div className="grid gap-1.5">
              <Label>Backup passphrase</Label>
              <Input type="password" value={passphrase} onChange={(event) => setPassphrase(event.target.value)} minLength={12} data-testid="slim-import-passphrase-input" />
            </div>
            <div className="grid gap-1.5">
              <Label>Target tenant</Label>
              <Input value={tenant?.name || ""} disabled data-testid="slim-import-target-input" />
            </div>
            <Button type="submit" disabled={busy || !file || passphrase.length < 12} data-testid="slim-import-preview-button">
              <Upload className="mr-2 size-4" />Validate Backup
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Preview Status</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            {!preview && <div className="text-muted-foreground">No preview loaded.</div>}
            {preview && (
              <>
                <div className="flex items-center justify-between"><span>Backup</span><span className="mono text-xs">{preview.backup_id}</span></div>
                <div className="flex items-center justify-between"><span>Source</span><Badge variant="secondary">{preview.source_product}</Badge></div>
                <div className="flex items-center justify-between"><span>Users mapped</span><span>{mappedUsers}/{users.length}</span></div>
                <div className="flex items-center justify-between"><span>Result</span><Badge variant={blocked ? "destructive" : "secondary"}>{blocked ? "Blocked" : "Ready"}</Badge></div>
              </>
            )}
          </CardContent>
        </Card>
      </form>

      {preview && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="text-base">Record Counts</CardTitle></CardHeader>
            <CardContent><CountTable counts={preview.record_counts} /></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Warnings and Blockers</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {(preview.blocking_errors || []).length === 0 ? <Alert><CheckCircle2 className="size-4" /><AlertTitle>No blockers</AlertTitle><AlertDescription>The target tenant passed the preview checks.</AlertDescription></Alert> : (
                <Alert variant="destructive"><AlertCircle className="size-4" /><AlertTitle>Import blocked</AlertTitle><AlertDescription>{preview.blocking_errors.join(", ")}</AlertDescription></Alert>
              )}
              {(preview.warnings || []).map((warning) => <div key={warning} className="rounded-md border px-3 py-2 text-sm">{warning}</div>)}
            </CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle className="text-base">Confirm Import</CardTitle></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
              <div className="grid gap-1.5">
                <Label>Type current shop name</Label>
                <Input value={confirmationPhrase} onChange={(event) => setConfirmationPhrase(event.target.value)} placeholder={tenant?.name || ""} data-testid="slim-import-confirmation-input" />
              </div>
              <label className="flex items-center gap-2 text-sm md:pb-2">
                <Checkbox checked={importUnassigned} onCheckedChange={(value) => setImportUnassigned(Boolean(value))} data-testid="slim-import-unassigned-checkbox" />
                Acknowledge unresolved assignments
              </label>
              <Button type="button" onClick={runImport} disabled={busy || blocked || confirmationPhrase !== tenant?.name || (preview.requires_unassigned_acknowledgement && !importUnassigned)} data-testid="slim-import-confirm-button">
                Import
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {report && (
        <Card>
          <CardHeader><CardTitle className="text-base">Final Report</CardTitle></CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <div className="flex justify-between"><span>Import ID</span><span className="mono">{report.import_id}</span></div>
            <div className="flex justify-between"><span>Status</span><Badge variant="secondary">{report.status}</Badge></div>
            <CountTable counts={report.counts_imported} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
