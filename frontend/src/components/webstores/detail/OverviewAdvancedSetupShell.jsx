import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function OverviewAdvancedSetupShell({ model }) {
  const { advancedSetupOpen, setActiveTab, setAdvancedSetupOpen } = model;

  return (
    <Card data-testid="webstore-advanced-setup-shell">
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="link"
            className="h-auto p-0 text-sm"
            onClick={() => setAdvancedSetupOpen((open) => !open)}
            data-testid="webstore-advanced-setup-toggle"
          >
            {advancedSetupOpen ? "Hide Advanced Setup" : "Advanced Setup"}
          </Button>
          <span className="text-xs text-muted-foreground">
            Detailed settings, permissions, lifecycle history, and questionnaire
            controls remain available when you need them.
          </span>
        </div>
        {advancedSetupOpen && (
          <div
            className="grid gap-2 rounded-md border bg-white p-3 text-sm sm:grid-cols-3"
            data-testid="webstore-advanced-setup"
          >
            <Button
              type="button"
              variant="outline"
              onClick={() => setActiveTab("products")}
            >
              Product details
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setActiveTab("storefront")}
            >
              Store settings and branding
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setActiveTab("review-launch")}
            >
              Preview and approval
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
