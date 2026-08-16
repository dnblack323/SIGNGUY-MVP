import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Eye, Link2, RotateCw, ShieldOff } from "lucide-react";
import { toast } from "sonner";

import api, { extractError } from "@/lib/api";
import DecisionRoomPreviewDialog from "@/components/decisionRoom/DecisionRoomPreviewDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function buildPublicDecisionRoomUrl(roomId, token) {
  if (!roomId || !token) return "";
  return `${window.location.origin}/public/decision-rooms/${roomId}?t=${encodeURIComponent(token)}`;
}

function tokenStatus(token) {
  if (token.revoked) return "revoked";
  if (token.consumed_at) return "used";
  if (token.expires_at && new Date(token.expires_at).getTime() < Date.now()) return "expired";
  return "active";
}

export default function DecisionRoomSharePanel({ roomId }) {
  const qc = useQueryClient();
  const [audienceEmail, setAudienceEmail] = useState("");
  const [latestLink, setLatestLink] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);

  const tokens = useQuery({
    queryKey: ["decision-room-share-tokens", roomId],
    queryFn: async () => (await api.get(`/decision-rooms/${roomId}/share-tokens`)).data,
    enabled: Boolean(roomId),
  });

  const mint = useMutation({
    mutationFn: async (email) => (await api.post(`/decision-rooms/${roomId}/share`, {
      audience_email: email || null,
      ttl_hours: 168,
      single_use: false,
    })).data,
    onSuccess: (data) => {
      setLatestLink(buildPublicDecisionRoomUrl(roomId, data.token));
      qc.invalidateQueries({ queryKey: ["decision-room-share-tokens", roomId] });
      toast.success("Share link created. Copy it manually or send it through an approved channel.");
    },
    onError: (error) => toast.error(extractError(error)),
  });

  const revoke = useMutation({
    mutationFn: async (tokenId) => api.delete(`/decision-rooms/share-tokens/${tokenId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["decision-room-share-tokens", roomId] });
      toast.success("Share link revoked");
    },
    onError: (error) => toast.error(extractError(error)),
  });

  const copyLatest = async () => {
    if (!latestLink) return;
    try {
      await navigator.clipboard?.writeText(latestLink);
      toast.success("Share link copied");
    } catch {
      toast.message("Copy the displayed link manually.");
    }
  };

  const items = tokens.data?.items || [];

  return (
    <Card data-testid="decision-room-share-panel">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 gap-3">
        <CardTitle className="text-base">Decision Room sharing</CardTitle>
        <Button size="sm" variant="outline" onClick={() => setPreviewOpen(true)} data-testid="decision-room-share-preview-button">
          <Eye className="size-4 mr-1" /> Preview
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2">
          <Label className="text-xs">Audience email (optional)</Label>
          <div className="flex flex-wrap gap-2">
            <Input
              value={audienceEmail}
              onChange={(event) => setAudienceEmail(event.target.value)}
              placeholder="customer@example.com"
              className="min-w-0 flex-1"
              data-testid="decision-room-share-email"
            />
            <Button
              type="button"
              onClick={() => mint.mutate(audienceEmail)}
              disabled={mint.isPending}
              data-testid="decision-room-share-create-button"
            >
              <Link2 className="size-4 mr-1" /> Create copy link
            </Button>
          </div>
          <div className="text-xs text-muted-foreground">
            This creates a secure link only. Email or SMS delivery is not marked successful by this service.
          </div>
        </div>
        {latestLink && (
          <div className="rounded-md border p-3 grid gap-2" data-testid="decision-room-share-latest">
            <Label className="text-xs">Latest one-time-visible link</Label>
            <div className="flex gap-2">
              <Input readOnly value={latestLink} />
              <Button type="button" variant="outline" onClick={copyLatest} data-testid="decision-room-share-copy-button">
                <Copy className="size-4 mr-1" /> Copy
              </Button>
            </div>
          </div>
        )}
        <div className="space-y-2" data-testid="decision-room-share-history">
          {items.length === 0 ? (
            <div className="text-sm text-muted-foreground">No share links have been created yet.</div>
          ) : items.map((token) => (
            <div key={token.id} className="rounded-md border p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{token.audience_email || "Manual share link"}</div>
                  <div className="text-xs text-muted-foreground">
                    Issued {token.created_at ? String(token.created_at).slice(0, 16) : "unknown"}
                    {token.expires_at ? ` · expires ${String(token.expires_at).slice(0, 16)}` : ""}
                  </div>
                </div>
                <Badge variant="outline">{tokenStatus(token)}</Badge>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => mint.mutate(token.audience_email || "")}
                  disabled={mint.isPending}
                  data-testid={`decision-room-share-resend-${token.id}`}
                >
                  <RotateCw className="size-4 mr-1" /> Resend link
                </Button>
                {!token.revoked && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => revoke.mutate(token.id)}
                    disabled={revoke.isPending}
                    data-testid={`decision-room-share-revoke-${token.id}`}
                  >
                    <ShieldOff className="size-4 mr-1" /> Revoke
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
      <DecisionRoomPreviewDialog roomId={roomId} open={previewOpen} onOpenChange={setPreviewOpen} />
    </Card>
  );
}
