import { Badge } from "@/components/ui/badge";
import {
  BrandingCard,
  SetupFilesCard,
} from "@/components/webstores/owner-portal/OwnerPortalFilesBranding";
import OwnerPortalLaunchPacket from "@/components/webstores/owner-portal/OwnerPortalLaunchPacket";
import OwnerPortalProducts from "@/components/webstores/owner-portal/OwnerPortalProducts";
import OwnerPortalQuestionnaire from "@/components/webstores/owner-portal/OwnerPortalQuestionnaire";
import {
  ChangeRequestHistoryCard,
  CommerceSummaryCard,
  SetupProgressCard,
  TermsCard,
} from "@/components/webstores/owner-portal/OwnerPortalSummarySections";
import { useWebstoreOwnerPortal } from "@/components/webstores/owner-portal/useWebstoreOwnerPortal";

export default function WebstoreOwnerPortalPage() {
  const portal = useWebstoreOwnerPortal();
  const { data, err, webstoreId } = portal;

  if (err)
    return (
      <div className="text-sm text-rose-700" data-testid="webstore-owner-error">
        {err}
      </div>
    );
  if (!data)
    return <div className="text-sm text-muted-foreground">Loading...</div>;

  return (
    <div className="space-y-4" data-testid="webstore-owner-portal-page">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{data.webstore.name}</h1>
          <p className="text-sm text-muted-foreground">
            Review setup, products, and launch approval.
          </p>
        </div>
        <Badge variant="outline" className="capitalize">
          {String(data.webstore.status).replace(/_/g, " ")}
        </Badge>
      </div>
      <SetupProgressCard data={data} progress={portal.progress} />
      <CommerceSummaryCard summary={data.commerce_summary} />
      <OwnerPortalQuestionnaire
        questionnaire={portal.questionnaire}
        answers={portal.answers}
        onAnswersChange={portal.setAnswers}
        onSaveDraft={portal.saveDraft}
        onSubmit={portal.submitQuestionnaire}
      />
      <SetupFilesCard
        files={portal.files}
        fileCategory={portal.fileCategory}
        setupFile={portal.setupFile}
        onFileCategoryChange={portal.setFileCategory}
        onSetupFileChange={portal.setSetupFile}
        onUpload={portal.uploadSetupFile}
      />
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
    </div>
  );
}
