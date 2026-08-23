import { Send } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { centsToDollarsString } from "@/lib/format";

export default function OverviewOrdersPanel({ model }) {
  const { formatDateTime, formatLabel, id, orders, productionHandoff } = model;

return (
            <Card data-testid="webstore-orders-panel">
              <CardHeader className="flex flex-row items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">Orders</CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Paid Webstore purchases from the canonical Orders system.
                  </p>
                </div>
                <Badge variant="outline">
                  {orders.data?.total ?? orders.data?.items?.length ?? 0}
                </Badge>
              </CardHeader>
              <CardContent>
                {orders.isLoading ? (
                  <p className="text-sm text-muted-foreground">Loading orders...</p>
                ) : orders.isError ? (
                  <p className="text-sm text-destructive">Orders could not be loaded.</p>
                ) : (orders.data?.items || []).length === 0 ? (
                  <p className="text-sm text-muted-foreground">No paid Webstore orders yet.</p>
                ) : (
                  <div className="space-y-2" data-testid="webstore-orders-list">
                    {(orders.data?.items || []).map((order) => (
                      <div
                        key={order.id}
                        className="grid gap-2 rounded-md border p-3 text-sm md:grid-cols-[1fr_auto_auto_auto] md:items-center"
                        data-testid={`webstore-order-${order.id}`}
                      >
                        <div>
                          <div className="font-medium">
                            Order #{order.number ?? order.id}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {order.customer?.name || order.customer?.email || "Customer"}
                            {order.created_at ? ` · ${formatDateTime(order.created_at)}` : ""}
                          </div>
                        </div>
                        <Badge variant="outline" className="w-fit capitalize">
                          {formatLabel(order.payment?.status || order.status)}
                        </Badge>
                        <Badge variant="outline" className="w-fit capitalize">
                          {formatLabel(order.fulfillment?.status || "awaiting production")}
                        </Badge>
                        <div className="font-semibold md:text-right">
                          {centsToDollarsString(order.total_cents)}
                        </div>
                        {(order.fulfillment?.production_bridge_status === "not_started" ||
                          order.fulfillment?.status === "awaiting_production_handoff") && (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="md:col-start-4 md:justify-self-end"
                            disabled={productionHandoff.isPending}
                            onClick={() => productionHandoff.mutate(order.id)}
                            data-testid={`webstore-production-handoff-${order.id}`}
                          >
                            {productionHandoff.isPending ? "Sending..." : "Send to Production"}
                          </Button>
                        )}
                        {order.items?.length > 0 && (
                          <div className="text-xs text-muted-foreground md:col-span-4">
                            {order.items.map((item) => `${item.quantity} × ${item.description}`).join(", ")}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
  );
}
