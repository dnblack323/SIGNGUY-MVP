import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import EmptyState from "@/components/common/EmptyState";
import { relativeTime } from "@/lib/format";
import { toast } from "sonner";
import { Ban, KeyRound, Send, Users2 } from "lucide-react";

export default function EmployeePortalAccessPage() {
  const qc = useQueryClient();
  const { data: employeesData, isLoading } = useQuery({
    queryKey: ["employees-all-for-portal"],
    queryFn: async () => (await api.get("/employees", { params: { status: "active" } })).data,
  });
  const { data: identitiesData } = useQuery({
    queryKey: ["employee-portal-identities"],
    queryFn: async () => (await api.get("/employee-portal")).data,
  });

  const identityByEmployee = useMemo(() => {
    const m = {};
    (identitiesData?.items || []).forEach((i) => { m[i.employee_id] = i; });
    return m;
  }, [identitiesData]);

  const invite = useMutation({
    mutationFn: async (employeeId) => (await api.post(`/employee-portal/${employeeId}/invite`)).data,
    onSuccess: () => {
      toast.success("Invitation sent");
      qc.invalidateQueries({ queryKey: ["employee-portal-identities"] });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const suspend = useMutation({
    mutationFn: async (employeeId) => (await api.post(`/employee-portal/${employeeId}/suspend`)).data,
    onSuccess: () => {
      toast.success("Access suspended");
      qc.invalidateQueries({ queryKey: ["employee-portal-identities"] });
    },
    onError: (e) => toast.error(extractError(e)),
  });

  const employees = employeesData?.items || [];

  return (
    <div className="space-y-4" data-testid="employee-portal-access-page">
      <PageHeader title="Employee Portal" subtitle="Invite active employees to their self-service portal — schedule, time clock, and timesheet." />
      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : employees.length === 0 ? (
        <EmptyState icon={Users2} title="No active employees" description="Add active employees under Team & Workflow → Employees first." />
      ) : (
        <Card>
          <CardContent className="p-0 divide-y">
            {employees.map((emp) => {
              const identity = identityByEmployee[emp.id];
              return (
                <div key={emp.id} className="flex items-center justify-between gap-3 p-3" data-testid={`employee-portal-access-row-${emp.id}`}>
                  <div>
                    <Link to={`/team/employees/${emp.id}`} className="font-medium hover:underline">{emp.name}</Link>
                    <div className="text-xs text-muted-foreground">{emp.role_label || "Employee"} · {emp.email || "no email on file"}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    {identity ? (
                      <>
                        <Badge variant={identity.status === "active" ? "default" : "secondary"} data-testid={`employee-portal-access-status-${emp.id}`}>
                          {identity.status === "active" ? "Active" : "Suspended"}
                        </Badge>
                        <span className="text-xs text-muted-foreground hidden sm:inline">
                          {identity.last_login_at ? `Signed in ${relativeTime(identity.last_login_at)}` : "Not signed in yet"}
                        </span>
                        <Button size="sm" variant="outline" onClick={() => invite.mutate(emp.id)} disabled={invite.isPending} data-testid={`employee-portal-access-resend-${emp.id}`}>
                          <KeyRound className="size-4 mr-1" />Resend
                        </Button>
                        {identity.status === "active" && (
                          <Button size="sm" variant="destructive" onClick={() => suspend.mutate(emp.id)} disabled={suspend.isPending} data-testid={`employee-portal-access-suspend-${emp.id}`}>
                            <Ban className="size-4 mr-1" />Suspend
                          </Button>
                        )}
                      </>
                    ) : (
                      <Button size="sm" onClick={() => invite.mutate(emp.id)} disabled={invite.isPending} data-testid={`employee-portal-access-invite-${emp.id}`}>
                        <Send className="size-4 mr-1" />Invite
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
