import { useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { listGeneratedAssets } from "@/lib/aiStudio";
import { Image } from "lucide-react";

export default function GeneratedAssetsPage() {
  const { hasPerm } = useAuth();
  const [assets, setAssets] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hasPerm("document:read")) return;
    listGeneratedAssets().then(setAssets).catch((err) => setError(extractError(err, "Unable to load generated assets")));
  }, [hasPerm]);

  if (!hasPerm("document:read")) {
    return (
      <div className="space-y-4" data-testid="generated-assets-page">
        <PageHeader title="Generated Assets" subtitle="AI-generated concepts, documents, campaigns, and reports." />
        <Alert><Image className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Document read access is required.</AlertDescription></Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="generated-assets-page">
      <PageHeader title="Generated Assets" subtitle="Concepts, mockups, documents, campaigns, and reports saved from AI Studio." />
      {error && <Alert variant="destructive"><AlertTitle>Generated Assets</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
      <Card>
        <CardHeader><CardTitle className="text-base">Library</CardTitle></CardHeader>
        <CardContent>
          {assets.length === 0 ? (
            <div className="text-sm text-muted-foreground" data-testid="generated-assets-empty">No generated assets saved yet.</div>
          ) : (
            <Table>
              <TableHeader><TableRow><TableHead>Title</TableHead><TableHead>Tool</TableHead><TableHead>Type</TableHead><TableHead>Status</TableHead><TableHead>Boundary</TableHead></TableRow></TableHeader>
              <TableBody>
                {assets.map((asset) => (
                  <TableRow key={asset.id}>
                    <TableCell className="font-medium">{asset.title}</TableCell>
                    <TableCell>{asset.tool_key?.replace(/_/g, " ")}</TableCell>
                    <TableCell>{asset.asset_type?.replace(/_/g, " ")}</TableCell>
                    <TableCell><Badge variant="outline">{asset.status}</Badge></TableCell>
                    <TableCell className="text-sm text-muted-foreground">{asset.provenance?.h7_local_mock ? "Local mock" : "Recorded"}</TableCell>
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
