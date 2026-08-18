import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function OverviewStatusCard({ model }) {
  const { formatLabel, questionnaire, questionnaireSubmission, selectedProductsCount, store } = model;

return (
              <Card data-testid="webstore-overview-status">
                <CardHeader><CardTitle className="text-base">At a glance</CardTitle></CardHeader>
                <CardContent className="grid gap-3 text-sm sm:grid-cols-3">
                  <div><div className="text-xs font-medium uppercase text-muted-foreground">Owner questionnaire</div><div className="font-semibold">{questionnaireSubmission ? "Submitted" : "Waiting on owner"}</div></div>
                  <div><div className="text-xs font-medium uppercase text-muted-foreground">Workflow status</div><div className="font-semibold capitalize">{formatLabel(store.setup_state || store.status)}</div></div>
                  <div><div className="text-xs font-medium uppercase text-muted-foreground">Products</div><div className="font-semibold">{selectedProductsCount}</div></div>
                </CardContent>
              </Card>
  );
}
