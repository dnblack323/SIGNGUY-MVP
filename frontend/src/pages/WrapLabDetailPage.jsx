import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, FileText, Layers, Lock, PackageCheck, ShieldCheck } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import AIContextualActions from "@/components/ai/AIContextualActions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { extractError } from "@/lib/api";
import { centsToDollarsString, formatDateTime } from "@/lib/format";
import {
  advanceWrapProject,
  createCoveragePlan,
  createDesignScene,
  createInspection,
  createPanelPlan,
  createWrapSchedule,
  createWrapWarranty,
  generateWrapPacket,
  getWrapProject,
} from "@/lib/wrapLab";
import { toast } from "sonner";

const statusOrder = ["lead_intake", "vehicle_recorded", "measurement_planning", "estimate_ready", "quote_linked", "contract_deposit_pending", "pre_install_ready", "pre_install_signed", "design_in_progress", "proof_ready", "proof_approved", "panel_plan_ready", "production_ready", "install_scheduled", "installing", "completion_packet_ready", "completed", "warranty_active"];

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

function vehicleDiagram() {
  return (
    <svg viewBox="0 0 520 210" className="w-full h-auto rounded border bg-white">
      <rect x="60" y="55" width="400" height="95" rx="18" fill="#f8fafc" stroke="#334155" strokeWidth="3" />
      <path d="M135 55 L180 25 H330 L385 55" fill="#e0f2fe" stroke="#334155" strokeWidth="3" />
      <line x1="260" y1="55" x2="260" y2="150" stroke="#94a3b8" strokeWidth="2" />
      <line x1="150" y1="70" x2="150" y2="142" stroke="#94a3b8" strokeWidth="2" />
      <line x1="370" y1="70" x2="370" y2="142" stroke="#94a3b8" strokeWidth="2" />
      <circle cx="145" cy="155" r="28" fill="#111827" />
      <circle cx="375" cy="155" r="28" fill="#111827" />
      <circle cx="145" cy="155" r="12" fill="#cbd5e1" />
      <circle cx="375" cy="155" r="12" fill="#cbd5e1" />
      <text x="260" y="196" textAnchor="middle" fontSize="14" fill="#475569">flat production profile</text>
    </svg>
  );
}

