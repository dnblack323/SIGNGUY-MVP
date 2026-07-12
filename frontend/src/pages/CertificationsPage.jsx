import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { useAuth } from "@/auth/AuthContext";
import { toast } from "sonner";
import { formatDate } from "@/lib/format";
import { LayoutGrid, ShieldCheck } from "lucide-react";
import IssueCertificationDialog from "@/components/certifications/IssueCertificationDialog";
import RevokeCertificationDialog from "@/components/certifications/RevokeCertificationDialog";

function ManageCertDialog({ cell, employeeName, equipmentName, onOpenChange, onRenew, onRevoke }) {
  const cert = cell?.certification;
  return (
    <Dialog open={!!cell} onOpenChange={onOpenChange}>
      <DialogContent data-testid="manage-certification-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">{employeeName} <StatusPill kind="certification" value={cell?.status} /></DialogTitle>
          <DialogDescription>{equipmentName}</DialogDescription>
        </DialogHeader>
        {cert && (
          <div className="text-sm space-y-1">
            <div>Issued: {cert.issued_date ? formatDate(cert.issued_date) : "—"}</div>
            <div>Expires: {cert.expiration_date ? formatDate(cert.expiration_date) : "Never"}</div>
            {cert.restrictions && <div>Restrictions: {cert.restrictions}</div>}
            {cert.revocation_reason && <div className="text-rose-700">Revoked: {cert.revocation_reason}</div>}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
          {cert && cert.status !== "revoked" && (
            <Button variant="destructive" onClick={onRevoke} data-testid="manage-cert-revoke-button">Revoke</Button>
          )}
          <Button onClick={onRenew} data-testid="manage-cert-renew-button">{cert ? "Renew" : "Issue"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MatrixTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["certification-matrix"], queryFn: async () => (await api.get("/certifications/matrix")).data });
  const [cell, setCell] = useState(null); // {employeeId, employeeName, equipmentId, equipmentName, certification, status}
  const [issueOpen, setIssueOpen] = useState(false);
  const [revokeOpen, setRevokeOpen] = useState(false);

  const revoke = useMutation({
    mutationFn: async (reason) => (await api.post(`/certifications/${cell.certification.id}/revoke`, { reason })).data,
    onSuccess: () => { toast.success("Certification revoked"); qc.invalidateQueries({ queryKey: ["certification-matrix"] }); setRevokeOpen(false); setCell(null); },
    onError: (e) => toast.error(extractError(e)),
  });

  if (isLoading || !data) return <div className="text-sm text-muted-foreground">Loading…</div>;
  if (data.employees.length === 0 || data.equipment.length === 0) {
    return <EmptyState icon={LayoutGrid} title="Nothing to show yet" description="Add Employees and Equipment with an access policy to build the Certification matrix." />;
  }

  return (
    <div className="rounded-xl border bg-card overflow-x-auto">
      <table className="w-full text-sm" data-testid="certification-matrix-table">
        <thead>
          <tr className="border-b">
            <th className="text-left py-2 px-3 sticky left-0 bg-card">Employee</th>
            {data.equipment.map((eq) => <th key={eq.id} className="py-2 px-3 text-left font-medium">{eq.name}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row) => (
            <tr key={row.employee_id} className="border-b last:border-0" data-testid={`certification-matrix-row-${row.employee_id}`}>
              <td className="py-2 px-3 font-medium sticky left-0 bg-card">{row.employee_name}</td>
              {row.cells.map((c) => {
                const eq = data.equipment.find((e) => e.id === c.equipment_id);
                return (
                  <td key={c.equipment_id} className="py-2 px-3">
                    <button
                      onClick={() => setCell({ employeeId: row.employee_id, employeeName: row.employee_name, equipmentId: c.equipment_id, equipmentName: eq?.name, certification: c.certification, status: c.status })}
                      data-testid={`certification-matrix-cell-${row.employee_id}-${c.equipment_id}`}
                    >
                      <StatusPill kind="certification" value={c.status} />
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <ManageCertDialog
        cell={cell} employeeName={cell?.employeeName} equipmentName={cell?.equipmentName}
        onOpenChange={(o) => !o && setCell(null)}
        onRenew={() => setIssueOpen(true)}
        onRevoke={() => setRevokeOpen(true)}
      />
      {cell && (
        <IssueCertificationDialog
          open={issueOpen} onOpenChange={setIssueOpen}
          employeeId={cell.employeeId} employeeName={cell.employeeName}
          equipmentId={cell.equipmentId} equipmentName={cell.equipmentName}
          renewalOf={cell.certification?.id}
        />
      )}
      <RevokeCertificationDialog open={revokeOpen} onOpenChange={setRevokeOpen} pending={revoke.isPending} onConfirm={(reason) => revoke.mutate(reason)} />
    </div>
  );
}

const CERT_STATUSES = ["not_started", "in_progress", "pending_signoff", "certified", "expired", "revoked", "failed"];

function AllCertificationsTab() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["certifications-list", status],
    queryFn: async () => (await api.get("/certifications", { params: { status: status || undefined } })).data.items,
  });
  const { data: employees } = useQuery({ queryKey: ["employees-for-certs"], queryFn: async () => (await api.get("/employees")).data.items || [] });
  const [revokeTarget, setRevokeTarget] = useState(null);

  const revoke = useMutation({
    mutationFn: async ({ id, reason }) => (await api.post(`/certifications/${id}/revoke`, { reason })).data,
    onSuccess: () => { toast.success("Certification revoked"); qc.invalidateQueries({ queryKey: ["certifications-list"] }); setRevokeTarget(null); },
    onError: (e) => toast.error(extractError(e)),
  });

  const employeeName = (id) => (employees || []).find((e) => e.id === id)?.name || id;
  const items = data || [];

  return (
    <div className="space-y-4">
      <Select value={status || "__all__"} onValueChange={(v) => setStatus(v === "__all__" ? "" : v)}>
        <SelectTrigger className="w-[200px]" data-testid="certifications-status-filter"><SelectValue placeholder="All statuses" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="__all__">All statuses</SelectItem>
          {CERT_STATUSES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s.replace(/_/g, " ")}</SelectItem>)}
        </SelectContent>
      </Select>
      {isLoading ? <div className="text-sm text-muted-foreground">Loading…</div> : items.length === 0 ? (
        <EmptyState icon={ShieldCheck} title="No Certifications" description="Issue Certifications from the Matrix tab." />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <table className="w-full text-sm" data-testid="certifications-list-table">
            <thead className="text-left text-xs text-muted-foreground border-b">
              <tr><th className="py-2 px-3">Employee</th><th className="py-2 px-3">Equipment</th><th className="py-2 px-3">Status</th><th className="py-2 px-3">Expires</th><th className="py-2 px-3" /></tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="border-b last:border-0" data-testid={`certification-row-${c.id}`}>
                  <td className="py-2 px-3">{employeeName(c.employee_id)}</td>
                  <td className="py-2 px-3">{c.equipment_name || c.certification_type || "—"}</td>
                  <td className="py-2 px-3"><StatusPill kind="certification" value={c.status} />{c.expires_soon && <span className="ml-1 text-xs text-amber-700">expiring soon</span>}</td>
                  <td className="py-2 px-3 text-muted-foreground">{c.expiration_date ? formatDate(c.expiration_date) : "Never"}</td>
                  <td className="py-2 px-3">
                    {c.status !== "revoked" && (
                      <Button size="sm" variant="ghost" onClick={() => setRevokeTarget(c.id)} data-testid={`certification-revoke-${c.id}`}>Revoke</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <RevokeCertificationDialog open={!!revokeTarget} onOpenChange={(o) => !o && setRevokeTarget(null)} pending={revoke.isPending} onConfirm={(reason) => revoke.mutate({ id: revokeTarget, reason })} />
    </div>
  );
}

export default function CertificationsPage() {
  const { hasPerm } = useAuth();
  const canRead = hasPerm("certification:read");
  return (
    <div className="space-y-4" data-testid="certifications-page">
      <PageHeader title="Certifications" subtitle="Employee × Equipment certification matrix — issue, renew and revoke." />
      {!canRead ? (
        <EmptyState title="No access" description="You don't have permission to view Certifications." />
      ) : (
        <Tabs defaultValue="matrix" data-testid="certifications-tabs">
          <TabsList>
            <TabsTrigger value="matrix" data-testid="certifications-tab-matrix">Matrix</TabsTrigger>
            <TabsTrigger value="all" data-testid="certifications-tab-all">All Certifications</TabsTrigger>
          </TabsList>
          <TabsContent value="matrix"><MatrixTab /></TabsContent>
          <TabsContent value="all"><AllCertificationsTab /></TabsContent>
        </Tabs>
      )}
    </div>
  );
}
