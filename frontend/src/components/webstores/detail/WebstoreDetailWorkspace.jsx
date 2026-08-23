import { useMemo, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ProductFoundationTab from "./ProductFoundationTab";
import ProductPlanTab from "./ProductPlanTab";
import StorefrontReviewTabs from "./StorefrontReviewTabs";
import WebstoreActivityFeed from "./WebstoreActivityFeed";
import WebstoreDetailHeader from "./WebstoreDetailHeader";
import OverviewTab from "./OverviewTab";
import { useWebstoreDetailQueries } from "./useWebstoreDetailQueries";
import { useWebstoreLaunchWorkflow } from "./useWebstoreLaunchWorkflow";
import { useWebstoreProductWorkspace } from "./useWebstoreProductWorkspace";
import { useWebstoreSetupWorkflow } from "./useWebstoreSetupWorkflow";
import {
  formatActivityLabel,
  formatDateTime,
  formatLabel,
} from "./WebstoreDetailUtils";

export default function WebstoreDetailWorkspace() {
  const { id } = useParams();
  const location = useLocation();
  const [templateId, setTemplateId] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [advancedSetupOpen, setAdvancedSetupOpen] = useState(false);

  const queries = useWebstoreDetailQueries(id);
  const {
    activePacket,
    activity,
    assignments,
    detail,
    questionnaire,
    questionnaireResponse,
    readiness,
    setupFileItems,
    store,
    refresh,
  } = queries;

  const setupWorkflow = useWebstoreSetupWorkflow({
    id,
    initialQuestionnaireDelivery: location.state?.questionnaireDelivery,
    assignments,
    questionnaire,
    questionnaireResponse,
    refresh,
  });

  const productWorkspace = useWebstoreProductWorkspace({
    id,
    qc: queries.qc,
    detail,
    setupFileItems,
    templateId,
    setTemplateId,
    refresh,
  });

  const launchWorkflow = useWebstoreLaunchWorkflow({
    id,
    activePacket,
    store,
    readiness,
    refresh,
  });

  const activeProducts = productWorkspace.activeProducts;
  const startingProductIdeas = Array.isArray(store?.setup_profile?.starting_products)
    ? store.setup_profile.starting_products.filter((idea) =>
        String(idea || "").trim(),
      )
    : [];
  const selectedProductsCount = activeProducts.length;
  const uploadCount = setupFileItems.length;
  const nextRequiredAction = selectedProductsCount
    ? "Continue setup on selected draft products before launch preparation."
    : startingProductIdeas.length
      ? "Review your starting product ideas under Products."
      : "Add a custom product or copy one from a template.";

  const feedItems = useMemo(
    () =>
      [
        ...(launchWorkflow.paymentNeedsAttention
          ? [
              {
                id: "payment-readiness",
                action: "stripe_incomplete",
                summary: "Stripe/payment setup needs attention",
                created_at: store.updated_at || store.created_at,
                metadata: { detail: launchWorkflow.paymentNeedsAttention },
                synthetic: true,
              },
            ]
          : []),
        ...(activity.data?.items || []),
      ].slice(0, 8),
    [activity.data?.items, launchWorkflow.paymentNeedsAttention, store],
  );

  if (detail.isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading...</div>;
  }

  if (!store) {
    return <div className="p-6 text-sm text-rose-700">Webstore not found.</div>;
  }

  const questionnaireLink = setupWorkflow.questionnaireDelivery?.link
    ? new URL(
        setupWorkflow.questionnaireDelivery.link,
        window.location.origin,
      ).toString()
    : "";

  const model = {
    ...queries,
    ...setupWorkflow,
    ...productWorkspace,
    ...launchWorkflow,
    activeProducts,
    activeTab,
    advancedSetupOpen,
    feedItems,
    formatActivityLabel,
    formatDateTime,
    formatLabel,
    id,
    nextRequiredAction,
    questionnaireLink,
    selectedProductsCount,
    setActiveTab,
    setAdvancedSetupOpen,
    setTemplateId,
    startingProductIdeas,
    templateId,
    uploadCount,
  };

  return (
    <div className="space-y-4" data-testid="webstore-detail-page">
      <WebstoreDetailHeader model={model} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="space-y-4 min-w-0"
          data-testid="webstore-detail-tabs"
        >
          <TabsList className="flex h-auto flex-wrap justify-start gap-1 rounded-md border bg-slate-100 p-1">
            <TabsTrigger
              className="data-[state=active]:bg-sky-700 data-[state=active]:text-white data-[state=active]:shadow"
              value="overview"
            >
              Overview
            </TabsTrigger>
            <TabsTrigger
              className="data-[state=active]:bg-sky-700 data-[state=active]:text-white data-[state=active]:shadow"
              value="products"
            >
              Products
            </TabsTrigger>
            <TabsTrigger
              className="data-[state=active]:bg-sky-700 data-[state=active]:text-white data-[state=active]:shadow"
              value="storefront"
            >
              Storefront
            </TabsTrigger>
            <TabsTrigger
              className="data-[state=active]:bg-sky-700 data-[state=active]:text-white data-[state=active]:shadow"
              value="review-launch"
            >
              Review & Launch
            </TabsTrigger>
          </TabsList>
          <OverviewTab model={model} />
          <ProductPlanTab model={model} />
          <ProductFoundationTab model={model} />
          <StorefrontReviewTabs model={model} />
        </Tabs>
        <WebstoreActivityFeed model={model} />
      </div>
    </div>
  );
}
