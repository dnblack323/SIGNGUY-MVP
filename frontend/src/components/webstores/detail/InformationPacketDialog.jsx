import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Mail, RotateCcw } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { extractError } from "@/lib/api";
import { getWebstoreInformationPacket, sendWebstoreInformationPacket } from "@/lib/webstores";
import { toast } from "sonner";

const STATUS = {
  prepared: { label: "Prepared", tone: "secondary" },
  sent: { label: "Sent", tone: "default" },
  delivered: { label: "Delivered", tone: "default" },
  failed: { label: "Not delivered", tone: "destructive" },
};

export default function InformationPacketDialog({ webstoreId, open, onOpenChange, onSent }) {
  const qc = useQueryClient();
  const [link, setLink] = useState("");
  const packet = useQuery({
    queryKey: ["webstore-information-packet", webstoreId],
    queryFn: () => getWebstoreInformationPacket(webstoreId),
    enabled: open && Boolean(webstoreId),
  });
  const send = useMutation({
    mutationFn: (resend) => sendWebstoreInformationPacket(webstoreId, { resend }),
    onSuccess: async (data) => {
      if (data.questionnaire_link) setLink(data.questionnaire_link);
      if (data.already_sent) toast.message("The packet was already sent. Use Resend to send a new link.");
      else if (data.delivery?.status === "failed") toast.error("The email was not delivered. Copy the link and share it another way.");
      else toast.success("Information packet sent");
      qc.setQueryData(["webstore-information-packet", webstoreId], data);
      await onSent?.();
    },
    onError: (err) => toast.error(extractError(err)),
  });
  const data = packet.data;
  const status = STATUS[data?.delivery?.status] || STATUS.prepared;
  const sent = (data?.sent_count || 0) > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[720px]" data-testid="information-packet-dialog">
        <DialogHeader>
          <DialogTitle>Information packet</DialogTitle>
          <DialogDescription>
            One email with how the store works, payments and proceeds, the final-sale policy, and the secure questionnaire link. The owner sees the same text in their portal.
          </DialogDescription>
        </DialogHeader>
        {packet.isLoading && <p className="text-sm text-muted-foreground">Loading preview...</p>}
        {data && (
          <div className="space-y-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={status.tone} data-testid="information-packet-status">{status.label}</Badge>
              <span className="text-muted-foreground">To {data.recipient_email || "no contact email"}</span>
              {sent && <span className="text-muted-foreground">Sent {data.sent_count} time{data.sent_count === 1 ? "" : "s"}</span>}
              {data.preview?.reply_to && <span className="text-muted-foreground">Replies go to {data.preview.reply_to}</span>}
            </div>
            {data.delivery?.status === "failed" && (
              <Alert variant="destructive">
                <AlertTitle>Email not delivered</AlertTitle>
                <AlertDescription>{data.delivery.error || data.delivery.provider_event || "Delivery failed."} Resend, or copy the link and share it directly.</AlertDescription>
              </Alert>
            )}
            <div className="rounded border p-3">
              <div className="font-medium">{data.preview?.subject}</div>
              <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-muted-foreground" data-testid="information-packet-body">{data.preview?.body}</pre>
            </div>
            {link && (
              <div className="flex flex-wrap items-center gap-2 rounded border border-sky-200 bg-sky-50 p-2">
                <span className="break-all text-xs" data-testid="information-packet-link">{link}</span>
                <Button size="sm" variant="outline" onClick={async () => { await navigator.clipboard.writeText(link); toast.success("Link copied"); }}>
                  <Copy className="size-4 mr-2" />Copy link
                </Button>
              </div>
            )}
          </div>
        )}
        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Close</Button>
          {sent ? (
            <Button onClick={() => send.mutate(true)} disabled={send.isPending} data-testid="information-packet-resend">
              <RotateCcw className="size-4 mr-2" />{send.isPending ? "Sending..." : "Resend with a new link"}
            </Button>
          ) : (
            <Button onClick={() => send.mutate(false)} disabled={send.isPending || !data?.recipient_email} data-testid="information-packet-send">
              <Mail className="size-4 mr-2" />{send.isPending ? "Sending..." : "Send packet"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
