import { useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { listAIStudioActivity } from "@/lib/aiStudio";
import { History } from "lucide-react";

export default function AIActivityPage() {
  const { hasPerm } = useAuth();
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hasPerm("ai_history:read")) return;
    listAIStudioActivity().then(setItems).catch((err) => setError(extractError(err, "Unable to load AI activity")));
  }, [hasPerm]);

  if (!hasPerm("ai_history:read")) {
    return (
      <div className="space-y-4" data-testid="ai-activity-page">
        <PageHeader title="AI Activity" subtitle="Tenant AI result history." />
        <Alert><History className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>AI history read access is required.</AlertDescription></Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="ai-activity-page">
      <PageHeader title="AI Activity" subtitle="Tool runs, generated results, drafts, usage bands, and linked context." />
      {error && <Alert variant="destructive"><AlertTitle>AI Activity</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
      <Card>
        <CardHeader><CardTitle className="text-base">Recent Activity</CardTitle></CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <div className="text-sm text-muted-foreground" data-testid="ai-activity-empty">No AI Studio activity yet.</div>
          ) : (
            <Table>
              <TableHeader><TableRow><TableHead>Tool</TableHead><TableHead>Mode</TableHead><TableHead>Result</TableHead><TableHead>Band</TableHead><TableHead>Context</TableHead></TableRow></TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={`${item.record_type}-${item.id}`}>
                    <TableCell>{item.tool_key?.replace(/_/g, " ")}</TableCell>
                    <TableCell>{item.mode_key?.replace(/_/g, " ")}</TableCell>
                    <TableCell><Badge variant="outline">{item.record_type?.replace(/_/g, " ")}</Badge></TableCell>
                    <TableCell>{item.usage_band}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{item.parent_record_type ? `${item.parent_record_type} ${item.parent_record_id}` : "-"}</TableCell>
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