export default function WrapLabDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [packetType, setPacketType] = useState("pre_install");
  const detail = useQuery({ queryKey: ["wrap-lab-project", id], queryFn: () => getWrapProject(id), enabled: !!id });
  const project = detail.data?.project;
  const next = useMemo(() => nextStatus(project?.status), [project?.status]);
  const refresh = () => qc.invalidateQueries({ queryKey: ["wrap-lab-project", id] });
  const advance = useWrapMutation(() => advanceWrapProject(id, next), "Project advanced", refresh);
  const coverage = useWrapMutation(() => createCoveragePlan(id, {
    coverage_level: "partial_wrap",
    panels: [
      { name: "Driver front door", width_inches: 42, height_inches: 36, status: "measured" },
      { name: "Passenger front door", width_inches: 42, height_inches: 36, status: "measured" },
      { name: "Hood", width_inches: 65, height_inches: 50, status: "measured" },
    ],
  }), "Coverage plan created", refresh);
  const inspection = useWrapMutation(() => createInspection(id, {
    inspection_type: "pre_install",
    status: "ready_for_signature",
    damage_items: [{ panel: "Driver front door", type: "scratch", notes: "Pre-existing surface scratch", x: 34, y: 42 }],
    acknowledgements: [{ text: "Installation reflects current paint condition", accepted: true }],
  }), "Inspection created", refresh);
  const design = useWrapMutation(() => createDesignScene(id, {
    vehicle_template_key: detail.data?.vehicle?.template_key || "sprinter_van_flat",
    artboard: { width_inches: 220, height_inches: 84 },
    scale: { unit: "inch", pixels_per_inch: 8 },
    layers: [
      { id: "template", type: "vehicle_template", name: "Vehicle template", locked: true },
      { id: "logo-primary", type: "logo_asset", name: "Primary logo", locked: true, source_file_id: "original-logo-file", original_format: "svg" },
      { id: "background-1", type: "shape", name: "Background sweep", locked: false, fill: "#0f766e" },
    ],
  }), "Vector scene created", refresh);
  const panelPlan = useWrapMutation(() => createPanelPlan(id, {
    status: "ready_for_production",
    printer_max_width_inches: 54,
    panels: [
      { name: "Driver side", width_inches: 196, height_inches: 70 },
      { name: "Passenger side", width_inches: 196, height_inches: 70 },
      { name: "Rear", width_inches: 72, height_inches: 64 },
    ],
    material_cost_cents: 84000,
    labor_cost_cents: 220000,
  }), "Panel plan created", refresh);
  const schedule = useWrapMutation(() => createWrapSchedule(id, { schedule_type: "install", title: "Wrap install", start_at: new Date().toISOString(), end_at: new Date(Date.now() + 4 * 3600000).toISOString() }), "Install scheduled", refresh);
  const warranty = useWrapMutation(() => createWrapWarranty(id, { status: "active", starts_at: new Date().toISOString(), coverage_terms: ["Installation workmanship warranty"], care_instructions: ["Hand wash only for two weeks", "Avoid close pressure washing"], warranty_value_cents: 0 }), "Warranty created", refresh);
  const packet = useWrapMutation(() => generateWrapPacket(id, packetType), "Packet generated", refresh);

  if (detail.isLoading) return <div className="p-6 text-sm text-muted-foreground">Loading...</div>;
  if (!project) return <div className="p-6 text-sm text-rose-700">Wrap Lab project not found.</div>;

  return (
    <div className="space-y-4" data-testid="wrap-lab-detail-page">
      <PageHeader
        title={project.project_name}
        subtitle={`${project.project_type.replace(/_/g, " ")} · ${project.status.replace(/_/g, " ")}`}
        actions={(
          <div className="flex items-center gap-2 flex-wrap">
            <AIContextualActions contextType="wrap_project" contextId={id} actions={[
              { label: "Wrap Concept", tool: "vehicle_graphics_studio", mode: "vehicle_wrap_concept" },
              { label: "Cost Guidance", tool: "pricing_profitability", mode: "wrap_cost_guidance" },
            ]} />
            <Button asChild variant="outline" size="sm"><Link to="/wrap-lab">Back</Link></Button>
          </div>
        )}
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_.9fr] gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Vehicle Layout</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {vehicleDiagram()}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><div className="text-muted-foreground">Vehicle</div><div className="font-medium">{detail.data?.vehicle ? `${detail.data.vehicle.year || ""} ${detail.data.vehicle.make} ${detail.data.vehicle.model}` : "No vehicle linked"}</div></div>
              <div><div className="text-muted-foreground">Estimate</div><div className="font-medium">{centsToDollarsString(project.estimate_total_cents)}</div></div>
              <div><div className="text-muted-foreground">Deposit</div><div className="font-medium">{centsToDollarsString(project.deposit_required_cents)}</div></div>
              <div><div className="text-muted-foreground">Due</div><div className="font-medium">{project.due_at ? formatDateTime(project.due_at) : "Not set"}</div></div>
            </div>
            <Button disabled={!next || advance.isPending} onClick={() => advance.mutate()} data-testid="wrap-advance">
              <ShieldCheck className="size-4 mr-2" />Advance to {next ? next.replace(/_/g, " ") : "complete"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Packet Builder</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Select value={packetType} onValueChange={setPacketType}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="pre_install">Pre-install</SelectItem>
                <SelectItem value="work_order">Work order</SelectItem>
                <SelectItem value="completion">Completion</SelectItem>
                <SelectItem value="warranty_aftercare">Warranty aftercare</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={() => packet.mutate()} disabled={packet.isPending}><FileText className="size-4 mr-2" />Generate packet</Button>
            <div className="rounded border divide-y text-sm">
              {(detail.data?.packets || []).map((p) => <div key={p.id} className="p-2 flex justify-between"><span>{p.packet_type.replace(/_/g, " ")}</span><Badge variant="outline">rev {p.revision}</Badge></div>)}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ActionCard title="Coverage" icon={PackageCheck} count={detail.data?.coverage_plans?.length} action="Create panel plan" onClick={() => coverage.mutate()} disabled={coverage.isPending} />
        <ActionCard title="Inspection" icon={ShieldCheck} count={detail.data?.inspections?.length} action="Create pre-install" onClick={() => inspection.mutate()} disabled={inspection.isPending} />
        <ActionCard title="Vector Scene" icon={Layers} count={detail.data?.design_scenes?.length} action="Create scene" onClick={() => design.mutate()} disabled={design.isPending} />
        <ActionCard title="Production Panels" icon={Lock} count={detail.data?.panel_plans?.length} action="Create panels" onClick={() => panelPlan.mutate()} disabled={panelPlan.isPending} />
        <ActionCard title="Schedule" icon={CalendarClock} count={detail.data?.schedules?.length} action="Schedule install" onClick={() => schedule.mutate()} disabled={schedule.isPending} />
        <ActionCard title="Warranty" icon={FileText} count={detail.data?.warranties?.length} action="Create aftercare" onClick={() => warranty.mutate()} disabled={warranty.isPending} />
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Production Summary</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <SummaryList label="Coverage panels" items={(detail.data?.coverage_plans || []).flatMap((p) => p.panels || []).map((p) => `${p.name}: ${p.width_inches}x${p.height_inches}`)} />
          <SummaryList label="Damage log" items={(detail.data?.inspections || []).flatMap((i) => i.damage_items || []).map((d) => `${d.panel}: ${d.type}`)} />
          <SummaryList label="Export panels" items={(detail.data?.panel_plans || []).flatMap((p) => p.export_manifest?.panels || []).map((p) => `${p.label}: ${p.source_panel}`)} />
        </CardContent>
      </Card>
    </div>
  );
}

function ActionCard({ title, icon: Icon, count, action, onClick, disabled }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-base flex items-center gap-2"><Icon className="size-4" />{title}</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="text-2xl font-semibold">{count || 0}</div>
        <Button size="sm" variant="outline" onClick={onClick} disabled={disabled}>{action}</Button>
      </CardContent>
    </Card>
  );
}

function SummaryList({ label, items }) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="mt-2 rounded border divide-y">
        {(items || []).slice(0, 5).map((item, idx) => <div key={`${item}-${idx}`} className="p-2 text-xs">{item}</div>)}
        {(!items || items.length === 0) && <div className="p-2 text-xs text-muted-foreground">None yet</div>}
      </div>
    </div>
  );
}
