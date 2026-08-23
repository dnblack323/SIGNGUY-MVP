import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { centsToDollarsString } from "@/lib/format";

export default function OwnerPortalProducts({
  products,
  productComments,
  onProductCommentsChange,
  onDecideProduct,
  onDecideMockup,
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Products</CardTitle>
      </CardHeader>
      <CardContent className="rounded border divide-y p-0">
        {(products || []).map((p) => (
          <div
            key={p.id}
            className="p-3 grid gap-3 md:grid-cols-[96px_1fr_auto] text-sm"
          >
            <div className="aspect-square overflow-hidden rounded border bg-slate-50">
              {p.images?.[0]?.url ? (
                <img
                  src={p.images[0].url}
                  alt={p.images[0].alt_text || p.name}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                  No image
                </div>
              )}
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="font-medium">{p.name}</div>
                <Badge
                  variant={
                    p.approval_status === "approved" ? "secondary" : "outline"
                  }
                >
                  {String(p.approval_status || "not_submitted").replace(
                    /_/g,
                    " ",
                  )}
                </Badge>
              </div>
              <div className="text-xs text-muted-foreground">
                {p.description || p.product_type}
              </div>
              {(p.mockups || []).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {p.mockups.map((mockup) => (
                    <div key={mockup.id} className="flex items-center gap-1">
                      <Badge variant="outline">
                        {mockup.alt_text || mockup.purpose || "Mockup"}
                      </Badge>
                      {mockup.approval_status === "pending_owner_approval" && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              onDecideMockup(mockup.id, "approve", p.id)
                            }
                          >
                            Approve Mockup
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              onDecideMockup(mockup.id, "request_changes", p.id)
                            }
                          >
                            Request Changes
                          </Button>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {p.approval_status === "pending_owner_approval" && (
                <div className="mt-3 space-y-2">
                  <Textarea
                    rows={2}
                    value={productComments[p.id] || ""}
                    onChange={(e) =>
                      onProductCommentsChange({
                        ...productComments,
                        [p.id]: e.target.value,
                      })
                    }
                    placeholder="Optional approval note, or required reason for changes."
                    data-testid={`portal-product-approval-comment-${p.id}`}
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      onClick={() => onDecideProduct(p.id, "approve")}
                      data-testid={`portal-product-approve-${p.id}`}
                    >
                      Approve Product
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onDecideProduct(p.id, "request_changes")}
                    >
                      Request Changes
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onDecideProduct(p.id, "reject")}
                    >
                      Reject
                    </Button>
                  </div>
                </div>
              )}
              {(p.approval_history || []).length > 0 && (
                <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                  {p.approval_history.map((entry) => (
                    <div key={entry.id}>
                      {String(entry.action).replace(/_/g, " ")} -{" "}
                      {entry.reason || "No comment"}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <span className="font-medium">
              {centsToDollarsString(p.selling_price_cents)}
            </span>
          </div>
        ))}
        {(products || []).length === 0 && (
          <div className="p-3 text-sm text-muted-foreground">
            No product previews are available yet.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
