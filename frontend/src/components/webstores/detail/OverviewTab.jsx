import { TabsContent } from "@/components/ui/tabs";
import GuidedSetupModule from "@/components/webstores/GuidedSetupModule";
import OverviewAdvancedSetupShell from "./OverviewAdvancedSetupShell";
import OverviewAssignmentsCard from "./OverviewAssignmentsCard";
import OverviewLaunchGatesCard from "./OverviewLaunchGatesCard";
import OverviewLaunchPacketCard from "./OverviewLaunchPacketCard";
import OverviewOrdersPanel from "./OverviewOrdersPanel";
import OverviewProductsSummaryCard from "./OverviewProductsSummaryCard";
import OverviewQuestionnaireCard from "./OverviewQuestionnaireCard";
import OverviewReportingCard from "./OverviewReportingCard";
import OverviewSetupFilesCard from "./OverviewSetupFilesCard";
import OverviewSetupProgressCard from "./OverviewSetupProgressCard";
import OverviewStatusCard from "./OverviewStatusCard";

export default function OverviewTab({ model }) {
  const {
    activePacket,
    activeProducts,
    advancedSetupOpen,
    detail,
    launch,
    packet,
    questionnaireSubmission,
    readiness,
    sendPacket,
    sendQuestionnaire,
    setActiveTab,
    setupFileItems,
    store,
  } = model;

  return (
    <TabsContent value="overview" className="space-y-4">
      <GuidedSetupModule
        store={store}
        questionnaireSubmission={questionnaireSubmission}
        activeProducts={activeProducts}
        activePacket={activePacket}
        setupFiles={setupFileItems}
        branding={detail.data?.branding}
        readiness={readiness.data}
        onShowTab={setActiveTab}
        onSendQuestionnaire={() => sendQuestionnaire.mutate()}
        onGeneratePacket={() => packet.mutate()}
        onSendPacket={() => sendPacket.mutate()}
        onLaunch={() => launch.mutate()}
        sendingQuestionnaire={sendQuestionnaire.isPending}
        generatingPacket={packet.isPending}
        sendingPacket={sendPacket.isPending}
        launching={launch.isPending}
      />
      <OverviewAdvancedSetupShell model={model} />
      {advancedSetupOpen ? (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <OverviewSetupProgressCard model={model} />
            <OverviewAssignmentsCard model={model} />
            <OverviewSetupFilesCard model={model} />
          </div>
          <OverviewQuestionnaireCard model={model} />
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <OverviewLaunchGatesCard model={model} />
            <OverviewProductsSummaryCard model={model} />
            <OverviewLaunchPacketCard model={model} />
          </div>
          <OverviewReportingCard model={model} />
        </>
      ) : (
        <OverviewStatusCard model={model} />
      )}
      <OverviewOrdersPanel model={model} />
    </TabsContent>
  );
}
