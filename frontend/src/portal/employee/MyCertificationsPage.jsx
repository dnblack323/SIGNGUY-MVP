import { useEffect, useState } from "react";
import employeePortalApi, { employeePortalExtractError } from "./employeePortalApi";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck } from "lucide-react";

function statusVariant(status) {
  if (["expired", "revoked", "failed"].includes(status)) return "destructive";
  return "outline";
}

export default function MyCertificationsPage() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    employeePortalApi.get("/portal/employee/certifications").then((r) => setData(r.data))
      .catch((e) => setErr(employeePortalExtractError(e)));
  }, []);
  return (
    <div className="space-y-4" data-testid="employee-portal-certifications-page">
      <h1 className="text-xl font-semibold flex items-center gap-2"><ShieldCheck className="h-5 w-5" /> My Certifications</h1>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      {!data ? <p className="text-sm text-slate-500">Loading…</p> : data.items.length === 0 ? (
        <p className="text-sm text-slate-500 italic" data-testid="employee-portal-certifications-empty">No Certifications on file yet.</p>
      ) : (
        <div className="rounded border bg-white divide-y" data-testid="employee-portal-certifications-list">
          {data.items.map((c) => (
            <div key={c.id} className="p-3 text-sm" data-testid={`employee-portal-certification-row-${c.id}`}>
              <div className="flex items-center justify-between">
                <div className="font-medium">{c.equipment_name || c.certification_type || "Certification"}</div>
                <Badge variant={statusVariant(c.status)} className="capitalize">{c.status.replace(/_/g, " ")}</Badge>
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                {c.expiration_date ? `Expires ${c.expiration_date}` : "Never expires"}
                {c.expires_soon ? " · renewal needed soon" : ""}
              </div>
              {c.restrictions && <div className="text-xs text-slate-500">Restrictions: {c.restrictions}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
