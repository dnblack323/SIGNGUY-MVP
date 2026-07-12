import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import employeePortalApi, { employeePortalExtractError } from "./employeePortalApi";
import { Badge } from "@/components/ui/badge";
import { GraduationCap } from "lucide-react";

export default function MyTrainingPage() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    employeePortalApi.get("/portal/employee/training/assignments").then((r) => setData(r.data))
      .catch((e) => setErr(employeePortalExtractError(e)));
  }, []);
  return (
    <div className="space-y-4" data-testid="employee-portal-training-page">
      <h1 className="text-xl font-semibold flex items-center gap-2"><GraduationCap className="h-5 w-5" /> My Training</h1>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      {!data ? <p className="text-sm text-slate-500">Loading…</p> : data.items.length === 0 ? (
        <p className="text-sm text-slate-500 italic" data-testid="employee-portal-training-empty">No Training assigned yet.</p>
      ) : (
        <div className="rounded border bg-white divide-y" data-testid="employee-portal-training-list">
          {data.items.map((a) => (
            <Link
              key={a.id} to={`/portal/employee/training/${a.id}`}
              className="p-3 flex items-center justify-between text-sm hover:bg-slate-50"
              data-testid={`employee-portal-training-row-${a.id}`}
            >
              <div>
                <div className="font-medium">{a.training_title || "Training"}</div>
                <div className="text-xs text-slate-500">{a.due_date ? `Due ${a.due_date}` : "No due date"}{a.overdue ? " · overdue" : ""}</div>
              </div>
              <Badge variant={a.overdue ? "destructive" : "outline"} className="capitalize">{a.status.replace(/_/g, " ")}</Badge>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
