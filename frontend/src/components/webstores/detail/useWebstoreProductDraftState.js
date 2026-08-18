import { useMemo, useState } from "react";
import {
  getProductSetupItems,
  productCatalogStatus,
} from "./WebstoreDetailUtils";

export function useWebstoreProductDraftState({ products, setupFileItems }) {
  const [productFilters, setProductFilters] = useState({
    status: "all",
    category_id: "all",
    q: "",
  });
  const [selectedProductId, setSelectedProductId] = useState("");
  const [productDraft, setProductDraft] = useState({});
  const [productError, setProductError] = useState("");
  const [productAiPreview, setProductAiPreview] = useState(null);
  const [productAiResult, setProductAiResult] = useState(null);
  const [productAiPrompt, setProductAiPrompt] = useState("");
  const [categoryEditDraft, setCategoryEditDraft] = useState({});
  const [editingCategoryId, setEditingCategoryId] = useState("");

  const filteredProducts = useMemo(() => {
    const q = productFilters.q.trim().toLowerCase();
    return products.filter((product) => {
      if (
        productFilters.status !== "all" &&
        productCatalogStatus(product) !== productFilters.status &&
        product.status !== productFilters.status
      )
        return false;
      if (
        productFilters.category_id !== "all" &&
        product.category_id !== productFilters.category_id
      )
        return false;
      if (
        q &&
        !String(product.name || "")
          .toLowerCase()
          .includes(q)
      )
        return false;
      return true;
    });
  }, [products, productFilters]);
  const selectedProduct = useMemo(
    () => products.find((product) => product.id === selectedProductId),
    [products, selectedProductId],
  );
  const activeProducts = products.filter(
    (product) => product.status !== "archived",
  );

  const resetProductAiState = () => {
    setProductAiPreview(null);
    setProductAiResult(null);
    setProductAiPrompt("");
  };

  const startProductSetup = (product) => {
    setSelectedProductId(product.id);
    setProductDraft(product);
    setProductError("");
    resetProductAiState();
  };

  const setProductField = (field, value) =>
    setProductDraft((draft) => ({ ...draft, [field]: value }));

  const setImageField = (slot, field, value) =>
    setProductDraft((draft) => ({
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

  const removeImageSlot = (slot) =>
    setProductDraft((draft) => {
      const next = { ...(draft.customer_images || {}) };
      delete next[slot];
      const images = Array.isArray(draft.images)
        ? draft.images.filter((image) => image?.slot !== slot)
        : draft.images;
      return { ...draft, customer_images: next, images };
    });

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
          url:
            file?.preview_url ||
            file?.url ||
            ((draft.customer_images || {})[slot] || {}).url,
        },
      },
    }));
  };

  const addAssociation = (field, key, value) => {
    if (!value || value === "none") return;
    setProductDraft((draft) => {
      const current = draft[field] || [];
      if (current.some((item) => item[key] === value)) return draft;
      return { ...draft, [field]: [...current, { [key]: value }] };
    });
  };

  const removeAssociation = (field, key, value) => {
    setProductDraft((draft) => ({
      ...draft,
      [field]: (draft[field] || []).filter((item) => item[key] !== value),
    }));
  };

  const addVariant = () =>
    setProductDraft((draft) => ({
      ...draft,
      variants: [
        ...(draft.variants || []),
        {
          id: `variant-${(draft.variants || []).length + 1}`,
          size: "",
          color: "",
          sku: "",
          selling_price_cents: draft.selling_price_cents || 0,
          status: "active",
          available: true,
        },
      ],
    }));

  const setVariantField = (index, field, value) =>
    setProductDraft((draft) => ({
      ...draft,
      variants: (draft.variants || []).map((variant, currentIndex) =>
        currentIndex === index ? { ...variant, [field]: value } : variant,
      ),
    }));

  const removeVariant = (index) =>
    setProductDraft((draft) => ({
      ...draft,
      variants: (draft.variants || []).filter(
        (_, currentIndex) => currentIndex !== index,
      ),
    }));

  const addPersonalizationField = () =>
    setProductDraft((draft) => ({
      ...draft,
      personalization_enabled: true,
      personalization_fields: [
        ...(draft.personalization_fields || []),
        {
          key: `field_${(draft.personalization_fields || []).length + 1}`,
          label: "",
          type: "text",
          required: false,
        },
      ],
    }));

  const setPersonalizationField = (index, field, value) =>
    setProductDraft((draft) => ({
      ...draft,
      personalization_fields: (draft.personalization_fields || []).map(
        (item, currentIndex) =>
          currentIndex === index ? { ...item, [field]: value } : item,
      ),
    }));

  const removePersonalizationField = (index) =>
    setProductDraft((draft) => ({
      ...draft,
      personalization_fields: (draft.personalization_fields || []).filter(
        (_, currentIndex) => currentIndex !== index,
      ),
    }));

  const addBundleItem = (productId) => {
    if (!productId || productId === "none") return;
    const bundled = products.find((item) => item.id === productId);
    setProductDraft((draft) => {
      if (
        (draft.bundle_items || []).some((item) => item.product_id === productId)
      )
        return draft;
      return {
        ...draft,
        bundle_items: [
          ...(draft.bundle_items || []),
          {
            product_id: productId,
            name_snapshot: bundled?.name,
            quantity: 1,
            sku_snapshot: bundled?.sku,
          },
        ],
      };
    });
  };

  const removeBundleItem = (productId) =>
    setProductDraft((draft) => ({
      ...draft,
      bundle_items: (draft.bundle_items || []).filter(
        (item) => item.product_id !== productId,
      ),
    }));

  return {
    activeProducts,
    addAssociation,
    addBundleItem,
    addPersonalizationField,
    addVariant,
    categoryEditDraft,
    editingCategoryId,
    filteredProducts,
    getProductSetupItems,
    productAiPreview,
    productAiPrompt,
    productAiResult,
    productDraft,
    productError,
    productFilters,
    removeAssociation,
    removeBundleItem,
    removeImageSlot,
    removePersonalizationField,
    removeVariant,
    resetProductAiState,
    selectedProduct,
    selectedProductId,
    setCategoryEditDraft,
    setEditingCategoryId,
    setImageField,
    setImageFile,
    setPersonalizationField,
    setProductAiPreview,
    setProductAiPrompt,
    setProductAiResult,
    setProductDraft,
    setProductError,
    setProductField,
    setProductFilters,
    setSelectedProductId,
    setVariantField,
    startProductSetup,
  };
}
