import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Car, Plus, RotateCcw } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { centsToDollarsString, parseDollarsToCents } from "@/lib/format";
import { createWrapProject, createWrapVehicle, getWrapReports, listWrapProjects } from "@/lib/wrapLab";
import { toast } from "sonner";

const statuses = ["lead_intake", "vehicle_recorded", "measurement_planning", "estimate_ready", "design_in_progress", "install_scheduled", "completed", "warranty_active"];

function statusTone(status) {
  if (["completed", "warranty_active"].includes(status)) return "secondary";
  if (status === "archived") return "destructive";
  return "outline";
}

export default function WrapLabPage() {
  const { hasPerm } = useAuth();
  const qc = useQueryClient();
  const canRead = hasPerm("wrap_lab:read");
  const canWrite = hasPerm("wrap_lab:write");
  const [status, setStatus] = useState("");
  const [form, setForm] = useState({
    customerId: "",
    make: "",
    model: "",
    year: "",
    projectName: "",
    estimate: "",
  });
  const projects = useQuery({ queryKey: ["wrap-lab-projects", status], queryFn: () => listWrapProjects(status ? { status } : {}), enabled: canRead });
  const reports = useQuery({ queryKey: ["wrap-lab-reports"], queryFn: getWrapReports, enabled: canRead });
  const createFlow = useMutation({
    mutationFn: async () => {
      const vehicle = await createWrapVehicle({
        customer_id: form.customerId,
        make: form.make,
        model: form.model,
        year: form.year || undefined,
        vehicle_type: "van",
      });
      return createWrapProject({
        customer_id: form.customerId,
        vehicle_id: vehicle.id,
        project_name: form.projectName,
        project_type: "partial_wrap",
        estimate_total_cents: parseDollarsToCents(form.estimate),
      });
    },
    onSuccess: async () => {
      toast.success("Wrap Lab project created");
      setForm({ customerId: "", make: "", model: "", year: "", projectName: "", estimate: "" });
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["wrap-lab-projects"] }),
        qc.invalidateQueries({ queryKey: ["wrap-lab-reports"] }),
      ]);
    },
    onError: (err) => toast.error(extractError(err)),
  });

  if (!canRead) {
    return (
      <div className="space-y-4" data-testid="wrap-lab-page">
        <PageHeader title="Wrap Lab" subtitle="Wrap Lab is available to authorized owner and admin accounts." />
        <Alert><Car className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account does not include Wrap Lab access.</AlertDescription></Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="wrap-lab-page">
      <PageHeader
        title="Wrap Lab"
        subtitle="Manage vehicle wrap projects from intake through warranty and aftercare."
        actions={<Button variant="outline" size="sm" onClick={() => projects.refetch()}><RotateCcw className="size-4 mr-2" />Refresh</Button>}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Projects</div><div className="text-xl font-semibold">{reports.data?.project_count || 0}</div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Estimates</div><div className="text-xl font-semibold">{centsToDollarsString(reports.data?.estimate_total_cents)}</div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Deposits</div><div className="text-xl font-semibold">{centsToDollarsString(reports.data?.deposit_required_cents)}</div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Install scheduled</div><div className="text-xl font-semibold">{reports.data?.status_counts?.install_scheduled || 0}</div></CardContent></Card>
      </div>

      {canWrite && (
        <Card>
          <CardHeader><CardTitle className="text-base">New Wrap Project</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
            <div className="grid gap-1.5"><Label>Customer ID</Label><Input value={form.customerId} onChange={(e) => setForm({ ...form, customerId: e.target.value })} data-testid="wrap-customer-id" /></div>
            <div className="grid gap-1.5"><Label>Year</Label><Input value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} /></div>
            <div className="grid gap-1.5"><Label>Make</Label><Input value={form.make} onChange={(e) => setForm({ ...form, make: e.target.value })} data-testid="wrap-make" /></div>
            <div className="grid gap-1.5"><Label>Model</Label><Input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} data-testid="wrap-model" /></div>
            <div className="grid gap-1.5"><Label>Project</Label><Input value={form.projectName} onChange={(e) => setForm({ ...form, projectName: e.target.value })} data-testid="wrap-project-name" /></div>
            <div className="grid gap-1.5"><Label>Estimate</Label><Input value={form.estimate} onChange={(e) => setForm({ ...form, estimate: e.target.value })} /></div>
            <Button className="md:col-span-6" disabled={createFlow.isPending || !form.customerId || !form.make || !form.model || !form.projectName} onClick={() => createFlow.mutate()} data-testid="wrap-project-create">
              <Plus className="size-4 mr-2" />Create project
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant={!status ? "secondary" : "outline"} onClick={() => setStatus("")}>All</Button>
        {statuses.map((s) => <Button key={s} size="sm" variant={status === s ? "secondary" : "outline"} onClick={() => setStatus(s)}>{s.replace(/_/g, " ")}</Button>)}
      </div>

      <div className="rounded border bg-white divide-y">
        {(projects.data?.items || []).map((project) => (
          <Link key={project.id} to={`/wrap-lab/${project.id}`} className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-2 p-3 text-sm hover:bg-slate-50" data-testid={`wrap-project-row-${project.id}`}>
            <div>
              <div className="font-medium">{project.project_name}</div>
              <div className="text-xs text-muted-foreground">{project.project_type.replace(/_/g, " ")} · customer {project.customer_id}</div>
            </div>
            <Badge variant={statusTone(project.status)} className="w-fit capitalize">{project.status.replace(/_/g, " ")}</Badge>
            <div className="text-xs text-muted-foreground md:text-right">{centsToDollarsString(project.estimate_total_cents)}</div>
          </Link>
        ))}
        {projects.isLoading && <div className="p-4 text-sm text-muted-foreground">Loading...</div>}
        {!projects.isLoading && (projects.data?.items || []).length === 0 && <div className="p-4 text-sm text-muted-foreground">No Wrap Lab projects yet.</div>}
      </div>
    </div>
  );
}
