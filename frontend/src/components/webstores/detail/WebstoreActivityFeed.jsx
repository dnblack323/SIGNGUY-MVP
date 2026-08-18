import {
  AlertCircle,
  Bell,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function WebstoreActivityFeed({ model }) {
  const { activity, detail, feedItems, formatActivityLabel, formatDateTime, id } = model;

return (
        <aside
          className="space-y-3 xl:sticky xl:top-4 xl:self-start"
          data-testid="webstore-builder-progress"
        >
          <Card className="border-amber-200">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Bell className="size-4 text-amber-700" />
                Webstores Feed
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {feedItems.map((item) => (
                <div
                  key={item.id}
                  className={`rounded-md border p-3 ${item.synthetic ? "border-amber-200 bg-amber-50" : "bg-white"}`}
                  data-testid={`webstore-feed-${item.id}`}
                >
                  <div className="flex items-start gap-2">
                    {item.synthetic ? (
                      <AlertCircle className="mt-0.5 size-4 shrink-0 text-amber-700" />
                    ) : (
                      <Bell className="mt-0.5 size-4 shrink-0 text-sky-700" />
                    )}
                    <div className="min-w-0">
                      <div className="font-medium capitalize">
                        {formatActivityLabel(item.action)}
                      </div>
                      <div className="mt-1 text-muted-foreground">
                        {item.summary}
                      </div>
                      {item.metadata?.detail && (
                        <div className="mt-1 text-xs text-amber-800">
                          {item.metadata.detail}
                        </div>
                      )}
                      <div className="mt-1 text-xs text-muted-foreground">
                        {formatDateTime(item.created_at)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {activity.isLoading && (
                <div className="text-muted-foreground">
                  Loading Webstores feed...
                </div>
              )}
              {!activity.isLoading && feedItems.length === 0 && (
                <div className="text-muted-foreground">
                  No Webstores activity yet.
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
  );
}
