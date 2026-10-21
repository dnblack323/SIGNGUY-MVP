import { TabsContent } from "@/components/ui/tabs";
import OverviewAssignmentsCard from "./OverviewAssignmentsCard";
import OverviewQuestionnaireCard from "./OverviewQuestionnaireCard";
import OverviewSetupFilesCard from "./OverviewSetupFilesCard";
import OverviewSetupProgressCard from "./OverviewSetupProgressCard";

// Setup (D3-4): request, information packet, owner access, questionnaire review and files.
export default function SetupTab({ model }) {
  return (
    <TabsContent value="setup" className="space-y-4" data-testid="webstore-setup-tab">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <OverviewSetupProgressCard model={model} />
        <OverviewAssignmentsCard model={model} />
        <OverviewSetupFilesCard model={model} />
      </div>
      <OverviewQuestionnaireCard model={model} />
    </TabsContent>
  );
}
