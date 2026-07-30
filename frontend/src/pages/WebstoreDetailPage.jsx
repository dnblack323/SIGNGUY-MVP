import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, CheckCircle2, ExternalLink, FileUp, PackagePlus, Palette, RotateCcw, Save, Send, ShieldCheck, UserPlus } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import WebstoreBrandingEditor from "@/components/webstores/WebstoreBranding";
import { centsToDollarsString } from "@/lib/format";
import { extractError } from "@/lib/api";
import {
  createProductFromTemplate,
  createProductTemplate,
  createWebstoreProductCategory,
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
  listWebstoreArtwork,
  listWebstoreMockups,
  listWebstoreProductCategories,
  applyWebstoreAnswers,
  previewWebstoreAnswerApplication,
  resendWebstoreInvitation,
  revokeWebstoreAssignment,
  reverseWebstoreAnswerApplication,
  sendLaunchPacket,
  setWebstoreStatus,
  uploadWebstoreSetupFile,
  updateProductTemplate,
  updateWebstoreProduct,
  updateWebstoreProductCategory,
  archiveProductTemplate,
  archiveWebstoreProduct,
  archiveWebstoreProductCategory,
  restoreProductTemplate,
  restoreWebstoreProduct,
  restoreWebstoreProductCategory,
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
  const [productFilters, setProductFilters] = useState({ status: "all", category_id: "all", q: "" });
  const [selectedProductId, setSelectedProductId] = useState("");
  const [productDraft, setProductDraft] = useState({});
  const [productError, setProductError] = useState("");
  const emptyTemplateDraft = {
    template_name: "",
    product_category: "",
    product_type: "",
    default_title: "",
    default_short_description: "",
    default_description: "",
    production_method: "",
    supplier_source_info: "",
    default_production_notes: "",
    default_customer_images: {},
    default_artwork_associations: [],
    default_mockup_associations: [],
  };
  const [templateDraft, setTemplateDraft] = useState(emptyTemplateDraft);
  const [templateEditDraft, setTemplateEditDraft] = useState({});
  const [editingTemplateId, setEditingTemplateId] = useState("");
  const [categoryDraft, setCategoryDraft] = useState({ name: "", description: "" });
  const [categoryEditDraft, setCategoryEditDraft] = useState({});
  const [editingCategoryId, setEditingCategoryId] = useState("");
  const detail = useQuery({ queryKey: ["webstore", id], queryFn: () => getWebstore(id), enabled: !!id });
  const templates = useQuery({ queryKey: ["webstore-product-templates"], queryFn: listProductTemplates });
  const categories = useQuery({ queryKey: ["webstore-product-categories", id], queryFn: () => listWebstoreProductCategories(id), enabled: !!id });
  const readiness = useQuery({ queryKey: ["webstore-readiness", id], queryFn: () => getLaunchReadiness(id), enabled: !!id });
  const reports = useQuery({ queryKey: ["webstore-reports", id], queryFn: () => getWebstoreReports(id), enabled: !!id });
  const setupProgress = useQuery({ queryKey: ["webstore-setup-progress", id], queryFn: () => getWebstoreSetupProgress(id), enabled: !!id });
  const assignments = useQuery({ queryKey: ["webstore-assignments", id], queryFn: () => listWebstoreAssignments(id), enabled: !!id });
  const questionnaire = useQuery({ queryKey: ["webstore-questionnaire", id], queryFn: () => getWebstoreQuestionnaire(id), enabled: !!id });
  const questionnaireResponse = useQuery({ queryKey: ["webstore-questionnaire-response", id], queryFn: () => getWebstoreQuestionnaireResponse(id), enabled: !!id });
  const setupFiles = useQuery({ queryKey: ["webstore-setup-files", id], queryFn: () => listWebstoreSetupFiles(id), enabled: !!id });
  const artworkOptions = useQuery({ queryKey: ["webstore-artwork", id, selectedProductId], queryFn: () => listWebstoreArtwork(id, selectedProductId ? { product_id: selectedProductId } : {}), enabled: !!id });
  const mockupOptions = useQuery({ queryKey: ["webstore-mockups", id, selectedProductId], queryFn: () => listWebstoreMockups(id, selectedProductId ? { product_id: selectedProductId } : {}), enabled: !!id });
  const store = detail.data?.webstore;
  const setupFileItems = setupFiles.data?.items || setupFiles.data || [];
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
      qc.invalidateQueries({ queryKey: ["webstore-product-categories", id] }),
      qc.invalidateQueries({ queryKey: ["webstore-product-templates"] }),
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
  const filteredProducts = useMemo(() => {
    const q = productFilters.q.trim().toLowerCase();
    return (detail.data?.products || []).filter((product) => {
      if (productFilters.status !== "all" && product.status !== productFilters.status) return false;
      if (productFilters.category_id !== "all" && product.category_id !== productFilters.category_id) return false;
      if (q && !String(product.name || "").toLowerCase().includes(q)) return false;
      return true;
    });
  }, [detail.data, productFilters]);
  const selectedProduct = useMemo(
    () => (detail.data?.products || []).find((product) => product.id === selectedProductId),
    [detail.data, selectedProductId],
  );
  const createBlankProduct = useMutation({
    mutationFn: () => createProductFromTemplate(id, { name: "New draft product", product_type: "general" }),
    onSuccess: async (product) => { toast.success("Draft product created"); setSelectedProductId(product.id); setProductDraft(product); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const addProduct = useMutation({
    mutationFn: () => createProductFromTemplate(id, { source_template_id: templateId, idempotency_key: `template-${templateId}-${Date.now()}` }),
    onSuccess: async (product) => { toast.success("Template copied into a private draft"); setTemplateId(""); setSelectedProductId(product.id); setProductDraft(product); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const saveProduct = useMutation({
    mutationFn: () => updateWebstoreProduct(id, productDraft.id, {
      expected_revision: productDraft.revision,
      name: productDraft.name,
      short_description: productDraft.short_description,
      full_description: productDraft.full_description,
      product_type: productDraft.product_type,
      category_id: productDraft.category_id || undefined,
      category_name: productDraft.category_name || undefined,
      production_method: productDraft.production_method,
      production_notes: productDraft.production_notes,
      supplier_source_info: productDraft.supplier_source_info,
      fulfillment_notes: productDraft.fulfillment_notes,
      customer_images: productDraft.customer_images || {},
      artwork_associations: productDraft.artwork_associations || [],
      mockup_associations: productDraft.mockup_associations || [],
    }),
    onSuccess: async (product) => { toast.success("Product draft saved"); setProductError(""); setProductDraft(product); await refresh(); },
    onError: (err) => { const message = extractError(err); setProductError(message); toast.error(message); },
  });
  const archiveProduct = useMutation({
    mutationFn: (product) => archiveWebstoreProduct(id, product.id, { expected_revision: product.revision }),
    onSuccess: async (product) => { toast.success("Product archived"); setProductError(""); setProductDraft(product); await refresh(); },
    onError: (err) => { const message = extractError(err); setProductError(message); toast.error(message); },
  });
  const restoreProduct = useMutation({
    mutationFn: (product) => restoreWebstoreProduct(id, product.id, { expected_revision: product.revision }),
    onSuccess: async (product) => { toast.success("Product restored to draft"); setProductError(""); setProductDraft(product); await refresh(); },
    onError: (err) => { const message = extractError(err); setProductError(message); toast.error(message); },
  });
  const createCategory = useMutation({
    mutationFn: () => createWebstoreProductCategory(id, categoryDraft),
    onSuccess: async () => { toast.success("Category created"); setCategoryDraft({ name: "", description: "" }); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const saveCategory = useMutation({
    mutationFn: () => updateWebstoreProductCategory(id, editingCategoryId, { ...categoryEditDraft, expected_revision: categoryEditDraft.revision }),
    onSuccess: async () => {
      toast.success("Category updated");
      setEditingCategoryId("");
      setCategoryEditDraft({});
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });
  const archiveCategory = useMutation({
    mutationFn: (category) => archiveWebstoreProductCategory(id, category.id, { expected_revision: category.revision }),
    onSuccess: refresh,
    onError: (err) => toast.error(extractError(err)),
  });
  const restoreCategory = useMutation({
    mutationFn: (category) => restoreWebstoreProductCategory(id, category.id, { expected_revision: category.revision }),
    onSuccess: refresh,
    onError: (err) => toast.error(extractError(err)),
  });
  const templatePayload = (draft, includeRevision = false) => ({
    ...(includeRevision ? { expected_revision: draft.revision } : {}),
    webstore_id: id,
    template_name: draft.template_name,
    product_category: draft.product_category,
    product_type: draft.product_type,
    default_title: draft.default_title,
    default_short_description: draft.default_short_description,
    default_description: draft.default_description,
    suggested_category_name: draft.suggested_category_name,
    production_method: draft.production_method,
    supplier_source_info: draft.supplier_source_info,
    default_production_notes: draft.default_production_notes,
    default_customer_images: draft.default_customer_images || {},
    default_artwork_associations: draft.default_artwork_associations || [],
    default_mockup_associations: draft.default_mockup_associations || [],
    best_store_types: draft.best_store_types || [],
    mockup_supported: draft.mockup_supported ?? true,
    internal_notes: draft.internal_notes,
  });
  const createTemplate = useMutation({
    mutationFn: () => createProductTemplate({ ...templatePayload(templateDraft), scope: "tenant", status: "active" }),
    onSuccess: async () => { toast.success("Tenant template created"); setTemplateDraft(emptyTemplateDraft); await refresh(); },
    onError: (err) => toast.error(extractError(err)),
  });
  const saveTemplate = useMutation({
    mutationFn: () => updateProductTemplate(editingTemplateId, templatePayload(templateEditDraft, true)),
    onSuccess: async () => {
      toast.success("Tenant template updated");
      setEditingTemplateId("");
      setTemplateEditDraft({});
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });
  const archiveTemplate = useMutation({
    mutationFn: (template) => archiveProductTemplate(template.id, { expected_revision: template.revision }),
    onSuccess: refresh,
    onError: (err) => toast.error(extractError(err)),
  });
  const restoreTemplate = useMutation({
    mutationFn: (template) => restoreProductTemplate(template.id, { expected_revision: template.revision }),
    onSuccess: refresh,
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
  const setProductField = (field, value) => setProductDraft((draft) => ({ ...draft, [field]: value }));
  const setImageField = (slot, field, value) => setProductDraft((draft) => ({
    ...draft,
    customer_images: {
      ...(draft.customer_images || {}),
      [slot]: {
        ...((draft.customer_images || {})[slot] || {}),
        slot,
        role: slot,
        [field]: value,
      },
    },
  }));
  const setImageFile = (slot, fileId) => {
    if (fileId === "none") {
      removeImageSlot(slot);
      return;
    }
    const file = setupFileItems.find((item) => item.id === fileId);
    setProductDraft((draft) => ({
      ...draft,
      customer_images: {
        ...(draft.customer_images || {}),
        [slot]: {
          ...((draft.customer_images || {})[slot] || {}),
          slot,
          role: slot,
          file_id: fileId === "none" ? "" : fileId,
          file_name: file?.file_name,
          content_type: file?.detected_content_type || file?.content_type,
          url: file?.preview_url || file?.url || ((draft.customer_images || {})[slot] || {}).url,
        },
      },
    }));
  };
  const removeImageSlot = (slot) => setProductDraft((draft) => {
    const next = { ...(draft.customer_images || {}) };
    delete next[slot];
    return { ...draft, customer_images: next };
  });
  const addAssociation = (field, key, value) => {
    if (!value || value === "none") return;
    setProductDraft((draft) => {
      const current = draft[field] || [];
      if (current.some((item) => item[key] === value)) return draft;
      return { ...draft, [field]: [...current, { [key]: value }] };
    });
  };
  const removeAssociation = (field, key, value) => {
    setProductDraft((draft) => ({ ...draft, [field]: (draft[field] || []).filter((item) => item[key] !== value) }));
  };
  const addTemplateAssociation = (setter, key, value) => {
    if (!value || value === "none") return;
    const field = key === "artwork_id" ? "default_artwork_associations" : "default_mockup_associations";
    setter((draft) => {
      const current = draft[field] || [];
      if (current.some((item) => item[key] === value)) return draft;
      return { ...draft, [field]: [...current, { [key]: value }] };
    });
  };
  const removeTemplateAssociation = (setter, key, value) => {
    const field = key === "artwork_id" ? "default_artwork_associations" : "default_mockup_associations";
    setter((draft) => ({ ...draft, [field]: (draft[field] || []).filter((item) => item[key] !== value) }));
  };

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
          <TabsTrigger value="products">Products</TabsTrigger>
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

        <TabsContent value="products" className="space-y-4" data-testid="webstore-product-foundation">
          <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_1.4fr] gap-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Products</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <Alert>
                  <AlertTitle>Draft foundation</AlertTitle>
                  <AlertDescription>New products are private drafts. Approval, publication, variants, pricing rules, and checkout come in later stages.</AlertDescription>
                </Alert>
                <div className="grid gap-2 md:grid-cols-3">
                  <Input placeholder="Search products" value={productFilters.q} onChange={(e) => setProductFilters({ ...productFilters, q: e.target.value })} data-testid="webstore-product-search" />
                  <Select value={productFilters.status} onValueChange={(value) => setProductFilters({ ...productFilters, status: value })}>
                    <SelectTrigger data-testid="webstore-product-status-filter"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All statuses</SelectItem>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="active">Active legacy</SelectItem>
                      <SelectItem value="archived">Archived</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={productFilters.category_id} onValueChange={(value) => setProductFilters({ ...productFilters, category_id: value })}>
                    <SelectTrigger data-testid="webstore-product-category-filter"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All categories</SelectItem>
                      {(categories.data?.items || []).map((category) => <SelectItem key={category.id} value={category.id}>{category.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => createBlankProduct.mutate()} disabled={createBlankProduct.isPending} data-testid="webstore-create-blank-product"><PackagePlus className="size-4 mr-2" />Create Blank Product</Button>
                  <Select value={templateId} onValueChange={setTemplateId}>
                    <SelectTrigger className="w-64" data-testid="webstore-stage4-template-select"><SelectValue placeholder="Add from template" /></SelectTrigger>
                    <SelectContent>{(templates.data || []).filter((t) => t.status !== "archived").map((t) => <SelectItem value={t.id} key={t.id}>{t.template_name}{t.scope === "platform" ? " (starter)" : ""}</SelectItem>)}</SelectContent>
                  </Select>
                  <Button disabled={!templateId || addProduct.isPending} onClick={() => addProduct.mutate()} data-testid="webstore-add-template-draft">Add To Store</Button>
                </div>
                <div className="rounded border divide-y">
                  {filteredProducts.map((product) => (
                    <button key={product.id} type="button" className="w-full p-3 text-left text-sm flex items-center justify-between gap-3 hover:bg-slate-50" onClick={() => { setSelectedProductId(product.id); setProductDraft(product); setProductError(""); }} data-testid={`webstore-product-row-${product.id}`}>
                      <span><span className="font-medium">{product.name}</span><span className="block text-xs text-muted-foreground">{product.status} · {product.public ? "public legacy" : "private"} · {product.category_name || product.category || "No category"}</span></span>
                      <span className="font-medium">{centsToDollarsString(product.selling_price_cents)}</span>
                    </button>
                  ))}
                  {filteredProducts.length === 0 && <div className="p-3 text-sm text-muted-foreground">No products match these filters.</div>}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="text-base">Product Editor</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {!productDraft.id ? (
                  <div className="text-sm text-muted-foreground">Select a product or create a draft to edit product foundation fields.</div>
                ) : (
                  <>
                    {productError && (
                      <Alert variant="destructive">
                        <AlertTitle>Product was not saved</AlertTitle>
                        <AlertDescription>
                          {productError}
                          <Button type="button" size="sm" variant="outline" className="mt-2" onClick={refresh}>Reload latest product data</Button>
                        </AlertDescription>
                      </Alert>
                    )}
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="grid gap-1.5"><Label>Name</Label><Input value={productDraft.name || ""} onChange={(e) => setProductField("name", e.target.value)} data-testid="webstore-product-name" /></div>
                      <div className="grid gap-1.5"><Label>Product type</Label><Input value={productDraft.product_type || ""} onChange={(e) => setProductField("product_type", e.target.value)} /></div>
                      <div className="grid gap-1.5"><Label>Category</Label><Select value={productDraft.category_id || "none"} onValueChange={(value) => setProductDraft({ ...productDraft, category_id: value === "none" ? "" : value, category_name: (categories.data?.items || []).find((c) => c.id === value)?.name || "" })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="none">No category</SelectItem>{(categories.data?.items || []).filter((category) => category.status === "active").map((category) => <SelectItem key={category.id} value={category.id}>{category.name}</SelectItem>)}</SelectContent></Select></div>
                      <div className="grid gap-1.5"><Label>Production method</Label><Input value={productDraft.production_method || ""} onChange={(e) => setProductField("production_method", e.target.value)} /></div>
                    </div>
                    <div className="grid gap-1.5"><Label>Short description</Label><Textarea value={productDraft.short_description || ""} onChange={(e) => setProductField("short_description", e.target.value)} /></div>
                    <div className="grid gap-1.5"><Label>Full description</Label><Textarea value={productDraft.full_description || ""} onChange={(e) => setProductField("full_description", e.target.value)} /></div>
                    <div className="grid gap-3 md:grid-cols-2">
                      {["primary", "secondary"].map((slot) => (
                        <div key={slot} className="rounded border p-3 space-y-2" data-testid={`webstore-product-image-${slot}`}>
                          <div className="font-medium capitalize">{slot} image</div>
                          <Select value={productDraft.customer_images?.[slot]?.file_id || "none"} onValueChange={(value) => setImageFile(slot, value)}>
                            <SelectTrigger data-testid={`webstore-product-image-${slot}-file`}><SelectValue placeholder="Choose uploaded setup file" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">No image</SelectItem>
                              {setupFileItems.map((file) => (
                                <SelectItem key={file.id} value={file.id}>{file.file_name || file.id}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <Input placeholder="Alternate text" value={productDraft.customer_images?.[slot]?.alt_text || ""} onChange={(e) => setImageField(slot, "alt_text", e.target.value)} />
                          <p className="text-xs text-muted-foreground">{slot === "primary" ? "Recommended: 1600x1200 px or larger." : "Recommended: 1200x1200 px or larger."}</p>
                          {(productDraft.customer_images?.[slot]?.url || productDraft.images?.find((image) => image.slot === slot)?.url) && (
                            <img
                              className="aspect-video w-full rounded border object-cover"
                              src={productDraft.customer_images?.[slot]?.url || productDraft.images?.find((image) => image.slot === slot)?.url}
                              alt={productDraft.customer_images?.[slot]?.alt_text || productDraft.images?.find((image) => image.slot === slot)?.alt_text || ""}
                            />
                          )}
                          <Button type="button" size="sm" variant="outline" onClick={() => removeImageSlot(slot)}>Remove</Button>
                        </div>
                      ))}
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="grid gap-1.5"><Label>Internal production notes</Label><Textarea value={productDraft.production_notes || ""} onChange={(e) => setProductField("production_notes", e.target.value)} /></div>
                      <div className="grid gap-1.5"><Label>Private supplier/source information</Label><Textarea value={productDraft.supplier_source_info || ""} onChange={(e) => setProductField("supplier_source_info", e.target.value)} /></div>
                      <div className="grid gap-1.5 md:col-span-2"><Label>Private fulfillment notes</Label><Textarea value={productDraft.fulfillment_notes || ""} onChange={(e) => setProductField("fulfillment_notes", e.target.value)} /></div>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="grid gap-1.5">
                        <Label>Private artwork</Label>
                        <Select value="none" onValueChange={(value) => addAssociation("artwork_associations", "artwork_id", value)}>
                          <SelectTrigger data-testid="webstore-product-artwork-associations"><SelectValue placeholder="Associate artwork" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">Choose artwork</SelectItem>
                            {(artworkOptions.data || []).map((artwork) => <SelectItem key={artwork.id} value={artwork.id}>{artwork.file_name || artwork.purpose || artwork.id}</SelectItem>)}
                          </SelectContent>
                        </Select>
                        <div className="flex flex-wrap gap-2">
                          {(productDraft.artwork_associations || []).map((item) => (
                            <Button key={item.artwork_id} type="button" size="sm" variant="outline" onClick={() => removeAssociation("artwork_associations", "artwork_id", item.artwork_id)}>{item.artwork_id} remove</Button>
                          ))}
                        </div>
                        <p className="text-xs text-muted-foreground">Artwork stays private to Staff and production workflows.</p>
                      </div>
                      <div className="grid gap-1.5">
                        <Label>Mockups</Label>
                        <Select value="none" onValueChange={(value) => addAssociation("mockup_associations", "mockup_id", value)}>
                          <SelectTrigger data-testid="webstore-product-mockup-associations"><SelectValue placeholder="Associate mockup" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">Choose mockup</SelectItem>
                            {(mockupOptions.data || []).map((mockup) => <SelectItem key={mockup.id} value={mockup.id}>{mockup.alt_text || mockup.purpose || mockup.id}</SelectItem>)}
                          </SelectContent>
                        </Select>
                        <div className="flex flex-wrap gap-2">
                          {(productDraft.mockup_associations || []).map((item) => (
                            <Button key={item.mockup_id} type="button" size="sm" variant="outline" onClick={() => removeAssociation("mockup_associations", "mockup_id", item.mockup_id)}>{item.mockup_id} remove</Button>
                          ))}
                        </div>
                        <p className="text-xs text-muted-foreground">Mockups are read-only previews until approval is added later.</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button onClick={() => saveProduct.mutate()} disabled={saveProduct.isPending || !productDraft.name} data-testid="webstore-save-product"><Save className="size-4 mr-2" />Save Draft</Button>
                      {productDraft.status === "archived" ? (
                        <Button variant="outline" onClick={() => restoreProduct.mutate(productDraft)}><RotateCcw className="size-4 mr-2" />Restore Draft</Button>
                      ) : (
                        <Button variant="outline" onClick={() => archiveProduct.mutate(productDraft)}><Archive className="size-4 mr-2" />Archive</Button>
                      )}
                    </div>
                    {selectedProduct?.template_provenance?.source_template_id && <div className="text-xs text-muted-foreground">Copied from template {selectedProduct.template_provenance.source_template_id} at revision {selectedProduct.template_provenance.source_template_revision || "unknown"}. This product is independent from later template changes.</div>}
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Templates</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-2 md:grid-cols-2">
                  <Input placeholder="Template name" value={templateDraft.template_name} onChange={(e) => setTemplateDraft({ ...templateDraft, template_name: e.target.value })} data-testid="webstore-template-name" />
                  <Input placeholder="Product type" value={templateDraft.product_type} onChange={(e) => setTemplateDraft({ ...templateDraft, product_type: e.target.value })} />
                  <Input placeholder="Suggested category" value={templateDraft.product_category} onChange={(e) => setTemplateDraft({ ...templateDraft, product_category: e.target.value })} />
                  <Input placeholder="Default product title" value={templateDraft.default_title} onChange={(e) => setTemplateDraft({ ...templateDraft, default_title: e.target.value })} />
                  <Input placeholder="Production method" value={templateDraft.production_method || ""} onChange={(e) => setTemplateDraft({ ...templateDraft, production_method: e.target.value })} />
                  <Select value={templateDraft.default_customer_images?.primary?.file_id || "none"} onValueChange={(value) => setTemplateDraft({ ...templateDraft, default_customer_images: value === "none" ? {} : { ...(templateDraft.default_customer_images || {}), primary: { ...((templateDraft.default_customer_images || {}).primary || {}), file_id: value, alt_text: ((templateDraft.default_customer_images || {}).primary || {}).alt_text || templateDraft.default_title } } })}>
                    <SelectTrigger><SelectValue placeholder="Default primary image" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No default image</SelectItem>
                      {setupFileItems.map((file) => <SelectItem key={file.id} value={file.id}>{file.file_name || file.id}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Input placeholder="Default image alternate text" value={templateDraft.default_customer_images?.primary?.alt_text || ""} onChange={(e) => setTemplateDraft({ ...templateDraft, default_customer_images: { ...(templateDraft.default_customer_images || {}), primary: { ...((templateDraft.default_customer_images || {}).primary || {}), alt_text: e.target.value } } })} />
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  <Textarea placeholder="Short description" value={templateDraft.default_short_description || ""} onChange={(e) => setTemplateDraft({ ...templateDraft, default_short_description: e.target.value })} />
                  <Textarea placeholder="Full description" value={templateDraft.default_description || ""} onChange={(e) => setTemplateDraft({ ...templateDraft, default_description: e.target.value })} />
                  <Textarea placeholder="Private supplier/source information" value={templateDraft.supplier_source_info || ""} onChange={(e) => setTemplateDraft({ ...templateDraft, supplier_source_info: e.target.value })} />
                  <Textarea placeholder="Default internal production notes" value={templateDraft.default_production_notes || ""} onChange={(e) => setTemplateDraft({ ...templateDraft, default_production_notes: e.target.value })} />
                  <div className="grid gap-1.5">
                    <Label>Private default artwork</Label>
                    <Select value="none" onValueChange={(value) => addTemplateAssociation(setTemplateDraft, "artwork_id", value)}>
                      <SelectTrigger><SelectValue placeholder="Choose artwork" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Choose artwork</SelectItem>
                        {(artworkOptions.data || []).map((artwork) => <SelectItem key={artwork.id} value={artwork.id}>{artwork.file_name || artwork.purpose || artwork.id}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <div className="flex flex-wrap gap-2">
                      {(templateDraft.default_artwork_associations || []).map((item) => <Button key={item.artwork_id} type="button" size="sm" variant="outline" onClick={() => removeTemplateAssociation(setTemplateDraft, "artwork_id", item.artwork_id)}>{item.artwork_id} remove</Button>)}
                    </div>
                  </div>
                  <div className="grid gap-1.5">
                    <Label>Private default mockups</Label>
                    <Select value="none" onValueChange={(value) => addTemplateAssociation(setTemplateDraft, "mockup_id", value)}>
                      <SelectTrigger><SelectValue placeholder="Choose mockup" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Choose mockup</SelectItem>
                        {(mockupOptions.data || []).map((mockup) => <SelectItem key={mockup.id} value={mockup.id}>{mockup.alt_text || mockup.purpose || mockup.id}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <div className="flex flex-wrap gap-2">
                      {(templateDraft.default_mockup_associations || []).map((item) => <Button key={item.mockup_id} type="button" size="sm" variant="outline" onClick={() => removeTemplateAssociation(setTemplateDraft, "mockup_id", item.mockup_id)}>{item.mockup_id} remove</Button>)}
                    </div>
                  </div>
                </div>
                <Button disabled={!templateDraft.template_name || !templateDraft.product_category || !templateDraft.product_type || createTemplate.isPending} onClick={() => createTemplate.mutate()} data-testid="webstore-create-template">Create Tenant Template</Button>
                <div className="rounded border divide-y">
                  {(templates.data || []).map((template) => (
                    <div key={template.id} className="p-3 text-sm space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <div><div className="font-medium">{template.template_name}</div><div className="text-xs text-muted-foreground">{template.scope === "platform" ? "Platform starter - read only" : "Tenant template"} · {template.status || (template.active ? "active" : "archived")}</div></div>
                        {template.scope === "platform" ? <Badge variant="outline">Starter</Badge> : (
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline" onClick={() => { setEditingTemplateId(template.id); setTemplateEditDraft(template); }}>Edit</Button>
                            {template.status === "archived" ? <Button size="sm" variant="outline" onClick={() => restoreTemplate.mutate(template)}>Restore</Button> : <Button size="sm" variant="outline" onClick={() => archiveTemplate.mutate(template)}>Archive</Button>}
                          </div>
                        )}
                      </div>
                      {editingTemplateId === template.id && (
                        <div className="grid gap-2 md:grid-cols-2 rounded bg-slate-50 p-2">
                          <Input value={templateEditDraft.template_name || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, template_name: e.target.value })} />
                          <Input value={templateEditDraft.default_title || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, default_title: e.target.value })} />
                          <Input value={templateEditDraft.product_type || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, product_type: e.target.value })} />
                          <Input value={templateEditDraft.product_category || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, product_category: e.target.value })} />
                          <Input placeholder="Production method" value={templateEditDraft.production_method || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, production_method: e.target.value })} />
                          <Input placeholder="Suggested category" value={templateEditDraft.suggested_category_name || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, suggested_category_name: e.target.value })} />
                          <Select value={templateEditDraft.default_customer_images?.primary?.file_id || "none"} onValueChange={(value) => setTemplateEditDraft({ ...templateEditDraft, default_customer_images: value === "none" ? {} : { ...(templateEditDraft.default_customer_images || {}), primary: { ...((templateEditDraft.default_customer_images || {}).primary || {}), file_id: value, alt_text: ((templateEditDraft.default_customer_images || {}).primary || {}).alt_text || templateEditDraft.default_title } } })}>
                            <SelectTrigger><SelectValue placeholder="Default primary image" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">No default image</SelectItem>
                              {setupFileItems.map((file) => <SelectItem key={file.id} value={file.id}>{file.file_name || file.id}</SelectItem>)}
                            </SelectContent>
                          </Select>
                          <Input placeholder="Default image alternate text" value={templateEditDraft.default_customer_images?.primary?.alt_text || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, default_customer_images: { ...(templateEditDraft.default_customer_images || {}), primary: { ...((templateEditDraft.default_customer_images || {}).primary || {}), alt_text: e.target.value } } })} />
                          <Textarea placeholder="Short description" value={templateEditDraft.default_short_description || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, default_short_description: e.target.value })} />
                          <Textarea placeholder="Full description" value={templateEditDraft.default_description || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, default_description: e.target.value })} />
                          <Textarea placeholder="Private supplier/source information" value={templateEditDraft.supplier_source_info || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, supplier_source_info: e.target.value })} />
                          <Textarea placeholder="Default internal production notes" value={templateEditDraft.default_production_notes || ""} onChange={(e) => setTemplateEditDraft({ ...templateEditDraft, default_production_notes: e.target.value })} />
                          <div className="grid gap-1.5">
                            <Label>Private default artwork</Label>
                            <Select value="none" onValueChange={(value) => addTemplateAssociation(setTemplateEditDraft, "artwork_id", value)}>
                              <SelectTrigger><SelectValue placeholder="Choose artwork" /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="none">Choose artwork</SelectItem>
                                {(artworkOptions.data || []).map((artwork) => <SelectItem key={artwork.id} value={artwork.id}>{artwork.file_name || artwork.purpose || artwork.id}</SelectItem>)}
                              </SelectContent>
                            </Select>
                            <div className="flex flex-wrap gap-2">
                              {(templateEditDraft.default_artwork_associations || []).map((item) => <Button key={item.artwork_id} type="button" size="sm" variant="outline" onClick={() => removeTemplateAssociation(setTemplateEditDraft, "artwork_id", item.artwork_id)}>{item.artwork_id} remove</Button>)}
                            </div>
                          </div>
                          <div className="grid gap-1.5">
                            <Label>Private default mockups</Label>
                            <Select value="none" onValueChange={(value) => addTemplateAssociation(setTemplateEditDraft, "mockup_id", value)}>
                              <SelectTrigger><SelectValue placeholder="Choose mockup" /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="none">Choose mockup</SelectItem>
                                {(mockupOptions.data || []).map((mockup) => <SelectItem key={mockup.id} value={mockup.id}>{mockup.alt_text || mockup.purpose || mockup.id}</SelectItem>)}
                              </SelectContent>
                            </Select>
                            <div className="flex flex-wrap gap-2">
                              {(templateEditDraft.default_mockup_associations || []).map((item) => <Button key={item.mockup_id} type="button" size="sm" variant="outline" onClick={() => removeTemplateAssociation(setTemplateEditDraft, "mockup_id", item.mockup_id)}>{item.mockup_id} remove</Button>)}
                            </div>
                          </div>
                          <Button size="sm" disabled={!templateEditDraft.template_name || saveTemplate.isPending} onClick={() => saveTemplate.mutate()} data-testid="webstore-save-template">Save</Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="text-base">Categories</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                  <Input placeholder="Category name" value={categoryDraft.name} onChange={(e) => setCategoryDraft({ ...categoryDraft, name: e.target.value })} data-testid="webstore-category-name" />
                  <Input placeholder="Customer-facing description" value={categoryDraft.description} onChange={(e) => setCategoryDraft({ ...categoryDraft, description: e.target.value })} />
                  <Button disabled={!categoryDraft.name || createCategory.isPending} onClick={() => createCategory.mutate()} data-testid="webstore-create-category">Create</Button>
                </div>
                <div className="rounded border divide-y">
                  {(categories.data?.items || []).map((category) => (
                    <div key={category.id} className="p-3 text-sm space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <div><div className="font-medium">{category.name}</div><div className="text-xs text-muted-foreground">{category.status} · {category.product_count || 0} active products</div></div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={() => { setEditingCategoryId(category.id); setCategoryEditDraft(category); }}>Edit</Button>
                          {category.status === "archived" ? <Button size="sm" variant="outline" onClick={() => restoreCategory.mutate(category)}>Restore</Button> : <Button size="sm" variant="outline" onClick={() => archiveCategory.mutate(category)}>Archive</Button>}
                        </div>
                      </div>
                      {editingCategoryId === category.id && (
                        <div className="grid gap-2 md:grid-cols-[1fr_1fr_auto] rounded bg-slate-50 p-2">
                          <Input value={categoryEditDraft.name || ""} onChange={(e) => setCategoryEditDraft({ ...categoryEditDraft, name: e.target.value })} />
                          <Input value={categoryEditDraft.description || ""} onChange={(e) => setCategoryEditDraft({ ...categoryEditDraft, description: e.target.value })} />
                          <Button size="sm" disabled={!categoryEditDraft.name || saveCategory.isPending} onClick={() => saveCategory.mutate()} data-testid="webstore-save-category">Save</Button>
                        </div>
                      )}
                    </div>
                  ))}
                  {(categories.data?.legacy_categories || []).map((name) => <div key={name} className="p-3 text-xs text-muted-foreground">Legacy free-text category preserved: {name}</div>)}
                </div>
              </CardContent>
            </Card>
          </div>
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
