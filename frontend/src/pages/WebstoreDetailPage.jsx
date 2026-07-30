import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, FileUp, PackagePlus, Palette, Send, ShieldCheck, UserPlus } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import WebstoreBrandingEditor from "@/components/webstores/WebstoreBranding";
import { centsToDollarsString } from "@/lib/format";
import { extractError } from "@/lib/api";
import {
  createProductFromTemplate,
  createWebstoreAssignment,
  getWebstoreQuestionnaire,
  getWebstoreQuestionnaireResponse,
  generateLaunchPacket,
  getLaunchReadiness,
  getWebstoreSetupProgress,
  getWebstore,
  getWebstoreReports,
  listWebstoreAssignments,
  listWebstoreSetupFiles,
  listProductTemplates,
  applyWebstoreAnswers,
  previewWebstoreAnswerApplication,
  resendWebstoreInvitation,
  revokeWebstoreAssignment,
  reverseWebstoreAnswerApplication,
  sendLaunchPacket,
  setWebstoreStatus,
  uploadWebstoreSetupFile,
  updateWebstore,
} from "@/lib/webstores";
import { toast } from "sonner";

export default function WebstoreDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [templateId, setTemplateId] = useState("");
  const [promo, setPromo] = useState("");
  const [assignment, setAssignment] = useState({ role: "manager", email: "", name: "" });
  const [fileCategory, setFileCategory] = useState("logo");
  const [setupFile, setSetupFile] = useState(null);
  const [answerPreview, setAnswerPreview] = useState(null);
  const [selectedAnswerKeys, setSelectedAnswerKeys] = useState([]);
  const [proposedValues, setProposedValues] = useState({});
  const [lastApplication, setLastApplication] = useState(null);
  const detail = useQuery({ queryKey: ["webstore", id], queryFn: () => getWebstore(id), enabled: !!id });
  const templates = useQuery({ queryKey: ["webstore-product-templates"], queryFn: listProductTemplates });
  const readiness = useQuery({ queryKey: ["webstore-readiness", id], queryFn: () => getLaunchReadiness(id), enabled: !!id });
  const reports = useQuery({ queryKey: ["webstore-reports", id], queryFn: () => getWebstoreReports(id), enabled: !!id });
  const setupProgress = useQuery({ queryKey: ["webstore-setup-progress", id], queryFn: () => getWebstoreSetupProgress(id), enabled: !!id });
  const assignments = useQuery({ queryKey: ["webstore-assignments", id], queryFn: () => listWebstoreAssignments(id), enabled: !!id });
  const questionnaire = useQuery({ queryKey: ["webstore-questionnaire", id], queryFn: () => getWebstoreQuestionnaire(id), enabled: !!id });
  const questionnaireResponse = useQuery({ queryKey: ["webstore-questionnaire-response", id], queryFn: () => getWebstoreQuestionnaireResponse(id), enabled: !!id });
  const setupFiles = useQuery({ queryKey: ["webstore-setup-files", id], queryFn: () => listWebstoreSetupFiles(id), enabled: !!id });
  const store = detail.data?.webstore;
  const activePacket = useMemo(() => (detail.data?.launch_packets || [])[0], [detail.data]);
  const refresh = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["webstore", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-readiness", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-reports", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-setup-progress", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-assignments", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-questionnaire-response", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-setup-files", id] }),
    ]);
  };
  const addAssignment = useMutation({
    mutationFn: () => createWebstoreAssignment(id, assignment),
    onSuccess: async (data) => {
      toast.success(data?.invitation?.status === "sent" ? "Invitation sent" : "Invitation link generated");
      setAssignment({ role: "manager", email: "", name: "" });
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });
  const uploadSetupFileMutation = useMutation({
    mutationFn: () => {
      const formData = new FormData();
      formData.append("category", fileCategory);
      formData.append("file", setupFile);
      return uploadWebstoreSetupFile(id, formData);
    },
    onSuccess: async () => { toast.success("Setup file uploaded"); setSetupFile(null); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const resendInvitation = useMutation({
    mutationFn: (assignmentId) => resendWebstoreInvitation(id, assignmentId),
    onSuccess: async () => { toast.success("Invitation regenerated"); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const revokeAssignment = useMutation({
    mutationFn: (assignmentId) => revokeWebstoreAssignment(id, assignmentId, "Revoked during setup review"),
    onSuccess: async () => { toast.success("Assignment revoked"); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const previewAnswers = useMutation({
    mutationFn: () => previewWebstoreAnswerApplication(id, {
      submission_id: questionnaireResponse.data?.submission?.id,
      selected_answer_keys: selectedAnswerKeys,
      proposed_values: proposedValues,
    }),
    onSuccess: (data) => setAnswerPreview(data),
    onError: (err) => toast.error(extractError(err)),
  });
  const applyAnswers = useMutation({
    mutationFn: () => applyWebstoreAnswers(id, {
      submission_id: questionnaireResponse.data?.submission?.id,
      selected_answer_keys: selectedAnswerKeys,
      proposed_values: proposedValues,
      reason: "Apply verified Webstore intake answers",
      idempotency_key: `apply-${questionnaireResponse.data?.submission?.id}-${[...selectedAnswerKeys].sort().join("-")}`,
    }),
    onSuccess: async (data) => { toast.success("Answers applied"); setLastApplication(data?.application || null); setAnswerPreview(null); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const reverseAnswers = useMutation({
    mutationFn: () => reverseWebstoreAnswerApplication(id, lastApplication.id, {
      reason: "Reverse setup answer application",
      idempotency_key: `reverse-${lastApplication.id}`,
    }),
    onSuccess: async () => { toast.success("Answer application reversed"); setLastApplication(null); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const addProduct = useMutation({
    mutationFn: () => createProductFromTemplate(id, { source_template_id: templateId, status: "active", public: true }),
    onSuccess: async () => { toast.success("Product added"); setTemplateId(""); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const saveGate = useMutation({
    mutationFn: (payload) => updateWebstore(id, payload),
    onSuccess: async () => { toast.success("Readiness updated"); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const packet = useMutation({
    mutationFn: () => generateLaunchPacket(id, { promotion_copy: promo }),
    onSuccess: async () => { toast.success("Launch packet generated"); setPromo(""); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const sendPacket = useMutation({
    mutationFn: () => sendLaunchPacket(id, activePacket.id),
    onSuccess: async () => { toast.success("Launch packet sent"); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const launch = useMutation({
    mutationFn: () => setWebstoreStatus(id, "live"),
    onSuccess: async () => { toast.success("Webstore launched"); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });

  if (detail.isLoading) return <div className="p-6 text-sm text-muted-foreground">Loading...</div>;
  if (!store) return <div className="p-6 text-sm text-rose-700">Webstore not found.</div>;

  return (
    <div className="space-y-4" data-testid="webstore-detail-page">
      <PageHeader
        title={store.name}
        subtitle={`/${store.slug} · ${String(store.status).replace(/_/g, " ")}`}
        actions={(
          <div className="flex items-center gap-2 flex-wrap">
            <Button asChild variant="outline" size="sm"><Link to={store.public_url || `/p/webstores/${store.public_slug || store.slug}`}><ExternalLink className="size-4 mr-2" />Public</Link></Button>
          </div>
        )}
      />

      <Tabs defaultValue="overview" className="space-y-4" data-testid="webstore-detail-tabs">
        <TabsList className="flex h-auto flex-wrap justify-start">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="setup">Store Setup</TabsTrigger>
          <TabsTrigger value="branding"><Palette className="size-4 mr-1" />Branding</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="approval">Approval</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Setup Progress</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Badge variant="outline" data-testid="webstore-setup-state">{setupProgress.data?.setup_state || store.setup_state || "not_started"}</Badge>
            {(setupProgress.data?.steps || []).map((step) => (
              <div key={step.key} className="flex items-center justify-between gap-3">
                <span>{step.label}</span>
                <Badge variant={step.status === "complete" ? "secondary" : "outline"}>{step.status}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Owners and Managers</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="grid grid-cols-1 md:grid-cols-[120px_1fr_1fr_auto] gap-2">
              <Select value={assignment.role} onValueChange={(role) => setAssignment({ ...assignment, role })}>
                <SelectTrigger data-testid="webstore-assignment-role"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="owner">Owner</SelectItem><SelectItem value="manager">Manager</SelectItem></SelectContent>
              </Select>
              <Input value={assignment.name} onChange={(e) => setAssignment({ ...assignment, name: e.target.value })} placeholder="Name" data-testid="webstore-assignment-name" />
              <Input type="email" value={assignment.email} onChange={(e) => setAssignment({ ...assignment, email: e.target.value })} placeholder="Email" data-testid="webstore-assignment-email" />
              <Button disabled={!assignment.email || addAssignment.isPending} onClick={() => addAssignment.mutate()} data-testid="webstore-assignment-add"><UserPlus className="size-4" /></Button>
            </div>
            <div className="rounded border divide-y">
              {(assignments.data || []).map((a) => (
                <div key={a.id} className="p-2 flex items-center justify-between gap-2">
                  <div>
                    <div>{a.email}</div>
                    <div className="text-xs text-muted-foreground">{a.role} - {a.status}{a.is_primary_owner ? " - primary" : ""}</div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" disabled={a.status === "active" || resendInvitation.isPending} onClick={() => resendInvitation.mutate(a.id)} data-testid={`webstore-assignment-resend-${a.id}`}>Resend</Button>
                    <Button size="sm" variant="outline" disabled={a.is_primary_owner || revokeAssignment.isPending || a.status === "revoked"} onClick={() => revokeAssignment.mutate(a.id)} data-testid={`webstore-assignment-revoke-${a.id}`}>Revoke</Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Setup Files</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
              <Input value={fileCategory} onChange={(e) => setFileCategory(e.target.value)} data-testid="webstore-file-category" />
              <Input type="file" onChange={(e) => setSetupFile(e.target.files?.[0] || null)} data-testid="webstore-setup-file" />
              <Button disabled={!setupFile || uploadSetupFileMutation.isPending} onClick={() => uploadSetupFileMutation.mutate()} data-testid="webstore-upload-file"><FileUp className="size-4" /></Button>
            </div>
            <div className="rounded border divide-y">
              {(setupFiles.data || []).map((f) => (
                <div key={f.id} className="p-2 flex items-center justify-between gap-2">
                  <span>{f.file_name}</span>
                  <span className="text-xs text-muted-foreground">{f.category} - v{f.version} - {f.private_download_only ? "download only" : "preview safe"}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Questionnaire Review</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="text-muted-foreground">{(questionnaire.data?.templates || []).length} active template section groups bound to this Webstore.</div>
          {questionnaireResponse.data?.submission ? (
            <>
              {Object.keys(questionnaireResponse.data.submission.submitted_snapshot?.answers || questionnaireResponse.data.submission.answers || {}).length > 0 && (
                <div className="rounded border p-3 space-y-2" data-testid="webstore-answer-selection">
                  <div className="font-medium">Select answers to apply</div>
                  {Object.entries(questionnaireResponse.data.submission.submitted_snapshot?.answers || questionnaireResponse.data.submission.answers || {}).map(([key, value]) => (
                    <label key={key} className="grid gap-1.5 md:grid-cols-[180px_1fr] items-center text-sm">
                      <span className="flex items-center gap-2">
                        <Checkbox
                          checked={selectedAnswerKeys.includes(key)}
                          onCheckedChange={(checked) => {
                            setSelectedAnswerKeys(checked ? [...selectedAnswerKeys, key] : selectedAnswerKeys.filter((item) => item !== key));
                            setProposedValues({ ...proposedValues, [key]: proposedValues[key] ?? value });
                          }}
                          data-testid={`webstore-select-answer-${key}`}
                        />
                        {key.replace(/_/g, " ")}
                      </span>
                      <Input
                        value={proposedValues[key] ?? value ?? ""}
                        onChange={(e) => setProposedValues({ ...proposedValues, [key]: e.target.value })}
                        disabled={!selectedAnswerKeys.includes(key)}
                        data-testid={`webstore-proposed-answer-${key}`}
                      />
                    </label>
                  ))}
                </div>
              )}
              <div className="rounded border bg-slate-50 p-3">
                <div className="font-medium">Latest response: {questionnaireResponse.data.submission.status}</div>
                <pre className="mt-2 max-h-40 overflow-auto text-xs">{JSON.stringify(questionnaireResponse.data.submission.submitted_snapshot?.answers || questionnaireResponse.data.submission.answers || {}, null, 2)}</pre>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => previewAnswers.mutate()} disabled={previewAnswers.isPending || selectedAnswerKeys.length === 0}>Preview apply</Button>
                <Button onClick={() => applyAnswers.mutate()} disabled={!questionnaireResponse.data?.submission?.id || applyAnswers.isPending || selectedAnswerKeys.length === 0}>Apply safe answers</Button>
                <Button variant="outline" onClick={() => reverseAnswers.mutate()} disabled={!lastApplication || reverseAnswers.isPending}>Reverse last apply</Button>
              </div>
              {answerPreview && (
                <div className="rounded border p-3" data-testid="webstore-answer-preview">
                  <div className="font-medium">Safe changes</div>
                  {(answerPreview.proposed_changes || []).map((change) => <div key={`${change.answer_key}-${change.target}`}>{change.label}: {String(change.from || "")} to {String(change.to || "")}</div>)}
                  {(answerPreview.rejected_changes || []).length > 0 && <div className="mt-2 text-amber-700">Rejected: {answerPreview.rejected_changes.map((c) => c.answer_key).join(", ")}</div>}
                </div>
              )}
            </>
          ) : (
            <div className="text-muted-foreground">No submitted owner questionnaire yet.</div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Launch Gates</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            {Object.entries(readiness.data?.checks || {}).map(([key, ok]) => (
              <div className="flex items-center justify-between gap-3" key={key}>
                <span className="capitalize text-muted-foreground">{key.replace(/_/g, " ")}</span>
                <Badge variant={ok ? "secondary" : "outline"}>{ok ? "Ready" : "Missing"}</Badge>
              </div>
            ))}
            <div className="flex items-center gap-2 pt-2">
              <Checkbox checked={!!store.terms_fee_acknowledged} onCheckedChange={(checked) => saveGate.mutate({ terms_fee_acknowledged: !!checked })} id="fee-ack" />
              <Label htmlFor="fee-ack">Terms and fees acknowledged</Label>
            </div>
            <div className="rounded border bg-amber-50 px-3 py-2 text-xs text-amber-800" data-testid="webstore-payment-readiness">
              <div className="font-medium">Payment readiness: {readiness.data?.checks?.payment_ready ? "Ready" : "Not connected"}</div>
              <div>{readiness.data?.payment_unavailable_reason || "Real verified provider checkout is not connected yet."}</div>
            </div>
            <Button className="w-full" disabled={!readiness.data?.ready || launch.isPending} onClick={() => launch.mutate()} data-testid="webstore-launch">
              <ShieldCheck className="size-4 mr-2" />Launch
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Products</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Select value={templateId} onValueChange={setTemplateId}>
                <SelectTrigger data-testid="webstore-template-select"><SelectValue placeholder="Choose template" /></SelectTrigger>
                <SelectContent>{(templates.data || []).map((t) => <SelectItem value={t.id} key={t.id}>{t.template_name}</SelectItem>)}</SelectContent>
              </Select>
              <Button disabled={!templateId || addProduct.isPending} onClick={() => addProduct.mutate()}><PackagePlus className="size-4" /></Button>
            </div>
            <div className="rounded border divide-y">
              {(detail.data?.products || []).map((p) => (
                <div key={p.id} className="p-3 text-sm flex items-center justify-between gap-3">
                  <div><div className="font-medium">{p.name}</div><div className="text-xs text-muted-foreground">{p.status} · {p.public ? "public" : "private"}</div></div>
                  <span className="font-medium">{centsToDollarsString(p.selling_price_cents)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Launch Packet</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-1.5"><Label>Promotion copy</Label><Input value={promo} onChange={(e) => setPromo(e.target.value)} data-testid="webstore-promo" /></div>
            <div className="flex gap-2">
              <Button variant="outline" disabled={packet.isPending} onClick={() => packet.mutate()}><CheckCircle2 className="size-4 mr-2" />Generate</Button>
              <Button disabled={!activePacket || sendPacket.isPending} onClick={() => sendPacket.mutate()}><Send className="size-4 mr-2" />Send</Button>
            </div>
            {activePacket && <Alert><AlertTitle className="capitalize">{activePacket.status.replace(/_/g, " ")}</AlertTitle><AlertDescription>{activePacket.promotion_copy || "Packet snapshot is ready."}</AlertDescription></Alert>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Reporting</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div><div className="text-muted-foreground">Orders</div><div className="text-lg font-semibold">{reports.data?.order_count || 0}</div></div>
          <div><div className="text-muted-foreground">Gross sales</div><div className="text-lg font-semibold">{centsToDollarsString(reports.data?.gross_sales_cents)}</div></div>
          <div><div className="text-muted-foreground">Platform fee</div><div className="text-lg font-semibold">{centsToDollarsString(reports.data?.ledger_totals_cents?.platform_usage_fee)}</div></div>
          <div><div className="text-muted-foreground">Owner share</div><div className="text-lg font-semibold">{centsToDollarsString(reports.data?.ledger_totals_cents?.store_owner_share)}</div></div>
        </CardContent>
      </Card>
        </TabsContent>

        <TabsContent value="setup" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Store Setup</CardTitle></CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Setup intake, assignments, files, and launch gates remain on the Overview tab while Stage 3 adds Branding.
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="branding" className="space-y-4">
          <WebstoreBrandingEditor webstoreId={id} products={detail.data?.products || []} />
        </TabsContent>

        <TabsContent value="preview" className="space-y-4">
          <WebstoreBrandingEditor webstoreId={id} products={detail.data?.products || []} />
        </TabsContent>

        <TabsContent value="approval" className="space-y-4">
          <WebstoreBrandingEditor webstoreId={id} products={detail.data?.products || []} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
