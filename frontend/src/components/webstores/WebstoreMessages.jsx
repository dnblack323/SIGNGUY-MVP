import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

/**
 * The one shop <-> owner thread for a Webstore (Phase 3c). Shared by the staff
 * workspace and the owner portal; each side passes its own load/send calls.
 * `viewer` is "shop" or "owner" and only decides which side is "you".
 */
export default function WebstoreMessages({ webstoreId, viewer, load, send, extractError, intro, onSent }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const queryKey = ["webstore-messages", viewer, webstoreId];
  const messages = useQuery({ queryKey, queryFn: () => load(webstoreId), enabled: !!webstoreId });
  const post = useMutation({
    mutationFn: () => send(webstoreId, draft.trim()),
    onSuccess: (data) => {
      setDraft("");
      qc.setQueryData(queryKey, data);
      onSent?.();
    },
    onError: (err) => toast.error(extractError(err)),
  });
  const items = messages.data?.items || [];

  return (
    <Card data-testid="webstore-messages">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Messages</CardTitle>
        {intro && <p className="text-sm text-muted-foreground">{intro}</p>}
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="max-h-96 space-y-2 overflow-y-auto" data-testid="webstore-messages-list">
          {items.map((message) => {
            const mine = message.from === viewer;
            return (
              <div key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`} data-testid={`webstore-message-${message.id}`}>
                <div className={`max-w-[85%] rounded-lg border px-3 py-2 ${mine ? "border-sky-200 bg-sky-50" : "bg-white"}`}>
                  <div className="text-xs font-medium text-muted-foreground">
                    {mine ? "You" : message.sender_name} · {message.created_at ? new Date(message.created_at).toLocaleString() : ""}
                  </div>
                  <div className="mt-1 whitespace-pre-wrap">{message.body}</div>
                </div>
              </div>
            );
          })}
          {messages.isLoading && <div className="text-muted-foreground">Loading messages...</div>}
          {!messages.isLoading && items.length === 0 && <div className="text-muted-foreground">No messages yet.</div>}
        </div>
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (draft.trim()) post.mutate();
          }}
        >
          <Textarea
            rows={3}
            maxLength={5000}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={viewer === "owner" ? "Write to the shop" : "Write to the store owner"}
            aria-label="Message"
            data-testid="webstore-message-input"
          />
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={!draft.trim() || post.isPending} data-testid="webstore-message-send">
              <Send className="size-4 mr-2" />
              {post.isPending ? "Sending..." : "Send"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
