import DecisionRoomReviewQueuePage from "@/pages/DecisionRoomReviewQueuePage";
import DecisionRoomsPage from "@/pages/DecisionRoomsPage";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useSearchParams } from "react-router-dom";

export default function ApprovalCenterPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") === "decision-rooms" ? "decision-rooms" : "approval-queue";
  return (
    <div className="space-y-4" data-testid="approval-center-page">
      <Tabs
        value={tab}
        onValueChange={(next) => setSearchParams(next === "decision-rooms" ? { tab: "decision-rooms" } : { tab: "queue" })}
        data-testid="approval-center-tabs"
      >
        <TabsList>
          <TabsTrigger value="approval-queue" data-testid="approval-center-tab-queue">Approval Queue</TabsTrigger>
          <TabsTrigger value="decision-rooms" data-testid="approval-center-tab-decision-rooms">Decision Rooms</TabsTrigger>
        </TabsList>
        <TabsContent value="approval-queue">
          <DecisionRoomReviewQueuePage />
        </TabsContent>
        <TabsContent value="decision-rooms">
          <DecisionRoomsPage />
        </TabsContent>
      </Tabs>
    </div>
  );
}
