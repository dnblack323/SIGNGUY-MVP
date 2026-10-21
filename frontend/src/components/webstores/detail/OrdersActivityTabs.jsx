import { TabsContent } from "@/components/ui/tabs";
import WebstoreMessages from "@/components/webstores/WebstoreMessages";
import { extractError } from "@/lib/api";
import { listWebstoreMessages, sendWebstoreMessage } from "@/lib/webstores";
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
        <WebstoreMessages
          webstoreId={model.id}
          viewer="shop"
          load={listWebstoreMessages}
          send={sendWebstoreMessage}
          extractError={extractError}
          intro="Everything here is shared with the store owner. Keep staff-only notes out of this thread."
          onSent={() => model.activity.refetch()}
        />
        <WebstoreActivityFeed model={model} />
      </TabsContent>
    </>
  );
}
