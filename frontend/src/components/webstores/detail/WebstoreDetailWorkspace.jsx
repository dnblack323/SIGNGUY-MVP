import { useMemo, useState } from "react";
import InformationPacketDialog from "./InformationPacketDialog";
import QuestionnaireReviewDialog from "./QuestionnaireReviewDialog";
import { useParams } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ProductFoundationTab from "./ProductFoundationTab";
import ProductPlanTab from "./ProductPlanTab";
import OrdersActivityTabs from "./OrdersActivityTabs";
import SetupTab from "./SetupTab";
import StorefrontReviewTabs from "./StorefrontReviewTabs";
import WebstoreDetailHeader from "./WebstoreDetailHeader";
import { STAFF_TABS } from "./WebstoreNextAction";
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
  const [templateId, setTemplateId] = useState("");
  const [activeTab, setActiveTab] = useState("overview");

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
    assignments,
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
  // Stage and next action come from the backend read model (Phase 3); no frontend copy.
  const stage = detail.data?.stage;
  const nextAction = detail.data?.next_action;

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

  const model = {
    ...queries,
    ...setupWorkflow,
    ...productWorkspace,
    ...launchWorkflow,
    activeProducts,
    activeTab,
    feedItems,
    formatActivityLabel,
    formatDateTime,
    formatLabel,
    id,
    nextAction,
    selectedProductsCount,
    setActiveTab,
    stage,
    setTemplateId,
    startingProductIdeas,
    templateId,
    uploadCount,
  };

  return (
    <div className="space-y-4" data-testid="webstore-detail-page">
      <WebstoreDetailHeader model={model} />
      <InformationPacketDialog webstoreId={id} open={model.packetOpen} onOpenChange={model.setPacketOpen} onSent={refresh} />
      <QuestionnaireReviewDialog webstoreId={id} open={model.reviewOpen} onOpenChange={model.setReviewOpen} onChanged={refresh} />
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4 min-w-0" data-testid="webstore-detail-tabs">
        <TabsList className="flex h-auto flex-wrap justify-start gap-1 rounded-md border bg-slate-100 p-1">
          {STAFF_TABS.map((tab) => (
            <TabsTrigger
              key={tab.value}
              className="data-[state=active]:bg-sky-700 data-[state=active]:text-white data-[state=active]:shadow"
              value={tab.value}
            >
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <OverviewTab model={model} />
        <SetupTab model={model} />
        <ProductPlanTab model={model} />
        <ProductFoundationTab model={model} />
        <StorefrontReviewTabs model={model} />
        <OrdersActivityTabs model={model} />
      </Tabs>
    </div>
  );
}
