import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import WorkspaceTimeline from "@/components/workspace/WorkspaceTimeline";
import WebstoreMessages from "@/components/webstores/WebstoreMessages";
import portalApi, { portalExtractError } from "@/portal/portalApi";
import {
  BrandingCard,
  SetupFilesCard,
} from "@/components/webstores/owner-portal/OwnerPortalFilesBranding";
import OwnerPortalLaunchPacket from "@/components/webstores/owner-portal/OwnerPortalLaunchPacket";
import OwnerPortalProducts from "@/components/webstores/owner-portal/OwnerPortalProducts";
import OwnerPortalQuestionnaire, { OwnerPortalWelcome } from "@/components/webstores/owner-portal/OwnerPortalQuestionnaire";
import {
  ChangeRequestHistoryCard,
  CommerceSummaryCard,
  SetupProgressCard,
  TermsCard,
} from "@/components/webstores/owner-portal/OwnerPortalSummarySections";
import { useWebstoreOwnerPortal } from "@/components/webstores/owner-portal/useWebstoreOwnerPortal";

const loadOwnerMessages = async (id) => (await portalApi.get(`/portal/webstores/${id}/messages`)).data;
const sendOwnerMessage = async (id, body) => (await portalApi.post(`/portal/webstores/${id}/messages`, { body })).data;

// Owner portal tabs (Phase 3, D3-5). Marketing stays hidden until Phase 8.
const OWNER_TABS = [
  { value: "overview", label: "Overview" },
  { value: "setup", label: "Store Setup" },
  { value: "orders", label: "Orders & Reports" },
  { value: "payments", label: "Payments & Payouts" },
  { value: "messages", label: "Messages & Files" },
];

export default function WebstoreOwnerPortalPage() {
  const portal = useWebstoreOwnerPortal();
  const { data, err, webstoreId } = portal;
  const [tab, setTab] = useState("overview");

  if (err)
    return (
      <div className="text-sm text-rose-700" data-testid="webstore-owner-error">
        {err}
      </div>
    );
  if (!data)
    return <div className="text-sm text-muted-foreground">Loading...</div>;

  const journey = data.journey || {};
  const nextStep = journey.next_action;
  const questionnaireNeeded = ["owner_complete_questionnaire", "owner_update_questionnaire", "questionnaire_complete"].includes(nextStep?.key);

  return (
    <div className="space-y-4" data-testid="webstore-owner-portal-page">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{data.webstore.name}</h1>
          <p className="text-sm text-muted-foreground">
            Review setup, products, and launch approval.
          </p>
        </div>
        {journey.stage && (
          <Badge variant="outline" data-testid="portal-webstore-stage">
            {journey.stage.label}
          </Badge>
        )}
      </div>
      <Tabs value={tab} onValueChange={setTab} className="space-y-4" data-testid="webstore-owner-portal-tabs">
        <TabsList className="flex h-auto flex-wrap justify-start gap-1 rounded-md border bg-slate-100 p-1">
          {OWNER_TABS.map((item) => (
            <TabsTrigger
              key={item.value}
              value={item.value}
              className="data-[state=active]:bg-sky-700 data-[state=active]:text-white data-[state=active]:shadow"
            >
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {nextStep?.key === "owner_complete_questionnaire" && <OwnerPortalWelcome welcome={portal.questionnaire?.welcome} />}
          <WorkspaceTimeline
            title="Your store"
            testId="portal-webstore-timeline"
            stages={journey.stage?.path || []}
            currentKey={journey.stage?.key}
            nextAction={
              nextStep && {
                heading: nextStep.for_you ? "Your next step" : "Nothing needed from you",
                text: nextStep.text,
              }
            }
            action={
              nextStep?.for_you ? (
                <Button size="sm" onClick={() => setTab("setup")} data-testid="portal-next-step-open">
                  Go to Store Setup
                </Button>
              ) : (
                <Button size="sm" variant="outline" onClick={() => setTab("messages")}>
                  Messages & Files
                </Button>
              )
            }
          />
          <SetupProgressCard data={data} progress={portal.progress} />
        </TabsContent>

        <TabsContent value="setup" className="space-y-4">
          {questionnaireNeeded && <OwnerPortalQuestionnaire
            questionnaire={portal.questionnaire}
            answers={portal.answers}
            onAnswersChange={portal.setAnswers}
            onSaveDraft={portal.saveDraft}
            onSubmit={portal.submitQuestionnaire}
            onFileSelected={portal.uploadQuestionFile}
            saveState={portal.saveState}
            submitting={portal.submitting}
          />}
          <BrandingCard webstoreId={webstoreId} products={data.products || []} />
          <OwnerPortalProducts
            products={data.products || []}
            productComments={portal.productComments}
            onProductCommentsChange={portal.setProductComments}
            onDecideProduct={portal.decideProduct}
            onDecideMockup={portal.decideMockup}
          />
          <OwnerPortalLaunchPacket
            data={data}
            packetComment={portal.packetComment}
            onPacketCommentChange={portal.setPacketComment}
            changeRequest={portal.changeRequest}
            onChangeRequestChange={portal.setChangeRequest}
            onApprove={portal.approve}
            onReject={portal.rejectPacket}
            onRequestChanges={portal.requestChanges}
          />
          <TermsCard data={data} onAcceptTerms={portal.acceptTerms} />
          <ChangeRequestHistoryCard requests={data.change_requests || []} />
        </TabsContent>

        <TabsContent value="orders" className="space-y-4">
          <CommerceSummaryCard summary={data.commerce_summary} />
        </TabsContent>

        <TabsContent value="payments" className="space-y-4">
          <Card data-testid="portal-payments-explainer">
            <CardHeader>
              <CardTitle className="text-base">Payments & Payouts</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                The shop runs checkout for your store and is the merchant for every order. Shoppers pay the shop directly.
              </p>
              <p>
                Any fundraising share or payout agreed with the shop is shown under Orders & Reports. You do not need to
                connect a payment account.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="messages" className="space-y-4">
          <WebstoreMessages
            webstoreId={webstoreId}
            viewer="owner"
            load={loadOwnerMessages}
            send={sendOwnerMessage}
            extractError={portalExtractError}
            intro="Questions or ideas for your store? Message the shop here."
          />
          <SetupFilesCard
            files={portal.files}
            fileCategory={portal.fileCategory}
            setupFile={portal.setupFile}
            onFileCategoryChange={portal.setFileCategory}
            onSetupFileChange={portal.setSetupFile}
            onUpload={portal.uploadSetupFile}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
