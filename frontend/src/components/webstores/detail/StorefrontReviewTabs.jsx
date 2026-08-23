import { Send } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { TabsContent } from "@/components/ui/tabs";
import WebstoreBrandingEditor from "@/components/webstores/WebstoreBranding";
import { centsToDollarsString } from "@/lib/format";

export default function StorefrontReviewTabs({ model }) {
  const {
    assignments,
    detail,
    formatDateTime,
    formatLabel,
    id,
    launch,
    startProductSetup,
    submitProductApproval,
  } = model;

return <>
          <TabsContent value="storefront" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Storefront Setup</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Store information, owner assignments, setup files, and type-specific settings remain available from Overview. Use Advanced Setup there when you need the detailed controls.
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="storefront" className="space-y-4">
            <WebstoreBrandingEditor
              webstoreId={id}
              products={detail.data?.products || []}
            />
          </TabsContent>

          <TabsContent value="review-launch" className="space-y-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Storefront Preview</CardTitle></CardHeader>
              <CardContent className="text-sm text-muted-foreground">Review the customer-facing appearance before requesting approval. Changes remain drafts until they are reviewed and published.</CardContent>
            </Card>
            <WebstoreBrandingEditor
              webstoreId={id}
              products={detail.data?.products || []}
            />
          </TabsContent>

          <TabsContent value="review-launch" className="space-y-4">
            <Card data-testid="webstore-product-approval-panel">
              <CardHeader>
                <CardTitle className="text-base">
                  Product and Mockup Approval
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {(detail.data?.products || []).map((product) => (
                  <div
                    key={product.id}
                    className="rounded-md border p-3"
                    data-testid={`webstore-product-approval-${product.id}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="font-medium">{product.name}</div>
                        <div className="text-xs text-muted-foreground">
                          Revision {product.revision || 1} -{" "}
                          {centsToDollarsString(product.selling_price_cents)}
                        </div>
                      </div>
                      <Badge
                        variant={
                          product.approval_status === "approved"
                            ? "secondary"
                            : "outline"
                        }
                      >
                        {formatLabel(product.approval_status || "not_submitted")}
                      </Badge>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={
                          submitProductApproval.isPending ||
                          product.status === "archived"
                        }
                        onClick={() => submitProductApproval.mutate(product)}
                      >
                        Send Product Approval
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => startProductSetup(product)}
                      >
                        Edit Product
                      </Button>
                    </div>
                    {(product.approval_history || []).length > 0 && (
                      <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                        {product.approval_history.map((entry) => (
                          <div key={entry.id}>
                            {formatLabel(entry.action)} by{" "}
                            {entry.actor_display || entry.actor_ref} on{" "}
                            {formatDateTime(entry.created_at)}
                            {entry.reason ? ` - ${entry.reason}` : ""}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {(detail.data?.products || []).length === 0 && (
                  <div className="text-muted-foreground">
                    Add products before requesting product approval.
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
  </>;
}
