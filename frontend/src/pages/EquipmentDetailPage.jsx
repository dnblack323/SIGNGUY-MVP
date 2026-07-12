import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import StatusPill from "@/components/common/StatusPill";
import EmptyState from "@/components/common/EmptyState";
import { toast } from "sonner";
import { formatDate } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";
import { ArrowLeft, Archive, FileText, Save, ShieldAlert } from "lucide-react";

const CATEGORIES = ["printer", "laminator", "plotter", "cutter", "heat_press", "embroidery_machine", "lift", "vehicle", "specialty_tool", "other"];
const STATUSES = ["active", "inactive", "maintenance", "retired", "archived"];
const ACCESS_POLICIES = [
  { value: "no_required", label: "No certification required" },
  { value: "recommended", label: "Recommended (never blocks)" },
  { value: "required_override_allowed", label: "Required — override allowed" },
  { value: "required_no_override", label: "Required — no override (hard block)" },
];

export default function EquipmentDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canManage = hasPerm("equipment:manage");
  const { data, isLoading } = useQuery({ queryKey: ["equipment-detail", id], queryFn: async () => (await api.get(`/equipment/${id}`)).data });
  const { data: employees } = useQuery({ queryKey: ["employees-for-equipment"], queryFn: async () => (await api.get("/employees")).data.items || [] });
  const [form, setForm] = useState({});

  const employeesById = useMemo(() => {
    const m = {};
    (employees || []).forEach((e) => { m[e.id] = e; });
    return m;
  }, [employees]);

  const save = useMutation({
    mutationFn: async (payload) => (await api.patch(`/equipment/${id}`, payload)).data,
    onSuccess: () => { toast.success("Saved"); qc.invalidateQueries({ queryKey: ["equipment-detail", id] }); setForm({}); },
    onError: (e) => toast.error(extractError(e)),
  });

  const archive = useMutation({
    mutationFn: async () => (await api.post(`/equipment/${id}/archive`)).data,
    onSuccess: () => { toast.success("Equipment archived"); qc.invalidateQueries({ queryKey: ["equipment-detail", id] }); },
    onError: (e) => toast.error(extractError(e)),
  });

  if (isLoading || !data) return <div className="text-sm text-muted-foreground">Loading…</div>;
  const eq = { ...data.equipment, ...form };

  return (
    <div className="space-y-4" data-testid="equipment-detail-page">
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="icon"><Link to="/team/equipment"><ArrowLeft className="size-4" /></Link></Button>
        <PageHeader
          title={<span className="flex items-center gap-2">{data.equipment.name}{data.equipment.safety_sensitive && <ShieldAlert className="size-4 text-amber-600" />}</span>}
          subtitle={<span className="flex items-center gap-2"><StatusPill kind="equipment_status" value={data.equipment.status} /><StatusPill kind="access_policy" value={data.equipment.access_policy} /></span>}
          actions={canManage && data.equipment.status !== "archived" && (
            <Button variant="outline" size="sm" onClick={() => archive.mutate()} disabled={archive.isPending} data-testid="equipment-archive-button">
              <Archive className="size-4 mr-1" />Archive
            </Button>
          )}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        <Tabs defaultValue="overview" data-testid="equipment-detail-tabs">
          <TabsList>
            <TabsTrigger value="overview" data-testid="equipment-tab-overview">Overview</TabsTrigger>
            <TabsTrigger value="training" data-testid="equipment-tab-training">Training</TabsTrigger>
            <TabsTrigger value="certifications" data-testid="equipment-tab-certifications">Certifications</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <Card>
              <CardHeader><CardTitle>Details</CardTitle></CardHeader>
              <CardContent className="grid gap-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5"><Label>Name</Label><Input value={eq.name || ""} disabled={!canManage} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="equipment-detail-name-input" /></div>
                  <div className="grid gap-1.5"><Label>Category</Label>
                    <Select value={eq.category} disabled={!canManage} onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}>
                      <SelectTrigger data-testid="equipment-detail-category-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c} className="capitalize">{c.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5"><Label>Status</Label>
                    <Select value={eq.status} disabled={!canManage} onValueChange={(v) => setForm((f) => ({ ...f, status: v }))}>
                      <SelectTrigger data-testid="equipment-detail-status-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-1.5"><Label>Location</Label><Input value={eq.location || ""} disabled={!canManage} onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))} data-testid="equipment-detail-location-input" /></div>
                </div>
                <div className="grid gap-1.5">
                  <Label>Access policy</Label>
                  <Select value={eq.access_policy} disabled={!canManage} onValueChange={(v) => setForm((f) => ({ ...f, access_policy: v }))}>
                    <SelectTrigger data-testid="equipment-detail-access-policy-select"><SelectValue /></SelectTrigger>
                    <SelectContent>{ACCESS_POLICIES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="flex items-center justify-between rounded-md border px-3 py-2">
                  <Label className="flex items-center gap-1.5"><ShieldAlert className="size-3.5" />Safety-sensitive</Label>
                  <Switch checked={!!eq.safety_sensitive} disabled={!canManage} onCheckedChange={(v) => setForm((f) => ({ ...f, safety_sensitive: v }))} data-testid="equipment-detail-safety-switch" />
                </div>
                <div className="grid gap-1.5"><Label>Description</Label><Textarea rows={3} value={eq.description || ""} disabled={!canManage} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} data-testid="equipment-detail-description-input" /></div>
                <div className="grid gap-1.5"><Label>Safety notes</Label><Textarea rows={2} value={eq.safety_notes || ""} disabled={!canManage} onChange={(e) => setForm((f) => ({ ...f, safety_notes: e.target.value }))} data-testid="equipment-detail-safety-notes-input" /></div>
                {canManage && Object.keys(form).length > 0 && (
                  <Button onClick={() => save.mutate(form)} disabled={save.isPending} data-testid="equipment-detail-save-button"><Save className="size-4 mr-1" />Save</Button>
                )}
                <div className="pt-2 border-t">
                  <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1"><FileText className="size-3.5" />Linked documents</div>
                  {!data.documents?.length ? (
                    <div className="text-sm text-muted-foreground italic">No documents linked yet.</div>
                  ) : (
                    <ul className="text-sm divide-y" data-testid="equipment-documents-list">
                      {data.documents.map((d) => <li key={d.link_id} className="py-1.5">{d.title}</li>)}
                    </ul>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="training">
            <Card>
              <CardHeader><CardTitle>Required Training for this Equipment</CardTitle></CardHeader>
              <CardContent>
                {!data.required_training?.length ? (
                  <EmptyState icon={FileText} title="No Training defined" description="Create a Training Definition on the Training page and link this Equipment." />
                ) : (
                  <ul className="divide-y text-sm" data-testid="equipment-required-training-list">
                    {data.required_training.map((t) => (
                      <li key={t.id} className="py-2 flex items-center justify-between">
                        <span>{t.title}</span>
                        <span className="text-xs text-muted-foreground capitalize">{t.training_type.replace(/_/g, " ")}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {data.pending_training?.length > 0 && (
                  <div className="pt-3 mt-3 border-t">
                    <div className="text-xs text-muted-foreground mb-1">Pending assignments ({data.pending_training.length})</div>
                    <ul className="divide-y text-sm" data-testid="equipment-pending-training-list">
                      {data.pending_training.map((a) => (
                        <li key={a.id} className="py-2 flex items-center justify-between">
                          <span>{employeesById[a.employee_id]?.name || a.employee_id}</span>
                          <StatusPill kind="training_assignment" value={a.status} />
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="certifications">
            <Card>
              <CardHeader><CardTitle>Certifications for this Equipment</CardTitle></CardHeader>
              <CardContent>
                {!data.certifications?.length ? (
                  <EmptyState icon={ShieldAlert} title="No Certifications issued" description="Issue Certifications from the Certifications page." />
                ) : (
                  <table className="w-full text-sm" data-testid="equipment-certifications-table">
                    <thead className="text-left text-xs text-muted-foreground border-b">
                      <tr><th className="py-2 pr-3">Employee</th><th className="py-2 pr-3">Status</th><th className="py-2 pr-3">Expires</th></tr>
                    </thead>
                    <tbody>
                      {data.certifications.map((c) => (
                        <tr key={c.id} className="border-b last:border-0">
                          <td className="py-2 pr-3">{employeesById[c.employee_id]?.name || c.employee_id}</td>
                          <td className="py-2 pr-3"><StatusPill kind="certification" value={c.status} /></td>
                          <td className="py-2 pr-3 text-muted-foreground">{c.expiration_date ? formatDate(c.expiration_date) : "Never"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <aside className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">At a glance</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div>Actively certified: <span className="font-semibold" data-testid="equipment-active-cert-count">{data.active_certification_count}</span></div>
              <div>Expiring soon: <span className="font-semibold" data-testid="equipment-expiring-cert-count">{data.expiring_certification_count}</span></div>
              <div>Pending Training: <span className="font-semibold">{data.pending_training?.length || 0}</span></div>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
