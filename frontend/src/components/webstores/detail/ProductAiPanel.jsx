import { Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export default function ProductAiPanel({ model }) {
  const { previewProductAi, productAiPreview, productAiPrompt, productAiResult, runProductAi, setProductAiPrompt } = model;

return (
                      <div
                        className="rounded border bg-slate-50 p-3 text-sm"
                        data-testid="webstore-product-ai-panel"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2 font-medium">
                              <Sparkles className="size-4" />
                              AI drafts for this product
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              Outputs are saved for review only and are not applied to product fields or mockups.
                            </div>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={previewProductAi.isPending}
                              onClick={() => previewProductAi.mutate("product_description")}
                              data-testid="webstore-ai-preview-description"
                            >
                              Description cost
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={previewProductAi.isPending}
                              onClick={() => previewProductAi.mutate("product_mockup")}
                              data-testid="webstore-ai-preview-mockup"
                            >
                              Mockup cost
                            </Button>
                          </div>
                        </div>
                        {productAiPreview && (
                          <div className="mt-3 space-y-3" data-testid="webstore-ai-preview">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant="outline">{productAiPreview.label}</Badge>
                              <Badge variant={productAiPreview.insufficient_credits ? "destructive" : "secondary"} data-testid="webstore-ai-credit-display">
                                {productAiPreview.credit_display}
                              </Badge>
                              <span className="text-xs text-muted-foreground">
                                {productAiPreview.available_credits} credits available
                              </span>
                            </div>
                            <Textarea
                              rows={2}
                              value={productAiPrompt}
                              onChange={(e) => setProductAiPrompt(e.target.value)}
                              placeholder="Optional direction for this AI draft"
                              data-testid="webstore-ai-prompt"
                            />
                            <div className="flex flex-wrap items-center gap-2">
                              <Button
                                type="button"
                                size="sm"
                                disabled={runProductAi.isPending || productAiPreview.insufficient_credits}
                                onClick={() => runProductAi.mutate()}
                                data-testid="webstore-ai-run-confirmed"
                              >
                                Confirm and save draft
                              </Button>
                              <span className="text-xs text-muted-foreground">
                                Manual setup remains available.
                              </span>
                            </div>
                          </div>
                        )}
                        {productAiResult?.ai_result && (
                          <div className="mt-3 rounded border bg-white p-3" data-testid="webstore-ai-review-output">
                            <div className="text-xs font-medium uppercase text-muted-foreground">
                              Saved review output
                            </div>
                            <div className="mt-1 font-medium">
                              {productAiResult.ai_result.title}
                            </div>
                            <div className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
                              {productAiResult.ai_result.content_text}
                            </div>
                            <div className="mt-2 text-xs text-muted-foreground">
                              Record: {productAiResult.ai_result.record_type} - not applied automatically.
                            </div>
                          </div>
                        )}
                      </div>
  );
}
