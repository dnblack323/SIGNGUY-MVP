import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock3, FileSpreadsheet, HelpCircle, RotateCcw, Save, SkipForward } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import ContextualHelp from "@/components/help/ContextualHelp";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import {
  applyCompanyProfile,
  applyPricingScenario,
  createHistoricalInvoiceImport,
  createTemplateExercise,
  getOnboardingDashboard,
  getPlaceholderRegistry,
  getSetupPackageHandoff,
  previewPlaceholders,
  recordTestPortal,
  submitPricingScenario,
  updateOnboardingTask,
  updateSetupPackageHandoff,
} from "@/lib/onboarding";
import { toast } from "sonner";

const statusTone = {
  completed: "secondary",
  skipped: "outline",
  deferred: "outline",
  blocked: "destructive",
  in_progress: "outline",
};

function StatusBadge({ status }) {
  return <Badge variant={statusTone[status] || "outline"}>{String(status || "not_started").replace(/_/g, " ")}</Badge>;
}

function useSetupMutation(fn, message) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: async () => {
      toast.success(message);
      await qc.invalidateQueries({ queryKey: ["onboarding-dashboard"] });
      await qc.invalidateQueries({ queryKey: ["setup-package-handoff"] });
    },
    onError: (err) => toast.error(extractError(err)),
  });
}

