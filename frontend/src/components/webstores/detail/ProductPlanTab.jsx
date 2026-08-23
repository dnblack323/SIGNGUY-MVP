import {
  PackagePlus,
  Sparkles,
} from "lucide-react";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TabsContent } from "@/components/ui/tabs";

export default function ProductPlanTab({ model }) {
  const {
    activeProducts,
    addProduct,
    createBlankProduct,
    formatLabel,
    id,
    questionnaire,
    questionnaireAnswers,
    questionnaireAnswerRows,
    questionnaireSubmission,
    setTemplateId,
    startingProductIdeas,
    templateId,
    templates,
    uploadCount,
  } = model;

return (
          <TabsContent
            value="products"
            className="space-y-4"
            data-testid="webstore-product-plan"
          >
            {startingProductIdeas.length > 0 && (
              <Card data-testid="webstore-starting-product-ideas" className="border-sky-200 bg-sky-50/40">
                <CardHeader><CardTitle className="text-base">Starting Product Ideas</CardTitle></CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p className="text-muted-foreground">These are ideas recorded during setup. They are not configured products yet, so start a draft when you are ready.</p>
                  {startingProductIdeas.map((idea) => {
                    const name = String(idea).trim();
                    const draft = activeProducts.find((product) => String(product.name || "").trim().toLowerCase() === name.toLowerCase());
                    return <div key={name} className="flex flex-wrap items-center justify-between gap-3 rounded border bg-white p-3" data-testid={`webstore-starting-product-idea-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}><div><div className="font-medium">{name}</div><div className="text-xs text-muted-foreground">{draft ? "Draft product created - continue configuration below." : "Idea only - not yet a configured product."}</div></div><Button type="button" size="sm" variant={draft ? "outline" : "default"} disabled={Boolean(draft) || createBlankProduct.isPending} onClick={() => createBlankProduct.mutate(name)}>{draft ? "Draft Created" : "Start Product"}</Button></div>;
                  })}
                </CardContent>
              </Card>
            )}
            <div className="grid grid-cols-1 xl:grid-cols-[1fr_1.1fr] gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    Questionnaire Summary
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <div className="text-xs font-medium uppercase text-muted-foreground">
                        Status
                      </div>
                      <div className="font-semibold">
                        {questionnaireSubmission
                          ? "Submitted"
                          : "Waiting on owner"}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs font-medium uppercase text-muted-foreground">
                        Uploaded logo/artwork
                      </div>
                      <div className="font-semibold">{uploadCount}</div>
                    </div>
                    <div>
                      <div className="text-xs font-medium uppercase text-muted-foreground">
                        Purpose
                      </div>
                      <div className="font-semibold">
                        {questionnaireAnswers.purpose ||
                          questionnaireAnswers.store_purpose ||
                          "Not answered"}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs font-medium uppercase text-muted-foreground">
                        Audience
                      </div>
                      <div className="font-semibold">
                        {questionnaireAnswers.audience ||
                          questionnaireAnswers.target_audience ||
                          "Not answered"}
                      </div>
                    </div>
                  </div>
                  <div className="rounded-md border">
                    {questionnaireAnswerRows.length ? (
                      questionnaireAnswerRows.map(([key, value]) => (
                        <div
                          key={key}
                          className="grid gap-1 border-b p-3 last:border-b-0 md:grid-cols-[180px_1fr]"
                        >
                          <div className="font-medium capitalize">
                            {formatLabel(key)}
                          </div>
                          <div className="text-muted-foreground">
                            {Array.isArray(value)
                              ? value.join(", ")
                              : String(value)}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="p-3 text-muted-foreground">
                        The owner questionnaire has not produced reviewable
                        answers yet.
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!questionnaireSubmission}
                    >
                      View Full Questionnaire
                    </Button>
                    <Button type="button" variant="outline" disabled>
                      Request Missing Information
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Sparkles className="size-4" />
                    AI Product Suggestions
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Alert>
                    <AlertTitle>No generated suggestions yet</AlertTitle>
                    <AlertDescription>
                      AI product recommendations, mockups, pricing suggestions,
                      owner-share estimates, and regeneration actions are
                      planned for a later Webstores stage and are not active
                      here.
                    </AlertDescription>
                  </Alert>
                  <div className="rounded-md border bg-slate-50 p-4 text-sm text-muted-foreground">
                    Suggestions will appear here as selectable product cards
                    after the AI product-planning workflow is implemented.
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" variant="outline" disabled>
                      Include Product
                    </Button>
                    <Button type="button" variant="outline" disabled>
                      Skip
                    </Button>
                    <Button type="button" variant="outline" disabled>
                      Edit Suggestion
                    </Button>
                    <Button type="button" variant="outline" disabled>
                      Regenerate Description
                    </Button>
                    <Button type="button" variant="outline" disabled>
                      Request Different Mockup
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Add Another Product</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
                <Select value={templateId} onValueChange={setTemplateId}>
                  <SelectTrigger data-testid="webstore-stage4-template-select">
                    <SelectValue placeholder="Add from template" />
                  </SelectTrigger>
                  <SelectContent>
                    {(templates.data || [])
                      .filter((t) => t.status !== "archived")
                      .map((t) => (
                        <SelectItem value={t.id} key={t.id}>
                          {t.template_name}
                          {t.scope === "platform" ? " (starter)" : ""}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
                <Button
                  disabled={!templateId || addProduct.isPending}
                  onClick={() => addProduct.mutate()}
                  data-testid="webstore-add-template-draft"
                >
                  <PackagePlus className="size-4 mr-2" />
                  Add From Template
                </Button>
                <Button
                  variant="outline"
                  onClick={() => createBlankProduct.mutate()}
                  disabled={createBlankProduct.isPending}
                  data-testid="webstore-create-blank-product"
                >
                  <PackagePlus className="size-4 mr-2" />
                  Create Custom Product
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled
                  className="lg:col-start-3"
                >
                  Ask AI for Another Suggestion
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
  );
}
