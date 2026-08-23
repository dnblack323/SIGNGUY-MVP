import { useMutation, useQuery } from "@tanstack/react-query";
import { extractError } from "@/lib/api";
import {
  archiveWebstoreProduct,
  archiveWebstoreProductCategory,
  createProductFromTemplate,
  duplicateWebstoreProduct,
  listWebstoreArtwork,
  listWebstoreMockups,
  previewWebstoreProductAiAction,
  reorderWebstoreProducts,
  restoreWebstoreProduct,
  restoreWebstoreProductCategory,
  runWebstoreProductAiAction,
  submitWebstoreMockupApproval,
  submitWebstoreProductApproval,
  updateWebstoreProduct,
  updateWebstoreProductCategory,
} from "@/lib/webstores";
import { toast } from "sonner";
import { productImagesForSave, toIntCents } from "./WebstoreDetailUtils";
import { useWebstoreProductDraftState } from "./useWebstoreProductDraftState";

export function useWebstoreProductWorkspace({
  id,
  qc,
  detail,
  setupFileItems,
  templateId,
  setTemplateId,
  refresh,
}) {
  const products = detail.data?.products || [];
  const draftState = useWebstoreProductDraftState({ products, setupFileItems });
  const {
    categoryEditDraft,
    editingCategoryId,
    productAiPreview,
    productAiPrompt,
    productDraft,
    resetProductAiState,
    setEditingCategoryId,
    setCategoryEditDraft,
    setProductAiPreview,
    setProductAiResult,
    setProductDraft,
    setProductError,
    setProductAiPrompt,
    setSelectedProductId,
  } = draftState;

  const artworkOptions = useQuery({
    queryKey: ["webstore-artwork", id, draftState.selectedProductId],
    queryFn: () =>
      listWebstoreArtwork(
        id,
        draftState.selectedProductId
          ? { product_id: draftState.selectedProductId }
          : {},
      ),
    enabled: !!id,
  });
  const mockupOptions = useQuery({
    queryKey: ["webstore-mockups", id, draftState.selectedProductId],
    queryFn: () =>
      listWebstoreMockups(
        id,
        draftState.selectedProductId
          ? { product_id: draftState.selectedProductId }
          : {},
      ),
    enabled: !!id,
  });

  const createBlankProduct = useMutation({
    mutationFn: (productName = "New draft product") =>
      createProductFromTemplate(id, {
        name: productName,
        product_type: "general",
      }),
    onSuccess: async (product) => {
      toast.success("Draft product created");
      setSelectedProductId(product.id);
      setProductDraft(product);
      resetProductAiState();
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const addProduct = useMutation({
    mutationFn: () =>
      createProductFromTemplate(id, {
        source_template_id: templateId,
        idempotency_key: `template-${templateId}-${Date.now()}`,
      }),
    onSuccess: async (product) => {
      toast.success("Template copied into a private draft");
      setTemplateId("");
      setSelectedProductId(product.id);
      setProductDraft(product);
      resetProductAiState();
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const saveProduct = useMutation({
    mutationFn: () =>
      updateWebstoreProduct(id, productDraft.id, {
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
        store_owner_share_cents: toIntCents(
          productDraft.store_owner_share_cents,
        ),
        fundraiser_share_cents: toIntCents(productDraft.fundraiser_share_cents),
        platform_fee_basis_points: toIntCents(
          productDraft.platform_fee_basis_points ?? 0,
        ),
        variants: productDraft.variants || [],
        personalization_enabled: Boolean(productDraft.personalization_enabled),
        personalization_fields: productDraft.personalization_fields || [],
        bundle_items: productDraft.bundle_items || [],
        inventory_policy: productDraft.inventory_policy || "not_tracked",
        inventory_quantity:
          productDraft.inventory_quantity === "" ||
          productDraft.inventory_quantity == null
            ? undefined
            : toIntCents(productDraft.inventory_quantity),
        display_order: toIntCents(productDraft.display_order ?? 0),
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
    onSuccess: async (product) => {
      toast.success("Product draft saved");
      setProductError("");
      setProductDraft(product);
      await refresh();
    },
    onError: (err) => {
      const message = extractError(err);
      setProductError(message);
      toast.error(message);
    },
  });

  const archiveProduct = useMutation({
    mutationFn: (product) =>
      archiveWebstoreProduct(id, product.id, {
        expected_revision: product.revision,
      }),
    onSuccess: async (product) => {
      toast.success("Product archived");
      setProductError("");
      setProductDraft(product);
      await refresh();
    },
    onError: (err) => {
      const message = extractError(err);
      setProductError(message);
      toast.error(message);
    },
  });

  const restoreProduct = useMutation({
    mutationFn: (product) =>
      restoreWebstoreProduct(id, product.id, {
        expected_revision: product.revision,
      }),
    onSuccess: async (product) => {
      toast.success("Product restored to draft");
      setProductError("");
      setProductDraft(product);
      await refresh();
    },
    onError: (err) => {
      const message = extractError(err);
      setProductError(message);
      toast.error(message);
    },
  });

  const duplicateProduct = useMutation({
    mutationFn: (product) =>
      duplicateWebstoreProduct(id, product.id, {
        expected_revision: product.revision,
      }),
    onSuccess: async (product) => {
      toast.success("Product duplicated");
      setSelectedProductId(product.id);
      setProductDraft(product);
      resetProductAiState();
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const reorderProducts = useMutation({
    mutationFn: (productIds) => reorderWebstoreProducts(id, productIds),
    onSuccess: async () => {
      toast.success("Product order updated");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const submitProductApproval = useMutation({
    mutationFn: (product) =>
      submitWebstoreProductApproval(id, product.id, {
        expected_revision: product.revision,
      }),
    onSuccess: async (product) => {
      toast.success("Product sent for owner approval");
      setProductDraft(product);
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const submitMockupApproval = useMutation({
    mutationFn: (mockupId) => submitWebstoreMockupApproval(id, mockupId),
    onSuccess: async () => {
      toast.success("Mockup sent for owner approval");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const previewProductAi = useMutation({
    mutationFn: (action) =>
      previewWebstoreProductAiAction(id, productDraft.id, { action }),
    onSuccess: (preview) => {
      setProductAiPreview(preview);
      setProductAiResult(null);
      toast.success(`AI credit preview ready: ${preview.credit_display}`);
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const runProductAi = useMutation({
    mutationFn: () =>
      runWebstoreProductAiAction(id, productDraft.id, {
        action: productAiPreview.action,
        confirmed_credit_charge_credits:
          productAiPreview.credit_charge_credits,
        prompt: productAiPrompt || undefined,
        idempotency_key: `webstore-ai-${productDraft.id}-${productAiPreview.action}-${Date.now()}`,
      }),
    onSuccess: async (result) => {
      setProductAiResult(result);
      toast.success("AI output saved for review");
      await qc.invalidateQueries({ queryKey: ["webstore-activity", id] });
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const saveCategory = useMutation({
    mutationFn: () =>
      updateWebstoreProductCategory(id, editingCategoryId, {
        ...categoryEditDraft,
        expected_revision: categoryEditDraft.revision,
      }),
    onSuccess: async () => {
      toast.success("Category updated");
      setEditingCategoryId("");
      setCategoryEditDraft({});
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const archiveCategory = useMutation({
    mutationFn: (category) =>
      archiveWebstoreProductCategory(id, category.id, {
        expected_revision: category.revision,
      }),
    onSuccess: refresh,
    onError: (err) => toast.error(extractError(err)),
  });

  const restoreCategory = useMutation({
    mutationFn: (category) =>
      restoreWebstoreProductCategory(id, category.id, {
        expected_revision: category.revision,
      }),
    onSuccess: refresh,
    onError: (err) => toast.error(extractError(err)),
  });

  return {
    ...draftState,
    addProduct,
    archiveCategory,
    archiveProduct,
    artworkOptions,
    createBlankProduct,
    duplicateProduct,
    mockupOptions,
    previewProductAi,
    reorderProducts,
    restoreCategory,
    restoreProduct,
    runProductAi,
    saveCategory,
    saveProduct,
    submitMockupApproval,
    submitProductApproval,
  };
}
