import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function OverviewSetupProgressCard({ model }) {
  const { setupProgress, store } = model;

return (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Setup Progress</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <Badge variant="outline" data-testid="webstore-setup-state">
                    {setupProgress.data?.setup_state ||
                      store.setup_state ||
                      "not_started"}
                  </Badge>
                  {(setupProgress.data?.steps || []).map((step) => (
                    <div
                      key={step.key}
                      className="flex items-center justify-between gap-3"
                    >
                      <span>{step.label}</span>
                      <Badge
                        variant={
                          step.status === "complete" ? "secondary" : "outline"
                        }
                      >
                        {step.status}
                      </Badge>
                    </div>
                  ))}
                </CardContent>
              </Card>
  );
}
