import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Bot, CalendarClock, CheckCircle2, Copy, FileText, Layers, Link2, PackageCheck, RotateCw, ShieldCheck, ShieldOff, TimerOff, Truck } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import AIContextualActions from "@/components/ai/AIContextualActions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { extractError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import {
  acknowledgeInspection,
  advanceWrapProject,
  createCoveragePlan,
  createDesignScene,
  createInspectionReviewLink,
  createInstallationRecord,
  createInspection,
  createPanelPlan,
  createWrapSchedule,
  expireInspectionReviewLink,
  generateWrapPacket,
  getWrapProject,
  handoffWrapProject,
  listInspectionReviewLinks,
  revokeInspectionReviewLink,
  updateWrapProject,
  updateWrapVehicle,
} from "@/lib/wrapLab";
import { toast } from "sonner";

const statusOrder = ["lead_intake", "vehicle_recorded", "measurement_planning", "estimate_ready", "quote_linked", "contract_deposit_pending", "pre_install_ready", "pre_install_signed", "design_in_progress", "proof_ready", "proof_approved", "panel_plan_ready", "production_ready", "install_scheduled", "installing", "completion_packet_ready", "completed", "warranty_active"];
const coverageOptions = ["full_wrap", "partial_wrap", "spot_graphics", "lettering", "color_change", "removal", "custom"];

function nextStatus(current) {
  const idx = statusOrder.indexOf(current);
  return idx >= 0 && idx < statusOrder.length - 1 ? statusOrder[idx + 1] : null;
}

function useWrapMutation(mutationFn, success, refresh) {
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      toast.success(success);
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });
}

