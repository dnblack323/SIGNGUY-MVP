import { useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api";

const SEVERITY_COLOR = {
  error: "text-red-700",
  warning: "text-amber-700",
  success: "text-emerald-700",
  info: "text-slate-700",
};

export default function DataSecurityPage() {
  const [activity, setActivity] = useState([]);
  const [audit, setAudit] = useState([]);

  useEffect(() => {
    api.get("/activity", { params: { limit: 50 } })
      .then((r) => setActivity(r.data?.items || []))
      .catch(() => setActivity([]));
    api.get("/audit", { params: { limit: 50 } })
      .then((r) => setAudit(r.data?.items || []))
      .catch(() => setAudit([]));
  }, []);

  return (
    <div className="space-y-4" data-testid="data-security-page">
      <PageHeader
        title="Data & Security"
        subtitle="Activity feed and immutable audit trail for this shop."
      />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Recent Activity</CardTitle></CardHeader>
          <CardContent>
            {activity.length === 0 ? (
              <div className="text-sm text-muted-foreground" data-testid="activity-empty">Nothing yet.</div>
            ) : (
              <Table data-testid="activity-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Module</TableHead>
                    <TableHead>Summary</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {activity.map((a) => (
                    <TableRow key={a.id} data-testid={`activity-row-${a.id}`}>
                      <TableCell className="text-xs text-muted-foreground">{new Date(a.created_at).toLocaleString()}</TableCell>
                      <TableCell><Badge variant="secondary" className="capitalize">{a.module}</Badge></TableCell>
                      <TableCell className={`text-sm ${SEVERITY_COLOR[a.severity] || ""}`}>{a.summary}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Audit Trail</CardTitle></CardHeader>
          <CardContent>
            {audit.length === 0 ? (
              <div className="text-sm text-muted-foreground" data-testid="audit-empty">Nothing yet.</div>
            ) : (
              <Table data-testid="audit-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {audit.map((a) => (
                    <TableRow key={a.id} data-testid={`audit-row-${a.id}`}>
                      <TableCell className="text-xs text-muted-foreground">{new Date(a.created_at).toLocaleString()}</TableCell>
                      <TableCell className="text-xs">{a.actor_email}</TableCell>
                      <TableCell className="text-sm mono">{a.action}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
