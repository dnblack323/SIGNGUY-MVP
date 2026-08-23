import {
  CheckCircle2,
  Send,
} from "lucide-react";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export default function OverviewLaunchPacketCard({ model }) {
  const {
    activePacket,
    changeResponses,
    detail,
    id,
    launch,
    packet,
    promo,
    sendPacket,
    setChangeResponses,
    store,
    updateChange,
  } = model;

return (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Launch Packet</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid gap-1.5">
                    <Label>Launch packet message</Label>
                    <Textarea
                      rows={3}
                      value={promo}
                      onChange={(e) => setPromo(e.target.value)}
                      placeholder="Optional owner-facing launch/promo note included in the next packet version."
                      data-testid="webstore-promo"
                    />
                    <div className="text-xs text-muted-foreground">
                      This text is saved into the generated packet version and
                      shown to the store owner for approval.
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      disabled={packet.isPending}
                      onClick={() => packet.mutate()}
                    >
                      <CheckCircle2 className="size-4 mr-2" />
                      Generate
                    </Button>
                    <Button
                      disabled={!activePacket || sendPacket.isPending}
                      onClick={() => sendPacket.mutate()}
                    >
                      <Send className="size-4 mr-2" />
                      Send
                    </Button>
                  </div>
                  {activePacket && (
                    <Alert data-testid="webstore-launch-packet-summary">
                      <AlertTitle className="capitalize">
                        Version {activePacket.version || 1} -{" "}
                        {String(activePacket.status).replace(/_/g, " ")}
                      </AlertTitle>
                      <AlertDescription>
                        <div className="rounded border bg-white p-2 text-sm">
                          {activePacket.promotion_copy ||
                            "No custom launch message was entered for this packet."}
                        </div>
                        <div className="mt-1 text-xs">
                          Products:{" "}
                          {activePacket.pricing_summary?.product_count ||
                            activePacket.snapshot?.products?.length ||
                            0}{" "}
                          · Delivery:{" "}
                          {activePacket.delivery_status || "not sent"}
                        </div>
                        <div className="mt-1 text-xs">
                          Snapshot: {activePacket.snapshot_hash || "pending"}
                        </div>
                      </AlertDescription>
                    </Alert>
                  )}
                  {(detail.data?.change_requests || []).length > 0 && (
                    <div
                      className="rounded border divide-y"
                      data-testid="webstore-change-requests"
                    >
                      {detail.data.change_requests.map((request) => (
                        <div key={request.id} className="p-3 space-y-2 text-sm">
                          <div className="flex items-center justify-between gap-2">
                            <div className="font-medium capitalize">
                              {request.category} - v{request.packet_version}
                            </div>
                            <Badge
                              variant={
                                ["resolved", "declined", "superseded"].includes(
                                  request.status,
                                )
                                  ? "secondary"
                                  : "outline"
                              }
                            >
                              {request.status}
                            </Badge>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {request.owner_comment}
                          </div>
                          {!["resolved", "declined", "superseded"].includes(
                            request.status,
                          ) && (
                            <div className="flex gap-2">
                              <Input
                                placeholder="Response to owner"
                                value={changeResponses[request.id] || ""}
                                data-testid={`webstore-change-response-${request.id}`}
                                onChange={(e) =>
                                  setChangeResponses((prev) => ({
                                    ...prev,
                                    [request.id]: e.target.value,
                                  }))
                                }
                              />
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                  updateChange.mutate({
                                    requestId: request.id,
                                    status: "resolved",
                                    response:
                                      changeResponses[request.id] ||
                                      "Resolved by shop staff.",
                                  })
                                }
                              >
                                Resolve
                              </Button>
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
