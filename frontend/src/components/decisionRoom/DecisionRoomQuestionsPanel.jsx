import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import StatusPill from "@/components/common/StatusPill";
import { toast } from "sonner";

/**
 * EC10 Phase 10E-3 — staff view + respond/resolve for customer questions.
 * Deliberately NOT a general messaging system: one response per question,
 * no threading, no broad review queue (that stays Phase 10E-4). Never
 * touches a Quote/Order/Order Item/pricing/Proof/staff markup.
 */
export default function DecisionRoomQuestionsPanel({ roomId, canRespond }) {
  const qc = useQueryClient();
  const [openReplyId, setOpenReplyId] = useState(null);
  const [replyText, setReplyText] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["decision-room-questions", roomId],
    queryFn: async () => (await api.get(`/decision-rooms/${roomId}/questions`)).data,
  });
  const items = data?.items || [];

  const respond = useMutation({
    mutationFn: async ({ questionId, staff_response }) => (await api.post(`/decision-rooms/${roomId}/questions/${questionId}/respond`, { staff_response })).data,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["decision-room-questions", roomId] }); toast.success("Response sent"); setOpenReplyId(null); setReplyText(""); },
    onError: (err) => toast.error(extractError(err)),
  });
  const resolve = useMutation({
    mutationFn: async (questionId) => (await api.post(`/decision-rooms/${roomId}/questions/${questionId}/resolve`)).data,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["decision-room-questions", roomId] }); toast.success("Marked resolved"); },
    onError: (err) => toast.error(extractError(err)),
  });

  if (isLoading) return null;
  if (items.length === 0) return null;

  return (
    <div className="grid gap-3" data-testid="decision-room-questions-panel">
      <h3 className="font-semibold text-sm">Customer questions ({items.length})</h3>
      <div className="rounded-xl border bg-card divide-y">
        {items.map((q) => (
          <div key={q.id} className="p-3 grid gap-2 text-sm" data-testid={`decision-room-staff-question-${q.id}`}>
            <div className="flex items-center gap-2 flex-wrap justify-between">
              <div className="flex items-center gap-2 flex-wrap">
                <StatusPill kind="decision_review_status" value={q.status === "open" ? "pending_review" : "acknowledged"} />
                <span className="text-xs text-muted-foreground">{q.status} · {new Date(q.created_at).toLocaleString()}</span>
              </div>
              {canRespond && q.status !== "resolved" && (
                <Button size="sm" variant="outline" onClick={() => resolve.mutate(q.id)} disabled={resolve.isPending} data-testid={`decision-room-question-${q.id}-resolve-button`}>
                  Mark resolved
                </Button>
              )}
            </div>
            <div>{q.customer_message}</div>
            {q.staff_response && <div className="text-xs text-muted-foreground border-t pt-1" data-testid={`decision-room-question-${q.id}-existing-response`}>Response: {q.staff_response}</div>}
            {canRespond && !q.staff_response && (
              openReplyId === q.id ? (
                <div className="grid gap-2">
                  <Textarea rows={2} value={replyText} onChange={(e) => setReplyText(e.target.value)} placeholder="Write a customer-safe response…" data-testid={`decision-room-question-${q.id}-response-textarea`} />
                  <div className="flex gap-2">
                    <Button size="sm" disabled={!replyText.trim() || respond.isPending} onClick={() => respond.mutate({ questionId: q.id, staff_response: replyText })} data-testid={`decision-room-question-${q.id}-send-response-button`}>Send response</Button>
                    <Button size="sm" variant="ghost" onClick={() => { setOpenReplyId(null); setReplyText(""); }}>Cancel</Button>
                  </div>
                </div>
              ) : (
                <Button size="sm" variant="outline" className="w-fit" onClick={() => setOpenReplyId(q.id)} data-testid={`decision-room-question-${q.id}-reply-button`}>Respond</Button>
              )
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
