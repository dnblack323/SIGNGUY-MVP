import { CheckCircle2, MessageSquare, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { centsToDollarsString } from "@/lib/format";

const CHANGE_REQUEST_CATEGORIES = [
  "branding",
  "product",
  "price",
  "description",
  "artwork",
  "mockup",
  "variant",
  "personalization",
  "fulfillment",
  "availability",
  "policy",
  "general",
];

export default function OwnerPortalLaunchPacket({
  data,
  packetComment,
  onPacketCommentChange,
  changeRequest,
  onChangeRequestChange,
  onApprove,
  onReject,
  onRequestChanges,
}) {
  if (!data.launch_packet) return null;
  const packetClosed = [
    "owner_approved",
    "rejected",
    "superseded",
    "invalidated",
  ].includes(data.launch_packet.status);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Launch Packet</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="font-medium">
              Version {data.launch_packet.version || 1}
            </div>
            <div className="text-xs text-muted-foreground capitalize">
              {String(data.launch_packet.status).replace(/_/g, " ")}
            </div>
          </div>
          <Badge variant="outline">
            {data.launch_packet.delivery_status || "portal"}
          </Badge>
        </div>
        <div>
          {data.launch_packet.promotion_copy ||
            "Launch packet is ready for approval."}
        </div>
        {data.launch_packet.snapshot?.owner_preview && (
          <div
            className="rounded border p-3 space-y-2"
            data-testid="portal-launch-packet-preview"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-medium">
                  {data.launch_packet.snapshot.owner_preview.display_name}
                </div>
                <div className="text-xs text-muted-foreground">
                  {data.launch_packet.snapshot.owner_preview.headline}
                </div>
              </div>
              <Badge
                variant="outline"
                style={{
                  borderColor:
                    data.launch_packet.snapshot.owner_preview.accent_color ||
                    undefined,
                }}
              >
                {data.launch_packet.snapshot.owner_preview.accent_color ||
                  "Accent set"}
              </Badge>
            </div>
            {data.launch_packet.snapshot.owner_preview.greeting && (
              <div className="text-xs text-muted-foreground">
                {data.launch_packet.snapshot.owner_preview.greeting}
              </div>
            )}
          </div>
        )}
        {data.launch_packet.snapshot?.qr_reference && (
          <div
            className="rounded border p-3 text-xs"
            data-testid="portal-launch-packet-share"
          >
            <div className="font-medium">Store link and QR</div>
            <div className="break-all">
              {data.launch_packet.snapshot.qr_reference.destination}
            </div>
            <div className="text-muted-foreground">
              {data.launch_packet.snapshot.qr_reference.warning}
            </div>
          </div>
        )}
        <div
          className="rounded border p-3 space-y-2"
          data-testid="portal-launch-packet-products"
        >
          {(data.launch_packet.snapshot?.products || []).map((product) => (
            <div
              key={product.packet_ref || product.id}
              className="flex items-center justify-between gap-3"
            >
              <div>
                <div className="font-medium">{product.name}</div>
                <div className="text-xs text-muted-foreground">
                  {product.description || product.product_type}
                </div>
              </div>
              <span className="font-medium">
                {centsToDollarsString(product.selling_price_cents)}
              </span>
            </div>
          ))}
        </div>
        {(data.launch_packet.approval_history || []).length > 0 && (
          <div
            className="rounded border p-3 text-xs"
            data-testid="portal-launch-packet-approval-history"
          >
            {(data.launch_packet.approval_history || []).map((entry) => (
              <div key={entry.id} className="flex justify-between gap-3">
                <span>{String(entry.action).replace(/_/g, " ")}</span>
                <span className="text-muted-foreground">
                  {entry.reason || entry.actor_display || "No comment"}
                </span>
              </div>
            ))}
          </div>
        )}
        <div
          className="rounded border p-3 text-xs"
          data-testid="portal-readiness-summary"
        >
          {(data.readiness_summary || []).map((gate) => (
            <div className="flex justify-between gap-3" key={gate.key}>
              <span>{gate.owner_wording}</span>
              <Badge variant={gate.state === "ready" ? "secondary" : "outline"}>
                {gate.state}
              </Badge>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Textarea
            rows={2}
            value={packetComment}
            onChange={(e) => onPacketCommentChange(e.target.value)}
            placeholder="Optional approval comment, or required reason for rejection."
            data-testid="portal-packet-decision-comment"
          />
          <Button
            disabled={packetClosed}
            onClick={onApprove}
            data-testid="portal-approve-packet"
          >
            <CheckCircle2 className="size-4 mr-2" />
            Approve packet v{data.launch_packet.version || 1}
          </Button>
          <Button
            variant="outline"
            disabled={!packetComment.trim() || packetClosed}
            onClick={onReject}
            data-testid="portal-reject-packet"
          >
            <XCircle className="size-4 mr-2" />
            Reject packet
          </Button>
        </div>
        <div
          className="rounded border p-3 space-y-2"
          data-testid="portal-change-request"
        >
          <div className="font-medium">Request changes</div>
          <select
            className="border rounded px-2 py-1 text-sm"
            value={changeRequest.category}
            onChange={(e) =>
              onChangeRequestChange({
                ...changeRequest,
                category: e.target.value,
              })
            }
          >
            {CHANGE_REQUEST_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <Textarea
            rows={3}
            value={changeRequest.comment}
            onChange={(e) =>
              onChangeRequestChange({
                ...changeRequest,
                comment: e.target.value,
              })
            }
            placeholder="Tell the shop what needs to change."
            data-testid="portal-change-request-comment"
          />
          <Button
            variant="outline"
            disabled={!changeRequest.comment.trim()}
            onClick={onRequestChanges}
            data-testid="portal-request-changes"
          >
            <MessageSquare className="size-4 mr-2" />
            Send change request
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