export default function OnboardingPage() {
  const { hasPerm, user } = useAuth();
  const qc = useQueryClient();
  const canWrite = hasPerm("onboarding:write") && ["owner", "admin"].includes(user?.role);
  const dashboard = useQuery({ queryKey: ["onboarding-dashboard"], queryFn: getOnboardingDashboard, enabled: hasPerm("onboarding:read") });
  const placeholders = useQuery({ queryKey: ["placeholder-registry"], queryFn: getPlaceholderRegistry, enabled: hasPerm("onboarding:read") });
  const handoff = useQuery({ queryKey: ["setup-package-handoff"], queryFn: getSetupPackageHandoff, enabled: hasPerm("onboarding:read") });

  const [company, setCompany] = useState({ shop_name: "", email: "", phone: "", website: "" });
  const [pricing, setPricing] = useState({ category: "banners", job_duration_hours: "2", crew_size: "1", material_cost_estimate: "45", customer_charge: "250", price_floor: "125", difficulty: "typical" });
  const [pricingSubmission, setPricingSubmission] = useState(null);
  const [importFile, setImportFile] = useState({ file_name: "", file_type: "csv", file_size_bytes: "" });
  const [placeholderText, setPlaceholderText] = useState("Hi {{customer_name}}, your order {{order_number}} is ready.");
  const [placeholderContext, setPlaceholderContext] = useState({ customer_name: "Acme Signs", order_number: "1001" });
  const [placeholderPreview, setPlaceholderPreview] = useState(null);

  const companyMutation = useSetupMutation(() => applyCompanyProfile({ company_profile: company }), "Company profile applied");
  const statusMutation = useSetupMutation(({ taskKey, status }) => updateOnboardingTask(taskKey, { status, reason: "Updated from onboarding dashboard" }), "Task updated");
  const pricingMutation = useMutation({
    mutationFn: () => submitPricingScenario({
      ...pricing,
      job_duration_hours: Number(pricing.job_duration_hours),
      crew_size: Number(pricing.crew_size),
      material_cost_estimate: Number(pricing.material_cost_estimate || 0),
      customer_charge: Number(pricing.customer_charge),
      price_floor: Number(pricing.price_floor),
    }),
    onSuccess: (data) => { setPricingSubmission(data); toast.success("Pricing scenario created"); },
    onError: (err) => toast.error(extractError(err)),
  });
  const pricingApplyMutation = useSetupMutation(
    () => applyPricingScenario(pricingSubmission.id, pricingSubmission.derived_suggestions?.suggested_shop_defaults_map || {}),
    "Pricing defaults applied",
  );
  const importMutation = useSetupMutation(() => createHistoricalInvoiceImport({
    ...importFile,
    file_size_bytes: importFile.file_size_bytes ? Number(importFile.file_size_bytes) : undefined,
    request_analysis: true,
  }), "Historical import recorded");
  const placeholderMutation = useMutation({
    mutationFn: () => previewPlaceholders({ content: placeholderText, context: placeholderContext }),
    onSuccess: setPlaceholderPreview,
    onError: (err) => toast.error(extractError(err)),
  });
  const templateMutation = useSetupMutation(() => createTemplateExercise({
    name: "Onboarding email sample",
    template_type: "email",
    body: { channels: { email_body: placeholderText } },
    context: placeholderContext,
    save_as_template: true,
  }), "Template exercise saved");
  const handoffMutation = useSetupMutation(() => updateSetupPackageHandoff({ status: "ready_for_intake", notes: "Reviewed from onboarding." }), "Setup handoff updated");
  const testPortalMutation = useSetupMutation(() => recordTestPortal({ checked_at: new Date().toISOString(), result: "manual_check_recorded" }), "Test portal check recorded");

  const tasks = useMemo(() => dashboard.data?.tasks || [], [dashboard.data?.tasks]);
  const grouped = useMemo(() => {
    const out = {};
    for (const task of tasks) {
      out[task.family] = out[task.family] || [];
      out[task.family].push(task);
    }
    return out;
  }, [tasks]);

  if (!hasPerm("onboarding:read")) {
    return (
      <div className="space-y-4" data-testid="onboarding-page">
        <PageHeader title="Onboarding" subtitle="Guided setup is available to internal shop users." />
        <Alert><HelpCircle className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account cannot read onboarding.</AlertDescription></Alert>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="onboarding-page">
      <PageHeader
        title="Onboarding"
        subtitle="Guided setup for shop launch readiness."
        actions={<><ContextualHelp surfaceKey="onboarding.dashboard" module="onboarding" /><Button variant="outline" size="sm" onClick={() => dashboard.refetch()}><RotateCcw className="size-4 mr-2" />Refresh</Button></>}
      />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Launch Checklist</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <Progress value={dashboard.data?.progress?.percent_complete || 0} data-testid="onboarding-progress" />
            <div className="text-sm text-muted-foreground" data-testid="onboarding-progress-text">
              {dashboard.data?.progress?.completed_tasks || 0} of {dashboard.data?.progress?.total_tasks || 0} complete
            </div>
            <div className="grid gap-4">
              {Object.entries(grouped).map(([family, rows]) => (
                <div key={family} className="space-y-2">
                  <div className="text-xs uppercase text-muted-foreground">{family}</div>
                  <div className="grid gap-2">
                    {rows.map((task) => (
                      <div key={task.task_key} className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between" data-testid={`onboarding-task-${task.task_key}`}>
                        <div className="min-w-0">
                          <div className="font-medium text-sm">{task.title}</div>
                          <div className="text-xs text-muted-foreground">{task.level} {task.dependencies?.length ? `· after ${task.dependencies.join(", ")}` : ""}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <StatusBadge status={task.status} />
                          <Button size="icon" variant="outline" disabled={!canWrite || task.status === "completed"} onClick={() => statusMutation.mutate({ taskKey: task.task_key, status: "completed" })} aria-label={`Complete ${task.title}`}>
                            <CheckCircle2 className="size-4" />
                          </Button>
                          <Button size="icon" variant="ghost" disabled={!canWrite || task.status === "skipped"} onClick={() => statusMutation.mutate({ taskKey: task.task_key, status: "skipped" })} aria-label={`Skip ${task.title}`}>
                            <SkipForward className="size-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Next Step</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="font-medium">{dashboard.data?.recommended_next_task?.title || "All current steps complete"}</div>
              <div className="text-muted-foreground">{dashboard.data?.recommended_next_task?.level || "complete"}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Setup Package</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-center justify-between"><span>Status</span><StatusBadge status={handoff.data?.handoff_status} /></div>
              <div className="text-muted-foreground">{handoff.data?.message || handoff.data?.purchase?.package_key || "No handoff loaded"}</div>
              <Button size="sm" variant="outline" disabled={!canWrite || !handoff.data?.available || handoffMutation.isPending} onClick={() => handoffMutation.mutate()}>
                <Clock3 className="size-4 mr-2" />Mark ready
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <Tabs defaultValue="company" className="space-y-4">
        <TabsList>
          <TabsTrigger value="company">Company</TabsTrigger>
          <TabsTrigger value="pricing">Pricing</TabsTrigger>
          <TabsTrigger value="imports">Imports</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
          <TabsTrigger value="portal">Portal</TabsTrigger>
        </TabsList>

        <TabsContent value="company">
          <Card><CardHeader><CardTitle className="text-base">Company Profile</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">
            {Object.keys(company).map((key) => <div className="grid gap-1" key={key}><Label>{key.replace(/_/g, " ")}</Label><Input value={company[key]} onChange={(e) => setCompany({ ...company, [key]: e.target.value })} /></div>)}
            <Button className="md:col-span-2 w-fit" disabled={!canWrite || companyMutation.isPending} onClick={() => companyMutation.mutate()}><Save className="size-4 mr-2" />Apply</Button>
          </CardContent></Card>
        </TabsContent>

        <TabsContent value="pricing">
          <Card><CardHeader><CardTitle className="text-base">Pricing Scenario <ContextualHelp surfaceKey="pricing.quiz" module="pricing" /></CardTitle></CardHeader><CardContent className="space-y-3">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="grid gap-1"><Label>Category</Label><Select value={pricing.category} onValueChange={(v) => setPricing({ ...pricing, category: v })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["banners", "rigid_signs", "cut_vinyl", "digital_print", "vehicle_graphics", "apparel", "services", "promotional", "custom"].map((v) => <SelectItem key={v} value={v}>{v.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select></div>
              {["job_duration_hours", "crew_size", "material_cost_estimate", "customer_charge", "price_floor"].map((key) => <div className="grid gap-1" key={key}><Label>{key.replace(/_/g, " ")}</Label><Input value={pricing[key]} onChange={(e) => setPricing({ ...pricing, [key]: e.target.value })} /></div>)}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button disabled={!canWrite || pricingMutation.isPending} onClick={() => pricingMutation.mutate()}>Create scenario</Button>
              <Button variant="outline" disabled={!canWrite || !pricingSubmission || pricingApplyMutation.isPending} onClick={() => pricingApplyMutation.mutate()}>Apply suggested defaults</Button>
            </div>
            {pricingSubmission && <pre className="max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(pricingSubmission.derived_suggestions, null, 2)}</pre>}
          </CardContent></Card>
        </TabsContent>

        <TabsContent value="imports">
          <Card><CardHeader><CardTitle className="text-base">Historical Invoice Import</CardTitle></CardHeader><CardContent className="grid gap-3 md:grid-cols-3">
            <div className="grid gap-1"><Label>File name</Label><Input value={importFile.file_name} onChange={(e) => setImportFile({ ...importFile, file_name: e.target.value })} /></div>
            <div className="grid gap-1"><Label>Type</Label><Input value={importFile.file_type} onChange={(e) => setImportFile({ ...importFile, file_type: e.target.value })} /></div>
            <div className="grid gap-1"><Label>Size bytes</Label><Input value={importFile.file_size_bytes} onChange={(e) => setImportFile({ ...importFile, file_size_bytes: e.target.value })} /></div>
            <Button className="w-fit" disabled={!canWrite || !importFile.file_name || importMutation.isPending} onClick={() => importMutation.mutate()}><FileSpreadsheet className="size-4 mr-2" />Record import</Button>
          </CardContent></Card>
        </TabsContent>

        <TabsContent value="templates">
          <Card><CardHeader><CardTitle className="text-base">Placeholder Exercise <ContextualHelp surfaceKey="templates.editor" module="templates" /></CardTitle></CardHeader><CardContent className="space-y-3">
            <Textarea rows={4} value={placeholderText} onChange={(e) => setPlaceholderText(e.target.value)} />
            <div className="grid gap-3 md:grid-cols-2">
              <Input value={placeholderContext.customer_name} onChange={(e) => setPlaceholderContext({ ...placeholderContext, customer_name: e.target.value })} />
              <Input value={placeholderContext.order_number} onChange={(e) => setPlaceholderContext({ ...placeholderContext, order_number: e.target.value })} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => placeholderMutation.mutate()}>Preview</Button>
              <Button disabled={!canWrite || templateMutation.isPending} onClick={() => templateMutation.mutate()}>Save template</Button>
            </div>
            <div className="text-xs text-muted-foreground">{(placeholders.data?.placeholders || []).slice(0, 8).map((p) => p.token).join(" ")}</div>
            {placeholderPreview && <pre className="rounded-md bg-muted p-3 text-xs">{JSON.stringify(placeholderPreview, null, 2)}</pre>}
          </CardContent></Card>
        </TabsContent>

        <TabsContent value="portal">
          <Card><CardHeader><CardTitle className="text-base">Test Portal</CardTitle></CardHeader><CardContent>
            <Button disabled={!canWrite || testPortalMutation.isPending} onClick={() => testPortalMutation.mutate()}>Record manual check</Button>
          </CardContent></Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
