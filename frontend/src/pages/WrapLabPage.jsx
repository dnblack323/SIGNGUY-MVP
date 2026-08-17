import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Car, Plus, RotateCcw, Search } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { createWrapProject, createWrapVehicle, getWrapReports, listWrapProjects, searchWrapTargets } from "@/lib/wrapLab";
import { toast } from "sonner";

const statuses = ["lead_intake", "vehicle_recorded", "measurement_planning", "pre_install_ready", "pre_install_signed", "proof_approved", "production_ready", "install_scheduled", "completed", "warranty_active", "archived"];
const projectTypes = ["full_wrap", "partial_wrap", "spot_graphics", "lettering", "color_change", "removal", "custom"];

function statusTone(status) {
  if (["completed", "warranty_active"].includes(status)) return "secondary";
  if (status === "archived") return "destructive";
  if (["production_ready", "install_scheduled"].includes(status)) return "default";
  return "outline";
}

function targetDescription(target) {
  return [target?.label, target?.description].filter(Boolean).join(" - ");
}

export default function WrapLabPage() {
  const { hasPerm } = useAuth();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const canRead = hasPerm("wrap_lab:read");
  const canWrite = hasPerm("wrap_lab:write");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [targetId, setTargetId] = useState("");
  const [form, setForm] = useState({
    projectName: "",
    projectType: "partial_wrap",
    year: "",
    make: "",
    model: "",
    bodyStyle: "",
    vin: "",
    licensePlate: "",
    color: "",
    unitNumber: "",
    requestedCoverage: "",
    removalRequirements: "",
    installationLocation: "",
    customerInstructions: "",
    internalNotes: "",
  });
  const projects = useQuery({ queryKey: ["wrap-lab-projects", status], queryFn: () => listWrapProjects(status ? { status } : {}), enabled: canRead });
  const reports = useQuery({ queryKey: ["wrap-lab-reports"], queryFn: getWrapReports, enabled: canRead });
  const targets = useQuery({ queryKey: ["wrap-lab-targets", search], queryFn: () => searchWrapTargets({ search }), enabled: canRead && search.trim().length > 1 });
  const selectedTarget = useMemo(() => (targets.data?.items || []).find((item) => item.id === targetId), [targets.data, targetId]);

  useEffect(() => {
    const fromParams = params.get("order_item_id") || params.get("order_id") || params.get("quote_id") || "";
    if (fromParams && !search) setSearch(fromParams);
  }, [params, search]);

  const createFlow = useMutation({
    mutationFn: async () => {
      if (!selectedTarget) throw new Error("Select a customer, quote, order, or wrap order item first.");
      const customerId = selectedTarget.customer_id || (selectedTarget.type === "customer" ? selectedTarget.id : "");
      if (!customerId) throw new Error("Selected target does not include a customer context.");
      const vehicle = await createWrapVehicle({
        customer_id: customerId,
        year: form.year || undefined,
        make: form.make,
        model: form.model,
        body_style: form.bodyStyle || undefined,
        vin: form.vin || undefined,
        license_plate: form.licensePlate || undefined,
        color: form.color || undefined,
        unit_number: form.unitNumber || undefined,
        requested_coverage: form.requestedCoverage || undefined,
        removal_requirements: form.removalRequirements || undefined,
        installation_location: form.installationLocation || undefined,
        customer_instructions: form.customerInstructions || undefined,
        internal_notes: form.internalNotes || undefined,
        vehicle_type: "other",
      });
      return createWrapProject({
        customer_id: customerId,
        vehicle_id: vehicle.id,
        quote_id: selectedTarget.type === "quote" ? selectedTarget.id : undefined,
        order_id: selectedTarget.type === "order" ? selectedTarget.id : selectedTarget.order_id,
        order_item_id: selectedTarget.type === "order_item" ? selectedTarget.id : undefined,
        work_order_id: selectedTarget.type === "work_order" ? selectedTarget.id : undefined,
        project_name: form.projectName,
        project_type: form.projectType,
        coverage_summary: form.requestedCoverage || undefined,
        specifications: {
          requested_coverage: form.requestedCoverage,
          removal_requirements: form.removalRequirements,
          material_notes: "",
          installer_notes: form.internalNotes,
        },
        notes: form.internalNotes || undefined,
      });
    },
    onSuccess: async () => {
      toast.success("Wrap Project created");
      setTargetId("");
      setSearch("");
      setForm({ projectName: "", projectType: "partial_wrap", year: "", make: "", model: "", bodyStyle: "", vin: "", licensePlate: "", color: "", unitNumber: "", requestedCoverage: "", removalRequirements: "", installationLocation: "", customerInstructions: "", internalNotes: "" });
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
        subtitle="Manage vehicle wrap projects from commercial source records through inspection, proofing, production, installation, and aftercare."
        actions={<Button variant="outline" size="sm" onClick={() => projects.refetch()}><RotateCcw className="size-4 mr-2" />Refresh</Button>}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Projects</div><div className="text-xl font-semibold">{reports.data?.project_count || 0}</div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Production ready</div><div className="text-xl font-semibold">{reports.data?.status_counts?.production_ready || 0}</div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Install scheduled</div><div className="text-xl font-semibold">{reports.data?.status_counts?.install_scheduled || 0}</div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Completed</div><div className="text-xl font-semibold">{reports.data?.status_counts?.completed || 0}</div></CardContent></Card>
      </div>

      {canWrite && (
        <Card data-testid="wrap-project-create-panel">
          <CardHeader><CardTitle className="text-base">Create Wrap Project From Source Record</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2 md:grid-cols-[minmax(260px,1fr)_minmax(280px,1fr)]">
              <div className="grid gap-1.5">
                <Label>Search customers, quotes, orders, or wrap items</Label>
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
                  <Input className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Customer, quote, order, vehicle wrap item..." data-testid="wrap-target-search" />
                </div>
              </div>
              <div className="grid gap-1.5">
                <Label>Selected source</Label>
                <Select value={targetId} onValueChange={setTargetId}>
                  <SelectTrigger data-testid="wrap-target-select"><SelectValue placeholder="Choose a search result" /></SelectTrigger>
                  <SelectContent>
                    {(targets.data?.items || []).map((target) => (
                      <SelectItem key={`${target.type}-${target.id}`} value={target.id}>{target.type.replace(/_/g, " ")} - {targetDescription(target)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <Field label="Project" value={form.projectName} onChange={(projectName) => setForm({ ...form, projectName })} testId="wrap-project-name" />
              <div className="grid gap-1.5">
                <Label>Work type</Label>
                <Select value={form.projectType} onValueChange={(projectType) => setForm({ ...form, projectType })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{projectTypes.map((type) => <SelectItem key={type} value={type}>{type.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <Field label="Year" value={form.year} onChange={(year) => setForm({ ...form, year })} />
              <Field label="Make" value={form.make} onChange={(make) => setForm({ ...form, make })} testId="wrap-make" />
              <Field label="Model" value={form.model} onChange={(model) => setForm({ ...form, model })} testId="wrap-model" />
              <Field label="Trim/body" value={form.bodyStyle} onChange={(bodyStyle) => setForm({ ...form, bodyStyle })} />
              <Field label="Color" value={form.color} onChange={(color) => setForm({ ...form, color })} />
              <Field label="Unit/fleet #" value={form.unitNumber} onChange={(unitNumber) => setForm({ ...form, unitNumber })} />
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <TextField label="Requested coverage" value={form.requestedCoverage} onChange={(requestedCoverage) => setForm({ ...form, requestedCoverage })} />
              <TextField label="Removal / existing graphics" value={form.removalRequirements} onChange={(removalRequirements) => setForm({ ...form, removalRequirements })} />
              <TextField label="Customer instructions" value={form.customerInstructions} onChange={(customerInstructions) => setForm({ ...form, customerInstructions })} />
              <TextField label="Internal notes" value={form.internalNotes} onChange={(internalNotes) => setForm({ ...form, internalNotes })} />
            </div>
            <Button disabled={createFlow.isPending || !selectedTarget || !form.make || !form.model || !form.projectName} onClick={() => createFlow.mutate()} data-testid="wrap-project-create">
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
              <div className="text-xs text-muted-foreground">{project.project_type.replace(/_/g, " ")} · customer {project.customer_id} · {project.order_item_id ? "linked item" : "source pending"}</div>
            </div>
            <Badge variant={statusTone(project.status)} className="w-fit capitalize">{project.status.replace(/_/g, " ")}</Badge>
            <div className="text-xs text-muted-foreground md:text-right">{project.due_at || "No target date"}</div>
          </Link>
        ))}
        {projects.isLoading && <div className="p-4 text-sm text-muted-foreground">Loading...</div>}
        {!projects.isLoading && (projects.data?.items || []).length === 0 && <div className="p-4 text-sm text-muted-foreground">No Wrap Lab projects yet.</div>}
      </div>
    </div>
  );
}

function Field({ label, value, onChange, testId }) {
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Input value={value} onChange={(e) => onChange(e.target.value)} data-testid={testId} />
    </div>
  );
}

function TextField({ label, value, onChange }) {
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Textarea value={value} onChange={(e) => onChange(e.target.value)} rows={3} />
    </div>
  );
}