export default function WrapLabDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const detail = useQuery({ queryKey: ["wrap-lab-project", id], queryFn: () => getWrapProject(id), enabled: !!id });
  const project = detail.data?.project;
  const vehicle = detail.data?.vehicle || {};
  const next = useMemo(() => nextStatus(project?.status), [project?.status]);
  const refresh = () => qc.invalidateQueries({ queryKey: ["wrap-lab-project", id] });
  const [vehicleForm, setVehicleForm] = useState(null);
  const [specForm, setSpecForm] = useState(null);
  const [inspectionForm, setInspectionForm] = useState({ inspection_type: "pre_install", required_views: "front,left,right,rear", damage_panel: "", damage_type: "scratch", severity: "minor", damage_notes: "", before_photo_file_ids: "", notes: "" });
  const [ackForm, setAckForm] = useState({ signer_name: "", signer_email: "", signature_data: "" });
  const [coverageForm, setCoverageForm] = useState({ coverage_level: "partial_wrap", panels: "Driver door,42,36\nPassenger door,42,36", notes: "" });
  const [panelForm, setPanelForm] = useState({ printer_max_width_inches: "54", panels: "Driver side,196,70\nPassenger side,196,70", notes: "" });
  const [designForm, setDesignForm] = useState({ vehicle_template_key: "", layer_name: "", source_file_id: "", notes: "" });
  const [scheduleForm, setScheduleForm] = useState({ title: "Wrap install", start_at: "", end_at: "", location: "", notes: "" });
  const [installForm, setInstallForm] = useState({ status: "completed", crew_names: "", actual_start_at: "", actual_end_at: "", location: "", preparation: "Surface cleaned\nOld graphics removed", checklist: "Panels installed\nEdges post-heated", quality_notes: "", completion_photo_file_ids: "" });
  const [handoffReason, setHandoffReason] = useState("");
  const [packetType, setPacketType] = useState("pre_install");

  const ensureVehicleForm = () => setVehicleForm(vehicleForm || {
    year: vehicle.year || "",
    make: vehicle.make || "",
    model: vehicle.model || "",
    body_style: vehicle.body_style || vehicle.trim || "",
    vin: vehicle.vin || "",
    license_plate: vehicle.license_plate || "",
    color: vehicle.color || "",
    unit_number: vehicle.unit_number || "",
    odometer: vehicle.odometer || "",
    requested_coverage: vehicle.requested_coverage || "",
    removal_requirements: vehicle.removal_requirements || "",
    installation_location: vehicle.installation_location || "",
    customer_instructions: vehicle.customer_instructions || "",
    internal_notes: vehicle.internal_notes || "",
  });
  const ensureSpecForm = () => setSpecForm(specForm || {
    project_type: project?.project_type || "partial_wrap",
    coverage_summary: project?.coverage_summary || "",
    material: project?.specifications?.material || "",
    laminate: project?.specifications?.laminate || "",
    panels_included: (project?.specifications?.panels_included || []).join(", "),
    panels_excluded: (project?.specifications?.panels_excluded || []).join(", "),
    finishing: project?.specifications?.finishing || "",
    installer_notes: project?.specifications?.installer_notes || "",
    warranty: project?.specifications?.warranty || "",
  });

  const advance = useWrapMutation(() => advanceWrapProject(id, next), "Project advanced", refresh);
  const saveVehicle = useWrapMutation(() => updateWrapVehicle(vehicle.id, { ...vehicleForm, odometer: vehicleForm.odometer ? Number(vehicleForm.odometer) : undefined }), "Vehicle intake saved", refresh);
  const saveSpecs = useWrapMutation(() => updateWrapProject(id, {
    project_type: specForm.project_type,
    coverage_summary: specForm.coverage_summary,
    specifications: {
      material: specForm.material,
      laminate: specForm.laminate,
      panels_included: splitCsv(specForm.panels_included),
      panels_excluded: splitCsv(specForm.panels_excluded),
      finishing: specForm.finishing,
      installer_notes: specForm.installer_notes,
      warranty: specForm.warranty,
    },
  }), "Wrap specifications saved", refresh);
  const coverage = useWrapMutation(() => createCoveragePlan(id, {
    coverage_level: coverageForm.coverage_level,
    panels: parsePanels(coverageForm.panels),
    notes: coverageForm.notes,
  }), "Coverage plan saved", refresh);
  const inspection = useWrapMutation(() => createInspection(id, {
    inspection_type: inspectionForm.inspection_type,
    status: "ready_for_signature",
    required_views: splitCsv(inspectionForm.required_views),
    before_photo_file_ids: splitCsv(inspectionForm.before_photo_file_ids),
    damage_items: inspectionForm.damage_panel ? [{ panel: inspectionForm.damage_panel, type: inspectionForm.damage_type, severity: inspectionForm.severity, notes: inspectionForm.damage_notes, recorded_at: new Date().toISOString() }] : [],
    surface_conditions: [{ notes: inspectionForm.notes, recorded_at: new Date().toISOString() }],
    notes: inspectionForm.notes,
  }), "Inspection saved", refresh);
  const acknowledge = useWrapMutation(() => acknowledgeInspection(latestInspection(detail.data)?.id, { ...ackForm, signature_type: "typed" }), "Inspection acknowledged", refresh);
  const design = useWrapMutation(() => createDesignScene(id, {
    vehicle_template_key: designForm.vehicle_template_key || vehicle.template_key,
    layers: [
      { id: "template", type: "vehicle_template", name: "Vehicle template", locked: true },
      designForm.source_file_id ? { id: "artwork-1", type: "logo_asset", name: designForm.layer_name || "Linked artwork", locked: true, source_file_id: designForm.source_file_id, original_format: "source" } : null,
    ].filter(Boolean),
    notes: designForm.notes,
  }), "Artwork scene saved", refresh);
  const panelPlan = useWrapMutation(() => createPanelPlan(id, { status: "ready_for_production", printer_max_width_inches: Number(panelForm.printer_max_width_inches || 54), panels: parsePanels(panelForm.panels), notes: panelForm.notes }), "Production panel plan saved", refresh);
  const schedule = useWrapMutation(() => createWrapSchedule(id, { schedule_type: "install", status: "scheduled", ...scheduleForm }), "Install scheduled", refresh);
  const installation = useWrapMutation(() => createInstallationRecord(id, {
    status: installForm.status,
    crew_names: splitCsv(installForm.crew_names),
    actual_start_at: installForm.actual_start_at || undefined,
    actual_end_at: installForm.actual_end_at || undefined,
    location: installForm.location,
    preparation_checklist: splitLines(installForm.preparation).map((label) => ({ label, complete: true })),
    installation_checklist: splitLines(installForm.checklist).map((label) => ({ label, complete: true })),
    quality_notes: installForm.quality_notes,
    completion_photo_file_ids: splitCsv(installForm.completion_photo_file_ids),
  }), "Installation/QC record saved", refresh);
  const handoff = useWrapMutation(() => handoffWrapProject(id, { override_reason: handoffReason || undefined }), "Production handoff complete", refresh);
  const packet = useWrapMutation(() => generateWrapPacket(id, packetType), "Packet generated", refresh);

  if (detail.isLoading) return <div className="p-6 text-sm text-muted-foreground">Loading...</div>;
  if (!project) return <div className="p-6 text-sm text-rose-700">Wrap Lab project not found.</div>;
  const readiness = detail.data?.readiness || { blockers: [], warnings: [] };
  const latestPreInspection = latestInspection(detail.data);

  return (
    <div className="space-y-4" data-testid="wrap-lab-detail-page">
      <PageHeader
        title={project.project_name}
        subtitle={`${project.project_type.replace(/_/g, " ")} · ${project.status.replace(/_/g, " ")}`}
        actions={(
          <div className="flex items-center gap-2 flex-wrap">
            <AIContextualActions contextType="wrap_project" contextId={id} actions={[
              { label: "AI Create Mockup", tool: "vehicle_graphics_studio", mode: "vehicle_wrap_concept" },
              { label: "AI Help Describe Damage", tool: "vehicle_graphics_studio", mode: "wrap_damage_description" },
              { label: "AI Suggest Coverage Notes", tool: "pricing_profitability", mode: "wrap_cost_guidance" },
            ]} />
            <Button asChild variant="outline" size="sm"><Link to="/wrap-lab">Back</Link></Button>
          </div>
        )}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_340px]">
        <Card data-testid="wrap-readiness-panel">
          <CardHeader><CardTitle className="text-base flex items-center gap-2">{readiness.ready ? <CheckCircle2 className="size-4 text-emerald-600" /> : <AlertTriangle className="size-4 text-amber-600" />}Wrap readiness</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Badge variant={readiness.ready ? "default" : "outline"}>{readiness.ready ? "Ready for production" : "Action required"}</Badge>
            {readiness.blockers?.map((b) => <div key={b.code} className="rounded border border-amber-200 bg-amber-50 p-2"><div className="font-medium">{b.label}</div><div className="text-xs text-muted-foreground">{b.required_action}</div></div>)}
            {readiness.warnings?.map((w) => <div key={w.code} className="rounded border p-2"><div className="font-medium">{w.label}</div><div className="text-xs text-muted-foreground">{w.required_action}</div></div>)}
            <div className="flex flex-wrap gap-2">
              <Button size="sm" disabled={!next || advance.isPending} onClick={() => advance.mutate()} data-testid="wrap-advance"><ShieldCheck className="size-4 mr-1" />Advance</Button>
              <Button size="sm" variant="outline" disabled={handoff.isPending} onClick={() => handoff.mutate()} data-testid="wrap-production-handoff"><Truck className="size-4 mr-1" />Production handoff</Button>
              <Button asChild size="sm" variant="outline"><Link to={`/approval-center?target_type=order_item&target_id=${project.order_item_id || ""}&customer_id=${project.customer_id}&wrap_project_id=${project.id}&wrap_project_revision=${project.approval_revision || 1}`}>Current approval</Link></Button>
            </div>
            {!readiness.ready && <Input placeholder="Override reason for authorized handoff" value={handoffReason} onChange={(e) => setHandoffReason(e.target.value)} data-testid="wrap-handoff-reason" />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Linked authority</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <LinkRow label="Customer" value={detail.data?.customer?.name || project.customer_id} to={`/customers/${project.customer_id}`} />
            {project.quote_id && <LinkRow label="Quote" value={project.quote_id} to={`/quotes/${project.quote_id}`} />}
            {project.order_id && <LinkRow label="Order" value={detail.data?.order?.number ? `O-${detail.data.order.number}` : project.order_id} to={`/orders/${project.order_id}`} />}
            {project.work_order_id && <LinkRow label="Work Order" value={detail.data?.work_order?.number ? `W-${detail.data.work_order.number}` : project.work_order_id} to={`/work-orders/${project.work_order_id}`} />}
            <div className="pt-2 text-xs text-muted-foreground">Order Items, Quotes, Orders, invoices, and pricing snapshots remain the commercial authority.</div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="intake" className="space-y-4">
        <TabsList className="flex h-auto flex-wrap justify-start">
          <TabsTrigger value="intake">Vehicle & Specs</TabsTrigger>
          <TabsTrigger value="inspection">Inspection</TabsTrigger>
          <TabsTrigger value="proofs">Proofs & Files</TabsTrigger>
          <TabsTrigger value="production">Production</TabsTrigger>
          <TabsTrigger value="install">Install & QC</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="intake" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="text-base">Vehicle intake</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {!vehicleForm ? (
                <SummaryGrid rows={[["Vehicle", `${vehicle.year || ""} ${vehicle.make || ""} ${vehicle.model || ""}`], ["Body", vehicle.body_style || vehicle.trim || "Not captured"], ["VIN", vehicle.vin || "Not captured"], ["Color", vehicle.color || "Not captured"], ["Unit", vehicle.unit_number || "Not captured"], ["Instructions", vehicle.customer_instructions || "None"]]} />
              ) : (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  {["year", "make", "model", "body_style", "vin", "license_plate", "color", "unit_number", "odometer", "installation_location"].map((field) => <Field key={field} label={field.replace(/_/g, " ")} value={vehicleForm[field]} onChange={(v) => setVehicleForm({ ...vehicleForm, [field]: v })} />)}
                  <TextField label="Requested coverage" value={vehicleForm.requested_coverage} onChange={(v) => setVehicleForm({ ...vehicleForm, requested_coverage: v })} />
                  <TextField label="Customer instructions" value={vehicleForm.customer_instructions} onChange={(v) => setVehicleForm({ ...vehicleForm, customer_instructions: v })} />
                </div>
              )}
              <Button size="sm" variant={vehicleForm ? "default" : "outline"} onClick={vehicleForm ? () => saveVehicle.mutate() : ensureVehicleForm} disabled={saveVehicle.isPending}>{vehicleForm ? "Save vehicle intake" : "Edit vehicle intake"}</Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Wrap specifications</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {!specForm ? (
                <SummaryGrid rows={[["Coverage", project.coverage_summary || project.project_type], ["Material", project.specifications?.material || "Not selected"], ["Laminate", project.specifications?.laminate || "Not selected"], ["Finishing", project.specifications?.finishing || "Not captured"], ["Installer notes", project.specifications?.installer_notes || "None"]]} />
              ) : (
                <div className="space-y-3">
                  <Select value={specForm.project_type} onValueChange={(project_type) => setSpecForm({ ...specForm, project_type })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{coverageOptions.map((o) => <SelectItem key={o} value={o}>{o.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select>
                  <TextField label="Coverage summary" value={specForm.coverage_summary} onChange={(v) => setSpecForm({ ...specForm, coverage_summary: v })} />
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    {["material", "laminate", "panels_included", "panels_excluded", "finishing", "installer_notes", "warranty"].map((field) => <Field key={field} label={field.replace(/_/g, " ")} value={specForm[field]} onChange={(v) => setSpecForm({ ...specForm, [field]: v })} />)}
                  </div>
                </div>
              )}
              <Button size="sm" variant={specForm ? "default" : "outline"} onClick={specForm ? () => saveSpecs.mutate() : ensureSpecForm} disabled={saveSpecs.isPending}>{specForm ? "Save specifications" : "Edit specifications"}</Button>
            </CardContent>
          </Card>
          <FormCard title="Measured coverage" icon={PackageCheck} action="Save coverage plan" onSubmit={() => coverage.mutate()} disabled={coverage.isPending}>
            <Select value={coverageForm.coverage_level} onValueChange={(coverage_level) => setCoverageForm({ ...coverageForm, coverage_level })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{coverageOptions.map((o) => <SelectItem key={o} value={o}>{o.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select>
            <TextField label="Panels as name,width,height" value={coverageForm.panels} onChange={(v) => setCoverageForm({ ...coverageForm, panels: v })} />
            <TextField label="Notes" value={coverageForm.notes} onChange={(v) => setCoverageForm({ ...coverageForm, notes: v })} />
          </FormCard>
        </TabsContent>

        <TabsContent value="inspection" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <FormCard title="Pre/post inspection" icon={ShieldCheck} action="Save inspection" onSubmit={() => inspection.mutate()} disabled={inspection.isPending} testId="wrap-inspection-form">
            <Select value={inspectionForm.inspection_type} onValueChange={(inspection_type) => setInspectionForm({ ...inspectionForm, inspection_type })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="pre_install">Pre-install</SelectItem><SelectItem value="completion">Post-install</SelectItem></SelectContent></Select>
            <Field label="Required views" value={inspectionForm.required_views} onChange={(v) => setInspectionForm({ ...inspectionForm, required_views: v })} />
            <Field label="Photo file IDs" value={inspectionForm.before_photo_file_ids} onChange={(v) => setInspectionForm({ ...inspectionForm, before_photo_file_ids: v })} />
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <Field label="Damage panel" value={inspectionForm.damage_panel} onChange={(v) => setInspectionForm({ ...inspectionForm, damage_panel: v })} testId="wrap-damage-panel" />
              <Field label="Damage type" value={inspectionForm.damage_type} onChange={(v) => setInspectionForm({ ...inspectionForm, damage_type: v })} />
              <Field label="Severity" value={inspectionForm.severity} onChange={(v) => setInspectionForm({ ...inspectionForm, severity: v })} />
            </div>
            <TextField label="Damage and surface notes" value={inspectionForm.damage_notes} onChange={(v) => setInspectionForm({ ...inspectionForm, damage_notes: v })} testId="wrap-damage-notes" />
            <div className="rounded border p-2 text-xs text-muted-foreground"><Bot className="mr-1 inline size-3" />AI Help Describe Damage is available above as an explicit action. Manual notes are always supported.</div>
          </FormCard>
          <Card>
            <CardHeader><CardTitle className="text-base">Customer acknowledgment</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="text-sm text-muted-foreground">Signed inspections are immutable. Corrections must be added as a new version or addendum.</div>
              <SummaryList label="Inspections" items={(detail.data?.inspections || []).map((i) => `${i.inspection_type} v${i.version || 1} · ${i.status}`)} />
              {latestPreInspection && <InspectionSharePanel inspection={latestPreInspection} />}
              <Field label="Signer name" value={ackForm.signer_name} onChange={(v) => setAckForm({ ...ackForm, signer_name: v })} />
              <Field label="Signer email" value={ackForm.signer_email} onChange={(v) => setAckForm({ ...ackForm, signer_email: v })} />
              <Field label="Typed signature" value={ackForm.signature_data} onChange={(v) => setAckForm({ ...ackForm, signature_data: v })} />
              <Button size="sm" onClick={() => acknowledge.mutate()} disabled={!latestPreInspection || !ackForm.signer_name || !ackForm.signature_data || acknowledge.isPending} data-testid="wrap-inspection-acknowledge">Acknowledge latest inspection</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="proofs" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <FormCard title="Artwork scene" icon={Layers} action="Save artwork scene" onSubmit={() => design.mutate()} disabled={design.isPending}>
            <Field label="Vehicle template" value={designForm.vehicle_template_key} onChange={(v) => setDesignForm({ ...designForm, vehicle_template_key: v })} />
            <Field label="Linked artwork file ID" value={designForm.source_file_id} onChange={(v) => setDesignForm({ ...designForm, source_file_id: v })} />
            <Field label="Layer label" value={designForm.layer_name} onChange={(v) => setDesignForm({ ...designForm, layer_name: v })} />
            <TextField label="Manual artwork notes" value={designForm.notes} onChange={(v) => setDesignForm({ ...designForm, notes: v })} />
          </FormCard>
          <Card>
            <CardHeader><CardTitle className="text-base">Proof, Decision Room, and files</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <SummaryList label="Approvals" items={(detail.data?.approvals || []).map((a) => `${a.parent_type}: ${a.action}`)} />
              <SummaryList label="Decision Rooms" items={(detail.data?.decision_rooms || []).map((r) => `${r.title || r.id} · ${r.status}`)} />
              <SummaryList label="Proofs" items={(detail.data?.proofs || []).map((p) => `${p.title || p.id} · ${p.status}`)} />
              <SummaryList label="Files/Documents" items={[...(detail.data?.linked_assets?.files || []), ...(detail.data?.linked_assets?.documents || [])].map((f) => f.title || f.name || f.filename || f.id)} />
              <Button asChild size="sm" variant="outline"><Link to={`/approval-center?target_type=order_item&target_id=${project.order_item_id || ""}&customer_id=${project.customer_id}`}>Create/open approval work</Link></Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="production" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <FormCard title="Production panel plan" icon={PackageCheck} action="Save ready panel plan" onSubmit={() => panelPlan.mutate()} disabled={panelPlan.isPending}>
            <Field label="Printer max width" value={panelForm.printer_max_width_inches} onChange={(v) => setPanelForm({ ...panelForm, printer_max_width_inches: v })} />
            <TextField label="Panels as name,width,height" value={panelForm.panels} onChange={(v) => setPanelForm({ ...panelForm, panels: v })} />
            <TextField label="Production notes" value={panelForm.notes} onChange={(v) => setPanelForm({ ...panelForm, notes: v })} />
          </FormCard>
          <FormCard title="Installation schedule" icon={CalendarClock} action="Schedule install" onSubmit={() => schedule.mutate()} disabled={schedule.isPending}>
            <Field label="Title" value={scheduleForm.title} onChange={(v) => setScheduleForm({ ...scheduleForm, title: v })} />
            <Field label="Start ISO" value={scheduleForm.start_at} onChange={(v) => setScheduleForm({ ...scheduleForm, start_at: v })} />
            <Field label="End ISO" value={scheduleForm.end_at} onChange={(v) => setScheduleForm({ ...scheduleForm, end_at: v })} />
            <Field label="Location" value={scheduleForm.location} onChange={(v) => setScheduleForm({ ...scheduleForm, location: v })} />
            <TextField label="Notes" value={scheduleForm.notes} onChange={(v) => setScheduleForm({ ...scheduleForm, notes: v })} />
          </FormCard>
        </TabsContent>

        <TabsContent value="install" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <FormCard title="Installation and quality control" icon={Truck} action="Save installation/QC" onSubmit={() => installation.mutate()} disabled={installation.isPending}>
            <Select value={installForm.status} onValueChange={(status) => setInstallForm({ ...installForm, status })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["planned", "in_progress", "blocked", "completed", "rework_required", "canceled"].map((s) => <SelectItem key={s} value={s}>{s.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select>
            <Field label="Crew names" value={installForm.crew_names} onChange={(v) => setInstallForm({ ...installForm, crew_names: v })} />
            <Field label="Actual start" value={installForm.actual_start_at} onChange={(v) => setInstallForm({ ...installForm, actual_start_at: v })} />
            <Field label="Actual end" value={installForm.actual_end_at} onChange={(v) => setInstallForm({ ...installForm, actual_end_at: v })} />
            <TextField label="Preparation checklist" value={installForm.preparation} onChange={(v) => setInstallForm({ ...installForm, preparation: v })} />
            <TextField label="Installation checklist" value={installForm.checklist} onChange={(v) => setInstallForm({ ...installForm, checklist: v })} />
            <TextField label="Quality notes" value={installForm.quality_notes} onChange={(v) => setInstallForm({ ...installForm, quality_notes: v })} />
          </FormCard>
          <Card>
            <CardHeader><CardTitle className="text-base">Packets and aftercare</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <Select value={packetType} onValueChange={setPacketType}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="pre_install">Pre-install</SelectItem><SelectItem value="work_order">Work order</SelectItem><SelectItem value="completion">Completion</SelectItem><SelectItem value="warranty_aftercare">Warranty aftercare</SelectItem></SelectContent></Select>
              <Button size="sm" onClick={() => packet.mutate()} disabled={packet.isPending}><FileText className="size-4 mr-1" />Generate packet snapshot</Button>
              <SummaryList label="Installation/QC records" items={(detail.data?.installation_records || []).map((r) => `${r.status} · ${r.location || "shop"}`)} />
              <SummaryList label="Packets" items={(detail.data?.packets || []).map((p) => `${p.packet_type} rev ${p.revision}`)} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardHeader><CardTitle className="text-base">Lifecycle timeline</CardTitle></CardHeader>
            <CardContent className="divide-y rounded border text-sm">
              {(detail.data?.timeline || []).map((event, idx) => (
                <div key={`${event.kind}-${event.entity_id}-${idx}`} className="grid grid-cols-1 gap-1 p-2 md:grid-cols-[180px_1fr_auto]">
                  <div className="text-xs text-muted-foreground">{event.at ? formatDateTime(event.at) : ""}</div>
                  <div>{event.label}</div>
                  <Badge variant="outline">{event.status || event.kind}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function splitCsv(value) {
  return String(value || "").split(",").map((v) => v.trim()).filter(Boolean);
}

function splitLines(value) {
  return String(value || "").split(/\r?\n/).map((v) => v.trim()).filter(Boolean);
}

function parsePanels(value) {
  return splitLines(value).map((line) => {
    const [name, width, height] = line.split(",").map((part) => part.trim());
    return { name, width_inches: Number(width || 0), height_inches: Number(height || 0), status: "measured", selected: true };
  }).filter((panel) => panel.name);
}

function latestInspection(data) {
  const inspections = (data?.inspections || []).filter((inspection) => inspection.status !== "superseded");
  return inspections.sort((a, b) => String(b.updated_at || b.created_at || "").localeCompare(String(a.updated_at || a.created_at || "")))[0];
}

function buildPublicInspectionUrl(inspectionId, token) {
  return `${window.location.origin}/p/wrap-inspections/${inspectionId}?t=${encodeURIComponent(token)}`;
}

function tokenStatus(token) {
  if (token.computed_status) return token.computed_status;
  if (token.revoked || token.status === "revoked") return "revoked";
  if (token.status === "completed" || token.completed_at) return "completed";
  if (token.status === "superseded") return "superseded";
  if (token.first_viewed_at) return "viewed";
  return token.status || "active";
}

function InspectionSharePanel({ inspection }) {
  const qc = useQueryClient();
  const [audienceEmail, setAudienceEmail] = useState("");
  const [latestLink, setLatestLink] = useState("");
  const links = useQuery({
    queryKey: ["wrap-inspection-review-links", inspection.id],
    queryFn: () => listInspectionReviewLinks(inspection.id),
    enabled: Boolean(inspection?.id),
  });
  const refreshLinks = () => qc.invalidateQueries({ queryKey: ["wrap-inspection-review-links", inspection.id] });
  const createLink = useMutation({
    mutationFn: () => createInspectionReviewLink(inspection.id, { audience_email: audienceEmail || null, ttl_hours: 168 }),
    onSuccess: (data) => {
      setLatestLink(buildPublicInspectionUrl(inspection.id, data.token));
      refreshLinks();
      toast.success("Inspection link created. Copy it manually or send it through an approved channel.");
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const resend = useMutation({
    mutationFn: () => createInspectionReviewLink(inspection.id, { audience_email: audienceEmail || null, ttl_hours: 168, note: "Replacement link issued from Wrap Lab" }),
    onSuccess: (data) => {
      setLatestLink(buildPublicInspectionUrl(inspection.id, data.token));
      refreshLinks();
      toast.success("Replacement inspection link created. Delivery was not marked as sent.");
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const expire = useMutation({
    mutationFn: (tokenId) => expireInspectionReviewLink(tokenId),
    onSuccess: refreshLinks,
    onError: (error) => toast.error(extractError(error)),
  });
  const revoke = useMutation({
    mutationFn: (tokenId) => revokeInspectionReviewLink(tokenId),
    onSuccess: refreshLinks,
    onError: (error) => toast.error(extractError(error)),
  });
  const copyLatest = async () => {
    if (!latestLink) return;
    try {
      await navigator.clipboard?.writeText(latestLink);
      toast.success("Inspection link copied");
    } catch {
      toast.message("Copy the displayed link manually.");
    }
  };
  const items = links.data?.items || [];
  return (
    <div className="rounded-md border p-3 space-y-3" data-testid="wrap-inspection-share-panel">
      <div className="font-medium text-sm">Customer review link</div>
      <div className="flex flex-wrap gap-2">
        <Input
          value={audienceEmail}
          onChange={(event) => setAudienceEmail(event.target.value)}
          placeholder="customer@example.com"
          className="min-w-0 flex-1"
          data-testid="wrap-inspection-share-email"
        />
        <Button type="button" size="sm" onClick={() => createLink.mutate()} disabled={createLink.isPending || inspection.status === "superseded"} data-testid="wrap-inspection-share-create">
          <Link2 className="size-4 mr-1" /> Create link
        </Button>
      </div>
      <div className="text-xs text-muted-foreground">
        This creates a secure inspection review link for v{inspection.version || 1}. Email or SMS delivery is not marked successful by this service.
      </div>
      {latestLink && (
        <div className="grid gap-2" data-testid="wrap-inspection-share-latest">
          <Label className="text-xs">Latest one-time-visible link</Label>
          <div className="flex gap-2">
            <Input readOnly value={latestLink} />
            <Button type="button" size="sm" variant="outline" onClick={copyLatest} data-testid="wrap-inspection-share-copy"><Copy className="size-4 mr-1" />Copy</Button>
          </div>
        </div>
      )}
      <div className="space-y-2" data-testid="wrap-inspection-share-history">
        {items.length === 0 ? <div className="text-xs text-muted-foreground">No inspection links have been created yet.</div> : items.map((token) => (
          <div key={token.id} className="rounded border p-2 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="font-medium">{token.audience_email || "Manual share link"}</div>
                <div className="text-muted-foreground">Version {token.parent_version || token.inspection_version || "current"}{token.expires_at ? ` · expires ${String(token.expires_at).slice(0, 16)}` : ""}</div>
              </div>
              <Badge variant="outline">{tokenStatus(token)}</Badge>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="outline" onClick={() => resend.mutate(token.id)} disabled={resend.isPending}><RotateCw className="size-4 mr-1" />Resend</Button>
              {!["revoked", "expired", "superseded", "completed"].includes(tokenStatus(token)) && (
                <>
                  <Button type="button" size="sm" variant="outline" onClick={() => expire.mutate(token.id)} disabled={expire.isPending}><TimerOff className="size-4 mr-1" />Expire</Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => revoke.mutate(token.id)} disabled={revoke.isPending}><ShieldOff className="size-4 mr-1" />Revoke</Button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Field({ label, value, onChange, testId }) {
  return (
    <div className="grid gap-1.5">
      <Label className="capitalize">{label}</Label>
      <Input value={value || ""} onChange={(e) => onChange(e.target.value)} data-testid={testId} />
    </div>
  );
}

function TextField({ label, value, onChange, testId }) {
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Textarea value={value || ""} onChange={(e) => onChange(e.target.value)} rows={3} data-testid={testId} />
    </div>
  );
}

function FormCard({ title, icon: Icon, action, children, onSubmit, disabled, testId }) {
  return (
    <Card data-testid={testId}>
      <CardHeader><CardTitle className="text-base flex items-center gap-2"><Icon className="size-4" />{title}</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {children}
        <Button size="sm" onClick={onSubmit} disabled={disabled}>{action}</Button>
      </CardContent>
    </Card>
  );
}

function SummaryGrid({ rows }) {
  return (
    <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
      {rows.map(([label, value]) => <div key={label} className="rounded border p-2"><div className="text-xs text-muted-foreground">{label}</div><div className="font-medium">{value}</div></div>)}
    </div>
  );
}

function SummaryList({ label, items }) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="mt-2 rounded border divide-y">
        {(items || []).slice(0, 6).map((item, idx) => <div key={`${item}-${idx}`} className="p-2 text-xs">{item}</div>)}
        {(!items || items.length === 0) && <div className="p-2 text-xs text-muted-foreground">None linked yet</div>}
      </div>
    </div>
  );
}

function LinkRow({ label, value, to }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded border p-2">
      <span className="text-muted-foreground">{label}</span>
      <Button asChild size="sm" variant="link"><Link to={to}>{value}</Link></Button>
    </div>
  );
}
