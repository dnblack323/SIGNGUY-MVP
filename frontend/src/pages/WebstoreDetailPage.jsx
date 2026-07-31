import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, CheckCircle2, Clock, ExternalLink, Eye, FileUp, Lock, PackagePlus, Palette, RotateCcw, Save, Send, ShieldCheck, Sparkles, UserPlus } from "lucide-react";
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
  updateWebstoreProduct,
  updateWebstoreProductCategory,
  archiveWebstoreProduct,
  archiveWebstoreProductCategory,
  restoreWebstoreProduct,
  restoreWebstoreProductCategory,
  updateWebstore,
} from "@/lib/webstores";
import { toast } from "sonner";

const CUSTOMER_IMAGE_SLOTS = ["primary", "secondary"];

function productImagesForSave(draft = {}) {
  const bySlot = {};
  const responseImages = Array.isArray(draft.images) ? draft.images : [];
  CUSTOMER_IMAGE_SLOTS.forEach((slot) => {
    const explicit = draft.customer_images?.[slot];
    const responseImage = responseImages.find((image) => image?.slot === slot);
    const source = explicit || responseImage;
    if (!source) return;
    const fileId = source.file_id || source.fileId;
    const url = source.preview_url || source.url;
    const altText = source.alt_text || source.altText || "";
    if (!fileId && !url && !altText) return;
    bySlot[slot] = {
      slot,
      role: source.role || slot,
      ...(fileId ? { file_id: fileId } : {}),
      ...(source.file_name ? { file_name: source.file_name } : {}),
      ...(source.content_type ? { content_type: source.content_type } : {}),
      ...(!fileId && url ? { url } : {}),
      ...(altText ? { alt_text: altText } : {}),
    };
  });
  return bySlot;
}

function productImageForSlot(product = {}, slot = "primary") {
  const explicit = product.customer_images?.[slot];
  const responseImage = Array.isArray(product.images)
    ? product.images.find((image) => image?.slot === slot)
    : null;
  return { explicit, responseImage };
}

function staffProductImageUrl(product = {}, slot = "primary") {
  const { explicit, responseImage } = productImageForSlot(product, slot);
  return explicit?.preview_url
    || explicit?.url
    || responseImage?.preview_url
    || responseImage?.url
    || "";
}

function productImageAltText(product = {}, slot = "primary") {
  const { explicit, responseImage } = productImageForSlot(product, slot);
  return explicit?.alt_text || responseImage?.alt_text || "";
}

function toIntCents(value) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

