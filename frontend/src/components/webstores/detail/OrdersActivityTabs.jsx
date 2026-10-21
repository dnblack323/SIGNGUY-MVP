import { TabsContent } from "@/components/ui/tabs";
import OverviewOrdersPanel from "./OverviewOrdersPanel";
import OverviewReportingCard from "./OverviewReportingCard";
import WebstoreActivityFeed from "./WebstoreActivityFeed";

export default function OrdersActivityTabs({ model }) {
  return (
    <>
      <TabsContent value="orders" className="space-y-4">
        <OverviewReportingCard model={model} />
        <OverviewOrdersPanel model={model} />
      </TabsContent>
      <TabsContent value="activity" className="space-y-4">
        <WebstoreActivityFeed model={model} />
      </TabsContent>
    </>
  );
}