function productCatalogStatus(product = {}) {
  return product.catalog_status || product.setup_status || (product.status === "draft" ? "planned" : product.status || "planned");
}

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
      if (productFilters.status !== "all" && productCatalogStatus(product) !== productFilters.status && product.status !== productFilters.status) return false;
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
      sku: productDraft.sku || undefined,
      selling_price_cents: toIntCents(productDraft.selling_price_cents),
      production_cost_cents: toIntCents(productDraft.production_cost_cents),
      store_owner_share_cents: toIntCents(productDraft.store_owner_share_cents),
      fundraiser_share_cents: toIntCents(productDraft.fundraiser_share_cents),
      platform_fee_basis_points: toIntCents(productDraft.platform_fee_basis_points ?? 150),
      variants: productDraft.variants || [],
      personalization_enabled: Boolean(productDraft.personalization_enabled),
      personalization_fields: productDraft.personalization_fields || [],
      bundle_items: productDraft.bundle_items || [],
      inventory_policy: productDraft.inventory_policy || "not_tracked",
      inventory_quantity: productDraft.inventory_quantity === "" || productDraft.inventory_quantity == null ? undefined : toIntCents(productDraft.inventory_quantity),
      status: productDraft.status || "draft",
      launch_packet_eligible: Boolean(productDraft.launch_packet_eligible),
      launch_packet_include: Boolean(productDraft.launch_packet_include),
      production_method: productDraft.production_method,
      production_notes: productDraft.production_notes,
      supplier_source_info: productDraft.supplier_source_info,
      fulfillment_notes: productDraft.fulfillment_notes,
      customer_images: productImagesForSave(productDraft),
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
    const images = Array.isArray(draft.images) ? draft.images.filter((image) => image?.slot !== slot) : draft.images;
    return { ...draft, customer_images: next, images };
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
  const addVariant = () => setProductDraft((draft) => ({
    ...draft,
    variants: [
      ...(draft.variants || []),
      { id: `variant-${(draft.variants || []).length + 1}`, size: "", color: "", sku: "", selling_price_cents: draft.selling_price_cents || 0, status: "active", available: true },
    ],
  }));
  const setVariantField = (index, field, value) => setProductDraft((draft) => ({
    ...draft,
    variants: (draft.variants || []).map((variant, currentIndex) => (
      currentIndex === index ? { ...variant, [field]: value } : variant
    )),
  }));
  const removeVariant = (index) => setProductDraft((draft) => ({
    ...draft,
    variants: (draft.variants || []).filter((_, currentIndex) => currentIndex !== index),
  }));
  const addPersonalizationField = () => setProductDraft((draft) => ({
    ...draft,
    personalization_enabled: true,
    personalization_fields: [
      ...(draft.personalization_fields || []),
      { key: `field_${(draft.personalization_fields || []).length + 1}`, label: "", type: "text", required: false },
    ],
  }));
  const setPersonalizationField = (index, field, value) => setProductDraft((draft) => ({
    ...draft,
    personalization_fields: (draft.personalization_fields || []).map((item, currentIndex) => (
      currentIndex === index ? { ...item, [field]: value } : item
    )),
  }));
  const removePersonalizationField = (index) => setProductDraft((draft) => ({
    ...draft,
    personalization_fields: (draft.personalization_fields || []).filter((_, currentIndex) => currentIndex !== index),
  }));
  const addBundleItem = (productId) => {
    if (!productId || productId === "none") return;
    const bundled = (detail.data?.products || []).find((item) => item.id === productId);
    setProductDraft((draft) => {
      if ((draft.bundle_items || []).some((item) => item.product_id === productId)) return draft;
      return {
        ...draft,
        bundle_items: [...(draft.bundle_items || []), { product_id: productId, name_snapshot: bundled?.name, quantity: 1, sku_snapshot: bundled?.sku }],
      };
    });
  };
  const removeBundleItem = (productId) => setProductDraft((draft) => ({
    ...draft,
    bundle_items: (draft.bundle_items || []).filter((item) => item.product_id !== productId),
  }));
  const formatLabel = (value) => String(value || "").replace(/_/g, " ");
  const formatDateTime = (value) => {
    if (!value) return "Not recorded";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Not recorded";
    return date.toLocaleString();
  };
  const ownerAssignment = (assignments.data || []).find((item) => item.role === "owner")
    || (assignments.data || [])[0];
  const questionnaireSubmission = questionnaireResponse.data?.submission;
  const questionnaireAnswers = questionnaireSubmission?.submitted_snapshot?.answers
    || questionnaireSubmission?.answers
    || {};
  const questionnaireAnswerRows = Object.entries(questionnaireAnswers)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .slice(0, 8);
  const activeProducts = (detail.data?.products || []).filter((product) => product.status !== "archived");
  const selectedProductsCount = activeProducts.length;
  const uploadCount = setupFileItems.length;
  const currentBuilderStep = selectedProductId ? "Product Setup" : selectedProductsCount ? "Product Setup" : "Product Plan";
  const nextRequiredAction = selectedProductsCount
    ? "Continue setup on selected draft products before launch preparation."
    : "Review the product plan, then add a custom product or copy from a template.";
  const workflowSteps = [
    { label: "Webstore Details", state: "complete" },
    { label: "Owner & Questionnaire", state: questionnaireSubmission ? "complete" : "waiting", note: questionnaireSubmission ? "Complete" : "Waiting on owner" },
    { label: "Branding & Artwork", state: uploadCount ? "complete" : "waiting", note: uploadCount ? `${uploadCount} upload${uploadCount === 1 ? "" : "s"}` : "Waiting on owner" },
    { label: "Product Plan", state: selectedProductsCount ? "complete" : "current", note: selectedProductsCount ? "Products selected" : "Current" },
    { label: "Product Setup", state: selectedProductsCount ? "current" : "waiting", note: selectedProductsCount ? `${selectedProductsCount} draft${selectedProductsCount === 1 ? "" : "s"}` : "Not ready yet" },
    { label: "Launch Setup", state: "future", note: "Coming in a later stage" },
    { label: "Owner Approval", state: "future", note: "Coming in a later stage" },
    { label: "Launch & Manage", state: "future", note: "Coming in a later stage" },
  ];
  const getProductSetupItems = (product) => [
    { label: "Basic information", done: Boolean(product?.name && product?.product_type) },
    { label: "Image or mockup", done: Boolean(staffProductImageUrl(product, "primary")) },
    { label: "Category", done: Boolean(product?.category_id || product?.category_name || product?.category) },
    { label: "Pricing", done: Number(product?.selling_price_cents || 0) > 0 },
    { label: "SKU or options", done: Boolean(product?.sku || (product?.variants || []).length) },
    { label: "Production setup", done: Boolean(product?.production_method || product?.production_notes) },
    { label: "Packet eligible", done: Boolean(product?.launch_packet_eligible || productCatalogStatus(product) === "ready" || productCatalogStatus(product) === "active") },
  ];
  const startProductSetup = (product) => {
    setSelectedProductId(product.id);
    setProductDraft(product);
    setProductError("");
  };

  if (detail.isLoading) return <div className="p-6 text-sm text-muted-foreground">Loading...</div>;
  if (!store) return <div className="p-6 text-sm text-rose-700">Webstore not found.</div>;

  return (
    <div className="space-y-4" data-testid="webstore-detail-page">
      <PageHeader
        title="Webstore Builder"
        subtitle={`${store.name} - ${formatLabel(store.webstore_type || store.store_type || "general")} webstore - ${formatLabel(store.status)}`}
        actions={(
          <div className="flex items-center gap-2 flex-wrap">
            {ownerAssignment ? (
              <Button asChild variant="outline" size="sm"><Link to={`/portal/webstores/${id}`}><ExternalLink className="size-4 mr-2" />View Webstore Owner Portal</Link></Button>
            ) : (
              <Button variant="outline" size="sm" disabled><ExternalLink className="size-4 mr-2" />Webstore Owner Portal Not Ready</Button>
            )}
            {store.status === "live" && (store.public_url || store.public_slug || store.slug) ? (
              <Button asChild variant="outline" size="sm"><Link to={store.public_url || `/p/webstores/${store.public_slug || store.slug}`}><Eye className="size-4 mr-2" />Preview Webstore</Link></Button>
            ) : (
              <Button variant="outline" size="sm" disabled><Eye className="size-4 mr-2" />Preview Not Ready</Button>
            )}
          </div>
        )}
      />

      <div className="grid gap-3 rounded-lg border bg-white p-4 shadow-sm md:grid-cols-[1fr_280px]" data-testid="webstore-builder-header">
        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <div className="text-xs font-medium uppercase text-muted-foreground">Webstore Type</div>
            <div className="font-semibold capitalize">{formatLabel(store.webstore_type || store.store_type || "general")}</div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase text-muted-foreground">Webstore Owner</div>
            <div className="font-semibold">{ownerAssignment?.name || ownerAssignment?.email || "Not assigned"}</div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase text-muted-foreground">Workflow status</div>
            <div className="font-semibold capitalize">{formatLabel(store.setup_state || setupProgress.data?.setup_state || store.status)}</div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase text-muted-foreground">Last updated</div>
            <div className="font-semibold">{formatDateTime(store.updated_at || store.created_at)}</div>
          </div>
        </div>
        <div className="rounded-md border bg-slate-50 p-3">
          <div className="text-xs font-medium uppercase text-muted-foreground">Next required action</div>
          <div className="mt-1 text-sm font-medium">{nextRequiredAction}</div>
        </div>
      </div>

      <div className="grid gap-2 rounded-lg border bg-white p-3 shadow-sm sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8" data-testid="webstore-builder-progress">
        {workflowSteps.map((step, index) => (
          <div key={step.label} className={`rounded-md border p-2 text-sm ${step.state === "current" ? "border-sky-500 bg-sky-50" : step.state === "complete" ? "border-emerald-200 bg-emerald-50" : "bg-slate-50"}`}>
            <div className="flex items-center gap-2">
              {step.state === "complete" ? <CheckCircle2 className="size-4 text-emerald-700" /> : step.state === "future" ? <Lock className="size-4 text-slate-500" /> : <Clock className="size-4 text-sky-700" />}
              <span className="font-medium">{index + 1}. {step.label}</span>
            </div>
            <div className="mt-1 text-xs text-muted-foreground">{step.note || formatLabel(step.state)}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-3 md:grid-cols-4" data-testid="webstore-builder-status-panel">
        <Card><CardContent className="p-3 text-sm"><div className="text-xs font-medium uppercase text-muted-foreground">Current step</div><div className="font-semibold">{currentBuilderStep}</div></CardContent></Card>
        <Card><CardContent className="p-3 text-sm"><div className="text-xs font-medium uppercase text-muted-foreground">Owner questionnaire</div><div className="font-semibold">{questionnaireSubmission ? "Submitted" : "Waiting on owner"}</div></CardContent></Card>
        <Card><CardContent className="p-3 text-sm"><div className="text-xs font-medium uppercase text-muted-foreground">AI review</div><div className="font-semibold">Coming in a later stage</div></CardContent></Card>
        <Card><CardContent className="p-3 text-sm"><div className="text-xs font-medium uppercase text-muted-foreground">Products selected</div><div className="font-semibold">{selectedProductsCount}</div></CardContent></Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-4" data-testid="webstore-detail-tabs">
        <TabsList className="flex h-auto flex-wrap justify-start">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="product-plan">Product Plan</TabsTrigger>
          <TabsTrigger value="product-setup">Product Setup</TabsTrigger>
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

        <TabsContent value="product-plan" className="space-y-4" data-testid="webstore-product-plan">
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_1.1fr] gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Questionnaire Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="grid gap-3 md:grid-cols-2">
                  <div>
                    <div className="text-xs font-medium uppercase text-muted-foreground">Status</div>
                    <div className="font-semibold">{questionnaireSubmission ? "Submitted" : "Waiting on owner"}</div>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase text-muted-foreground">Uploaded logo/artwork</div>
                    <div className="font-semibold">{uploadCount}</div>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase text-muted-foreground">Purpose</div>
                    <div className="font-semibold">{questionnaireAnswers.purpose || questionnaireAnswers.store_purpose || "Not answered"}</div>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase text-muted-foreground">Audience</div>
                    <div className="font-semibold">{questionnaireAnswers.audience || questionnaireAnswers.target_audience || "Not answered"}</div>
                  </div>
                </div>
                <div className="rounded-md border">
                  {questionnaireAnswerRows.length ? questionnaireAnswerRows.map(([key, value]) => (
                    <div key={key} className="grid gap-1 border-b p-3 last:border-b-0 md:grid-cols-[180px_1fr]">
                      <div className="font-medium capitalize">{formatLabel(key)}</div>
                      <div className="text-muted-foreground">{Array.isArray(value) ? value.join(", ") : String(value)}</div>
                    </div>
                  )) : (
                    <div className="p-3 text-muted-foreground">The owner questionnaire has not produced reviewable answers yet.</div>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" disabled={!questionnaireSubmission}>View Full Questionnaire</Button>
                  <Button type="button" variant="outline" disabled>Request Missing Information</Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2"><Sparkles className="size-4" />AI Product Suggestions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Alert>
                  <AlertTitle>No generated suggestions yet</AlertTitle>
                  <AlertDescription>AI product recommendations, mockups, pricing suggestions, owner-share estimates, and regeneration actions are planned for a later Webstores stage and are not active here.</AlertDescription>
                </Alert>
                <div className="rounded-md border bg-slate-50 p-4 text-sm text-muted-foreground">
                  Suggestions will appear here as selectable product cards after the AI product-planning workflow is implemented.
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" disabled>Include Product</Button>
                  <Button type="button" variant="outline" disabled>Skip</Button>
                  <Button type="button" variant="outline" disabled>Edit Suggestion</Button>
                  <Button type="button" variant="outline" disabled>Regenerate Description</Button>
                  <Button type="button" variant="outline" disabled>Request Different Mockup</Button>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Add Another Product</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
              <Select value={templateId} onValueChange={setTemplateId}>
                <SelectTrigger data-testid="webstore-stage4-template-select"><SelectValue placeholder="Add from template" /></SelectTrigger>
                <SelectContent>{(templates.data || []).filter((t) => t.status !== "archived").map((t) => <SelectItem value={t.id} key={t.id}>{t.template_name}{t.scope === "platform" ? " (starter)" : ""}</SelectItem>)}</SelectContent>
              </Select>
              <Button disabled={!templateId || addProduct.isPending} onClick={() => addProduct.mutate()} data-testid="webstore-add-template-draft"><PackagePlus className="size-4 mr-2" />Add From Template</Button>
              <Button variant="outline" onClick={() => createBlankProduct.mutate()} disabled={createBlankProduct.isPending} data-testid="webstore-create-blank-product"><PackagePlus className="size-4 mr-2" />Create Custom Product</Button>
              <Button type="button" variant="outline" disabled className="lg:col-start-3">Ask AI for Another Suggestion</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="product-setup" className="space-y-4" data-testid="webstore-product-foundation">
          <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_1.4fr] gap-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Selected Products</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <Alert>
                  <AlertTitle>Private catalog setup</AlertTitle>
                  <AlertDescription>Each selected product stays private while Staff completes catalog status, options, cents-based pricing, shares, media, and packet eligibility.</AlertDescription>
                </Alert>
                <div className="grid gap-2 md:grid-cols-3">
                  <Input placeholder="Search products" value={productFilters.q} onChange={(e) => setProductFilters({ ...productFilters, q: e.target.value })} data-testid="webstore-product-search" />
                  <Select value={productFilters.status} onValueChange={(value) => setProductFilters({ ...productFilters, status: value })}>
                    <SelectTrigger data-testid="webstore-product-status-filter"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All statuses</SelectItem>
                      <SelectItem value="planned">Planned</SelectItem>
                      <SelectItem value="incomplete">Incomplete</SelectItem>
                      <SelectItem value="ready">Ready</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
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
                  <Button variant="outline" onClick={() => createBlankProduct.mutate()} disabled={createBlankProduct.isPending} data-testid="webstore-create-blank-product"><PackagePlus className="size-4 mr-2" />Create Custom Product</Button>
                  <Button asChild variant="link" size="sm"><Link to="/webstores">Manage Product Templates</Link></Button>
                  <Button asChild variant="link" size="sm"><Link to="/webstores">Manage Categories</Link></Button>
                </div>
                <div className="grid gap-3">
                  {filteredProducts.map((product) => (
                    <div key={product.id} className="rounded-md border p-3 text-sm" data-testid={`webstore-product-card-${product.id}`}>
                      <div className="flex gap-3">
                        <div className="h-20 w-24 shrink-0 overflow-hidden rounded border bg-slate-100">
                          {staffProductImageUrl(product) ? (
                            <img className="h-full w-full object-cover" src={staffProductImageUrl(product)} alt="" />
                          ) : (
                            <div className="flex h-full items-center justify-center text-xs text-muted-foreground">No image</div>
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div>
                              <div className="font-medium">{product.name}</div>
                              <div className="text-xs text-muted-foreground capitalize">{formatLabel(productCatalogStatus(product))} - {product.public ? "public legacy" : "private catalog"} - {product.category_name || product.category || "No category"}</div>
                            </div>
                            <Badge variant="outline">{centsToDollarsString(product.selling_price_cents)}</Badge>
                          </div>
                          <div className="mt-3 grid gap-1 text-xs text-muted-foreground md:grid-cols-2">
                            {getProductSetupItems(product).map((item) => (
                              <div key={item.label} className="flex items-center gap-2">
                                {item.done ? <CheckCircle2 className="size-3 text-emerald-700" /> : <Clock className="size-3 text-amber-700" />}
                                <span>{item.label}</span>
                              </div>
                            ))}
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <Button type="button" size="sm" onClick={() => startProductSetup(product)} data-testid={`webstore-product-row-${product.id}`}>Continue Setup</Button>
                            <Button type="button" size="sm" variant="outline" disabled={!staffProductImageUrl(product)}>Preview</Button>
                            {product.status === "archived" ? (
                              <Button type="button" size="sm" variant="outline" onClick={() => restoreProduct.mutate(product)}>Restore</Button>
                            ) : (
                              <Button type="button" size="sm" variant="outline" onClick={() => archiveProduct.mutate(product)}>Archive</Button>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                  {filteredProducts.length === 0 && <div className="p-3 text-sm text-muted-foreground">No products match these filters.</div>}
                </div>
              </CardContent>
            </Card>

            <Card data-testid="webstore-product-editor">
              <CardHeader><CardTitle className="text-base">Focused Product Setup</CardTitle></CardHeader>
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
                    <Tabs defaultValue="basic" className="space-y-3" data-testid="webstore-product-editor-sections">
                      <TabsList className="flex h-auto flex-wrap justify-start">
                        <TabsTrigger value="basic">Basic Information</TabsTrigger>
                        <TabsTrigger value="images">Images and Mockups</TabsTrigger>
                        <TabsTrigger value="options">Options and Personalization</TabsTrigger>
                        <TabsTrigger value="pricing">Pricing and Shares</TabsTrigger>
                        <TabsTrigger value="production">Production Setup</TabsTrigger>
                        <TabsTrigger value="review">Review Status</TabsTrigger>
                      </TabsList>

                      <TabsContent value="basic" className="space-y-3">
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="grid gap-1.5"><Label>Name</Label><Input value={productDraft.name || ""} onChange={(e) => setProductField("name", e.target.value)} data-testid="webstore-product-name" /></div>
                      <div className="grid gap-1.5"><Label>Product type</Label><Input value={productDraft.product_type || ""} onChange={(e) => setProductField("product_type", e.target.value)} /></div>
                      <div className="grid gap-1.5"><Label>Category</Label><Select value={productDraft.category_id || "none"} onValueChange={(value) => setProductDraft({ ...productDraft, category_id: value === "none" ? "" : value, category_name: (categories.data?.items || []).find((c) => c.id === value)?.name || "" })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="none">No category</SelectItem>{(categories.data?.items || []).filter((category) => category.status === "active").map((category) => <SelectItem key={category.id} value={category.id}>{category.name}</SelectItem>)}</SelectContent></Select></div>
                      <div className="grid gap-1.5"><Label>Production method</Label><Input value={productDraft.production_method || ""} onChange={(e) => setProductField("production_method", e.target.value)} /></div>
                    </div>
                    <div className="grid gap-1.5"><Label>Short description</Label><Textarea value={productDraft.short_description || ""} onChange={(e) => setProductField("short_description", e.target.value)} /></div>
                    <div className="grid gap-1.5"><Label>Full description</Label><Textarea value={productDraft.full_description || ""} onChange={(e) => setProductField("full_description", e.target.value)} /></div>
                      </TabsContent>
                      <TabsContent value="images" className="space-y-3">
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
                          <Input placeholder="Alternate text" value={productImageAltText(productDraft, slot)} onChange={(e) => setImageField(slot, "alt_text", e.target.value)} />
                          <p className="text-xs text-muted-foreground">{slot === "primary" ? "Recommended: 1600x1200 px or larger." : "Recommended: 1200x1200 px or larger."}</p>
                          {staffProductImageUrl(productDraft, slot) && (
                            <img
                              className="aspect-video w-full rounded border object-cover"
                              src={staffProductImageUrl(productDraft, slot)}
                              alt={productImageAltText(productDraft, slot)}
                            />
                          )}
                          <Button type="button" size="sm" variant="outline" onClick={() => removeImageSlot(slot)}>Remove</Button>
                        </div>
                      ))}
                    </div>
                      </TabsContent>
                      <TabsContent value="options" className="space-y-4">
                        <div className="space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <Label>Variants and SKUs</Label>
                            <Button type="button" size="sm" variant="outline" onClick={addVariant}>Add Variant</Button>
                          </div>
                          <div className="grid gap-2">
                            {(productDraft.variants || []).map((variant, index) => (
                              <div key={variant.id || index} className="grid gap-2 rounded border p-2 md:grid-cols-[1fr_1fr_1fr_120px_auto]">
                                <Input placeholder="Size" value={variant.size || ""} onChange={(e) => setVariantField(index, "size", e.target.value)} data-testid={`webstore-variant-size-${index}`} />
                                <Input placeholder="Color" value={variant.color || ""} onChange={(e) => setVariantField(index, "color", e.target.value)} data-testid={`webstore-variant-color-${index}`} />
                                <Input placeholder="SKU" value={variant.sku || ""} onChange={(e) => setVariantField(index, "sku", e.target.value)} data-testid={`webstore-variant-sku-${index}`} />
                                <Input type="number" min="0" placeholder="Price cents" value={variant.selling_price_cents ?? ""} onChange={(e) => setVariantField(index, "selling_price_cents", toIntCents(e.target.value))} data-testid={`webstore-variant-price-${index}`} />
                                <Button type="button" size="sm" variant="outline" onClick={() => removeVariant(index)}>Remove</Button>
                              </div>
                            ))}
                            {(productDraft.variants || []).length === 0 && <div className="rounded border p-3 text-sm text-muted-foreground">No variants yet. A single SKU can still be saved on this product.</div>}
                          </div>
                        </div>
                        <div className="grid gap-3 md:grid-cols-2">
                          <div className="grid gap-1.5"><Label>Product SKU</Label><Input value={productDraft.sku || ""} onChange={(e) => setProductField("sku", e.target.value)} data-testid="webstore-product-sku" /></div>
                          <div className="grid gap-1.5"><Label>Inventory policy</Label><Select value={productDraft.inventory_policy || "not_tracked"} onValueChange={(value) => setProductField("inventory_policy", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="not_tracked">Not tracked</SelectItem><SelectItem value="track_quantity">Track quantity</SelectItem><SelectItem value="made_to_order">Made to order</SelectItem></SelectContent></Select></div>
                          <div className="grid gap-1.5"><Label>Inventory quantity</Label><Input type="number" min="0" value={productDraft.inventory_quantity ?? ""} onChange={(e) => setProductField("inventory_quantity", e.target.value === "" ? "" : toIntCents(e.target.value))} /></div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <Label>Personalization</Label>
                            <div className="flex items-center gap-2 text-sm"><Checkbox checked={Boolean(productDraft.personalization_enabled)} onCheckedChange={(checked) => setProductField("personalization_enabled", Boolean(checked))} />Enabled</div>
                          </div>
                          <div className="grid gap-2">
                            {(productDraft.personalization_fields || []).map((field, index) => (
                              <div key={field.key || index} className="grid gap-2 rounded border p-2 md:grid-cols-[1fr_1fr_120px_auto]">
                                <Input placeholder="Key" value={field.key || ""} onChange={(e) => setPersonalizationField(index, "key", e.target.value)} />
                                <Input placeholder="Prompt label" value={field.label || ""} onChange={(e) => setPersonalizationField(index, "label", e.target.value)} data-testid={`webstore-personalization-label-${index}`} />
                                <Select value={field.type || "text"} onValueChange={(value) => setPersonalizationField(index, "type", value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="text">Text</SelectItem><SelectItem value="textarea">Textarea</SelectItem><SelectItem value="select">Select</SelectItem><SelectItem value="number">Number</SelectItem></SelectContent></Select>
                                <Button type="button" size="sm" variant="outline" onClick={() => removePersonalizationField(index)}>Remove</Button>
                              </div>
                            ))}
                          </div>
                          <Button type="button" size="sm" variant="outline" onClick={addPersonalizationField} data-testid="webstore-add-personalization">Add Prompt</Button>
                        </div>
                      </TabsContent>
                      <TabsContent value="pricing" className="space-y-3">
                        <div className="grid gap-3 md:grid-cols-2">
                          <div className="grid gap-1.5"><Label>Selling price (cents)</Label><Input type="number" min="0" value={productDraft.selling_price_cents ?? 0} onChange={(e) => setProductField("selling_price_cents", toIntCents(e.target.value))} data-testid="webstore-product-selling-price" /></div>
                          <div className="grid gap-1.5"><Label>Production cost (cents)</Label><Input type="number" min="0" value={productDraft.production_cost_cents ?? 0} onChange={(e) => setProductField("production_cost_cents", toIntCents(e.target.value))} data-testid="webstore-product-production-cost" /></div>
                          <div className="grid gap-1.5"><Label>Owner share (cents)</Label><Input type="number" min="0" value={productDraft.store_owner_share_cents ?? 0} onChange={(e) => setProductField("store_owner_share_cents", toIntCents(e.target.value))} data-testid="webstore-product-owner-share" /></div>
                          <div className="grid gap-1.5"><Label>Fundraiser share (cents)</Label><Input type="number" min="0" value={productDraft.fundraiser_share_cents ?? 0} onChange={(e) => setProductField("fundraiser_share_cents", toIntCents(e.target.value))} /></div>
                          <div className="grid gap-1.5"><Label>Platform fee (basis points)</Label><Input type="number" min="0" max="10000" value={productDraft.platform_fee_basis_points ?? 150} onChange={(e) => setProductField("platform_fee_basis_points", toIntCents(e.target.value))} /></div>
                          <div className="rounded-md border bg-slate-50 p-3 text-sm">
                            <div className="font-medium">Internal margin</div>
                            <div className="text-muted-foreground">{centsToDollarsString(Math.max(0, Number(productDraft.selling_price_cents || 0) - Number(productDraft.production_cost_cents || 0) - Number(productDraft.store_owner_share_cents || 0) - Number(productDraft.fundraiser_share_cents || 0)))}</div>
                          </div>
                        </div>
                      </TabsContent>
                      <TabsContent value="production" className="space-y-3">
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="grid gap-1.5"><Label>Internal production notes</Label><Textarea value={productDraft.production_notes || ""} onChange={(e) => setProductField("production_notes", e.target.value)} /></div>
                      <div className="grid gap-1.5"><Label>Private supplier/source information</Label><Textarea value={productDraft.supplier_source_info || ""} onChange={(e) => setProductField("supplier_source_info", e.target.value)} /></div>
                      <div className="grid gap-1.5 md:col-span-2"><Label>Private fulfillment notes</Label><Textarea value={productDraft.fulfillment_notes || ""} onChange={(e) => setProductField("fulfillment_notes", e.target.value)} /></div>
                    </div>
                      </TabsContent>
                      <TabsContent value="review" className="space-y-3">
                        <div className="rounded-md border p-3 text-sm">
                          <div className="font-medium">Setup checklist</div>
                          <div className="mt-2 grid gap-1 text-muted-foreground md:grid-cols-2">
                            {getProductSetupItems(productDraft).map((item) => (
                              <div key={item.label} className="flex items-center gap-2">
                                {item.done ? <CheckCircle2 className="size-3 text-emerald-700" /> : <Clock className="size-3 text-amber-700" />}
                                <span>{item.label}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="grid gap-3 md:grid-cols-2">
                          <div className="grid gap-1.5">
                            <Label>Catalog status</Label>
                            <Select value={productDraft.status || "draft"} onValueChange={(value) => setProductField("status", value)}>
                              <SelectTrigger data-testid="webstore-product-status"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="planned">Planned</SelectItem>
                                <SelectItem value="incomplete">Incomplete</SelectItem>
                                <SelectItem value="ready">Ready</SelectItem>
                                <SelectItem value="active">Active</SelectItem>
                                <SelectItem value="archived">Archived</SelectItem>
                                {productDraft.status === "draft" && <SelectItem value="draft">Draft legacy</SelectItem>}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="grid gap-2 rounded border p-3 text-sm">
                            <div className="flex items-center gap-2">
                              <Checkbox checked={Boolean(productDraft.launch_packet_eligible)} onCheckedChange={(checked) => setProductField("launch_packet_eligible", Boolean(checked))} data-testid="webstore-product-packet-eligible" />
                              <Label>Eligible for later Launch Packet</Label>
                            </div>
                            <div className="flex items-center gap-2">
                              <Checkbox checked={Boolean(productDraft.launch_packet_include)} onCheckedChange={(checked) => setProductField("launch_packet_include", Boolean(checked))} data-testid="webstore-product-packet-include" />
                              <Label>Include when Launch Packet assembly is implemented</Label>
                            </div>
                          </div>
                        </div>
                        <div className="grid gap-2">
                          <Label>Bundle items</Label>
                          <Select value="none" onValueChange={addBundleItem}>
                            <SelectTrigger data-testid="webstore-product-bundle-select"><SelectValue placeholder="Add product to bundle" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">Choose product</SelectItem>
                              {(detail.data?.products || []).filter((item) => item.id !== productDraft.id && item.status !== "archived").map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}
                            </SelectContent>
                          </Select>
                          <div className="flex flex-wrap gap-2">
                            {(productDraft.bundle_items || []).map((item) => (
                              <Button key={item.product_id} type="button" size="sm" variant="outline" onClick={() => removeBundleItem(item.product_id)}>{item.name_snapshot || item.product_id} remove</Button>
                            ))}
                          </div>
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
                            <Button key={item.artwork_id} type="button" size="sm" variant="outline" onClick={() => removeAssociation("artwork_associations", "artwork_id", item.artwork_id)}>Associated artwork remove</Button>
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
                            <Button key={item.mockup_id} type="button" size="sm" variant="outline" onClick={() => removeAssociation("mockup_associations", "mockup_id", item.mockup_id)}>Associated mockup remove</Button>
                          ))}
                        </div>
                        <p className="text-xs text-muted-foreground">Mockups are read-only previews until approval is added later.</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button onClick={() => saveProduct.mutate()} disabled={saveProduct.isPending || !productDraft.name} data-testid="webstore-save-product"><Save className="size-4 mr-2" />Save Product</Button>
                      {productDraft.status === "archived" ? (
                        <Button variant="outline" onClick={() => restoreProduct.mutate(productDraft)}><RotateCcw className="size-4 mr-2" />Restore Draft</Button>
                      ) : (
                        <Button variant="outline" onClick={() => archiveProduct.mutate(productDraft)}><Archive className="size-4 mr-2" />Archive</Button>
                      )}
                    </div>
                    {selectedProduct?.template_provenance?.source_template_id && <div className="text-xs text-muted-foreground">Copied from a product template. This product is independent from later template changes.</div>}
                      </TabsContent>
                    </Tabs>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4" data-testid="webstore-product-resources">
            <Card>
              <CardHeader><CardTitle className="text-base">Product Templates</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="text-muted-foreground">Templates are reusable shop resources. Copy one into this Webstore from Product Plan, then edit the private product draft here.</div>
                <div className="flex flex-wrap gap-2">
                  <Button asChild variant="outline" size="sm"><Link to="/webstores">Manage Product Templates</Link></Button>
                  <Button type="button" variant="outline" size="sm" disabled>Create New Template Later</Button>
                </div>
                <div className="rounded border divide-y">
                  {(templates.data || []).slice(0, 5).map((template) => (
                    <div key={template.id} className="flex items-center justify-between gap-3 p-3">
                      <div>
                        <div className="font-medium">{template.template_name}</div>
                        <div className="text-xs text-muted-foreground">{template.scope === "platform" ? "Platform starter" : "Tenant template"} - {template.status || (template.active ? "active" : "archived")}</div>
                      </div>
                      {template.scope === "platform" && <Badge variant="outline">Starter</Badge>}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card data-testid="webstore-category-resources">
              <CardHeader><CardTitle className="text-base">Product Categories</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="text-muted-foreground">Categories can be selected for this Webstore's products. New category creation belongs in the shared category resource area.</div>
                <div className="flex flex-wrap gap-2">
                  <Button asChild variant="outline" size="sm"><Link to="/webstores">Manage Categories</Link></Button>
                  <Button type="button" variant="outline" size="sm" disabled>Create New Category Later</Button>
                </div>
                <div className="rounded border divide-y">
                  {(categories.data?.items || []).map((category) => (
                    <div key={category.id} className="p-3 space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <div><div className="font-medium">{category.name}</div><div className="text-xs text-muted-foreground">{category.status} - {category.product_count || 0} active products</div></div>
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
