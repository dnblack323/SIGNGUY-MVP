import { useMemo, useState } from "react";
import { StatusPill } from "@/components/common/StatusPill";
import { DecisionRoomMedia } from "@/components/decisionRoom/DecisionRoomMedia";
import { DecisionRoomAnchorableMedia } from "@/components/decisionRoom/DecisionRoomAnchorableMedia";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CheckCircle2, XCircle, Bookmark, MessageCircleQuestion, X } from "lucide-react";

/**
 * EC10 Phase 10E-1/10E-2/10E-3 — Decision Room comparison view. Shared by
 * the Customer Portal detail page and the Public Token page (both fetch
 * the identical customer-safe shape from the backend — see
 * `decision_room_service.get_customer_view()`).
 *
 * `buildMediaUrl(fileId)` builds the customer-safe media endpoint URL for a
 * given referenced file id (portal: `/portal/decision-rooms/{id}/media/
 * {fileId}`; public: `/public/decision-rooms/{id}/media/{fileId}?t=...`).
 * `authToken` is the portal JWT (omit for public-token mode — the token is
 * already embedded in the URL by `buildMediaUrl`).
 *
 * Phase 10E-2 actions (select/reject/reject-all/request-change) go through
 * `onSubmitDecision`. Phase 10E-3 adds `onSubmitQuestion`, `onAddOverlay`/
 * `onWithdrawOverlay` (anchored comments/pins over option media), and
 * `onSaveForLater` — all promise-returning callbacks supplied by the
 * portal/public page. This component stays a pure presentational view: it
 * never calls an API directly, only derives "already done" state from the
 * caller-supplied history arrays (`myDecisions`/`myQuestions`/`myOverlays`/
 * `mySavedForLater`, all most-recent-first).
 */
export default function DecisionRoomCustomerView({
  room, buildMediaUrl, authToken, myDecisions, onSubmitDecision,
  myQuestions, onSubmitQuestion, myOverlays, onAddOverlay, onWithdrawOverlay,
  mySavedForLater, onSaveForLater,
}) {
  const money = (cents) => `$${(cents / 100).toFixed(2)}`;
  const canRespond = room.status === "published" && typeof onSubmitDecision === "function";
  const [busyKey, setBusyKey] = useState(null);
  const [changeComment, setChangeComment] = useState("");
  const [questionText, setQuestionText] = useState("");
  const [questionOptionId, setQuestionOptionId] = useState("__none__");
  const [saveNote, setSaveNote] = useState("");
  const [showSaveForm, setShowSaveForm] = useState(false);

  const decisions = useMemo(() => myDecisions || [], [myDecisions]);
  // `myDecisions` is sorted most-recent-first by the backend — the latest
  // `option_selected` row is always the current (unsuperseded) selection,
  // since every new selection points its `supersedes_decision_id` back at
  // the immediately-prior one (see `submit_customer_decision()`).
  const currentSelectionOptionId = useMemo(
    () => decisions.find((d) => d.action_type === "option_selected")?.option_id ?? null,
    [decisions],
  );
  const rejectedOptionIds = useMemo(
    () => new Set(decisions.filter((d) => d.action_type === "option_rejected").map((d) => d.option_id)),
    [decisions],
  );
  const allOptionsRejected = decisions.some((d) => d.action_type === "all_options_rejected");
  const changeRequestSubmitted = decisions.some((d) => d.action_type === "change_requested");
  const questions = myQuestions || [];
  const overlays = myOverlays || [];
  const savedMarks = mySavedForLater || [];
  const canAnnotate = canRespond && !!room.allow_customer_comments && typeof onAddOverlay === "function";

  async function submit(action_type, option_id, comment) {
    const key = `${action_type}:${option_id || ""}`;
    setBusyKey(key);
    try {
      await onSubmitDecision({ action_type, option_id: option_id || null, comment: comment || null });
      if (action_type === "change_requested") setChangeComment("");
    } finally {
      setBusyKey(null);
    }
  }

  async function submitQuestion() {
    if (!questionText.trim()) return;
    setBusyKey("question");
    try {
      await onSubmitQuestion({ customer_message: questionText, option_id: questionOptionId === "__none__" ? null : questionOptionId });
      setQuestionText(""); setQuestionOptionId("__none__");
    } finally {
      setBusyKey(null);
    }
  }

  async function submitSave() {
    setBusyKey("save_for_later");
    try {
      await onSaveForLater({ note: saveNote || null });
      setSaveNote(""); setShowSaveForm(false);
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <div className="space-y-6" data-testid="decision-room-customer-view">
      <div>
        <div className="flex items-center gap-2 flex-wrap justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-semibold" data-testid="decision-room-customer-title">{room.title}</h1>
            <StatusPill kind="decision_room" value={room.status} />
          </div>
          {canRespond && room.allow_save_for_later && typeof onSaveForLater === "function" && (
            <Button size="sm" variant="outline" onClick={() => setShowSaveForm((v) => !v)} data-testid="decision-room-save-for-later-toggle-button">
              <Bookmark className="size-3.5 mr-1" />Save for later
            </Button>
          )}
        </div>
        {room.customer_safe_intro && <p className="text-slate-600 mt-1" data-testid="decision-room-customer-intro">{room.customer_safe_intro}</p>}
        {room.status === "expired" && <p className="text-sm text-orange-700 mt-2" data-testid="decision-room-expired-banner">This Decision Room has expired. It is shown here as a historical record.</p>}
        {room.status === "closed" && <p className="text-sm text-slate-500 mt-2" data-testid="decision-room-closed-banner">This Decision Room is closed. It is shown here as a historical record.</p>}
        {allOptionsRejected && <p className="text-sm text-rose-700 mt-2" data-testid="decision-room-all-rejected-banner">You rejected all options. Our team has been notified and will follow up.</p>}
        {showSaveForm && (
          <div className="mt-2 rounded-lg border p-3 space-y-2 bg-amber-50" data-testid="decision-room-save-for-later-form">
            <p className="text-xs text-slate-600">Saving does not select or reject any option — it's just a bookmark so you can pick up where you left off.</p>
            <Textarea rows={2} value={saveNote} onChange={(e) => setSaveNote(e.target.value)} placeholder="Optional note to yourself…" data-testid="decision-room-save-for-later-note" />
            <Button size="sm" disabled={busyKey === "save_for_later"} onClick={submitSave} data-testid="decision-room-save-for-later-submit-button">Confirm save</Button>
          </div>
        )}
        {savedMarks.length > 0 && (
          <p className="text-xs text-emerald-700 mt-2 flex items-center gap-1" data-testid="decision-room-saved-confirmation">
            <Bookmark className="size-3" />Saved on {new Date(savedMarks[0].saved_at || savedMarks[0].created_at).toLocaleString()} — no selection was submitted.
          </p>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2" data-testid="decision-room-customer-options">
        {(room.options || []).map((o) => {
          const isSelected = currentSelectionOptionId === o.id;
          const isRejected = rejectedOptionIds.has(o.id);
          return (
            <div
              key={o.id}
              className={`rounded-lg border bg-white p-4 space-y-2 ${isSelected ? "ring-2 ring-emerald-500" : ""}`}
              data-testid={`decision-room-customer-option-${o.id}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{o.customer_label}</span>
                <div className="flex items-center gap-1">
                  {o.badge_type !== "none" && <StatusPill kind="decision_badge" value={o.badge_type} />}
                  {isSelected && <span className="inline-flex items-center gap-1 text-xs text-emerald-700" data-testid={`decision-room-customer-option-${o.id}-selected-badge`}><CheckCircle2 className="size-3.5" />Selected</span>}
                  {isRejected && !isSelected && <span className="inline-flex items-center gap-1 text-xs text-slate-400" data-testid={`decision-room-customer-option-${o.id}-rejected-badge`}><XCircle className="size-3.5" />Rejected</span>}
                </div>
              </div>
              {o.headline && <div className="text-sm font-medium text-slate-700">{o.headline}</div>}
              {o.customer_safe_description && <p className="text-sm text-slate-600">{o.customer_safe_description}</p>}
              {o.included_features?.length > 0 && (
                <ul className="text-sm list-disc pl-5 text-slate-700">{o.included_features.map((f, i) => <li key={i}>{f}</li>)}</ul>
              )}
              {o.excluded_features?.length > 0 && (
                <ul className="text-sm list-disc pl-5 text-slate-400">{o.excluded_features.map((f, i) => <li key={i}>Not included: {f}</li>)}</ul>
              )}
              {o.expected_timing && <div className="text-xs text-slate-500">Timing: {o.expected_timing}</div>}
              {(o.file_ids?.length > 0 || o.rendered_preview_file_id || o.proof_preview_file_id) && (
                <div className="grid grid-cols-2 gap-2" data-testid={`decision-room-customer-option-${o.id}-media`}>
                  {o.rendered_preview_file_id && (
                    <DecisionRoomAnchorableMedia
                      src={buildMediaUrl?.(o.rendered_preview_file_id)} authToken={authToken} alt="Rendered preview"
                      testId={`decision-room-media-${o.id}-preview`} fileId={o.rendered_preview_file_id}
                      canAnnotate={canAnnotate} overlays={overlays} onAddOverlay={onAddOverlay}
                    />
                  )}
                  {o.proof_preview_file_id && (
                    <DecisionRoomAnchorableMedia
                      src={buildMediaUrl?.(o.proof_preview_file_id)} authToken={authToken} alt="Proof preview"
                      testId={`decision-room-media-${o.id}-proof`} fileId={o.proof_preview_file_id}
                      canAnnotate={canAnnotate} overlays={overlays} onAddOverlay={onAddOverlay}
                    />
                  )}
                  {(o.file_ids || []).map((fid) => (
                    <DecisionRoomAnchorableMedia
                      key={fid} src={buildMediaUrl?.(fid)} authToken={authToken} alt="Attachment"
                      testId={`decision-room-media-${o.id}-${fid}`} fileId={fid}
                      canAnnotate={canAnnotate} overlays={overlays} onAddOverlay={onAddOverlay}
                    />
                  ))}
                </div>
              )}
              <div className="text-lg font-semibold tabular-nums" data-testid={`decision-room-customer-option-${o.id}-price`}>
                {o.displayed_price_cents != null ? money(o.displayed_price_cents) : (o.price_display_mode === "contact_for_price" ? "Contact us for pricing" : "Price on request")}
              </div>
              {canRespond && (
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm" className="flex-1" disabled={!!busyKey || isSelected}
                    onClick={() => submit("option_selected", o.id)}
                    data-testid={`decision-room-select-${o.id}-button`}
                  >
                    {isSelected ? "Selected" : "Select this option"}
                  </Button>
                  <Button
                    size="sm" variant="outline" className="flex-1" disabled={!!busyKey || isRejected}
                    onClick={() => submit("option_rejected", o.id)}
                    data-testid={`decision-room-reject-${o.id}-button`}
                  >
                    {isRejected ? "Rejected" : "Reject"}
                  </Button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {canRespond && room.allow_reject_all && !allOptionsRejected && (
        <div className="rounded-lg border border-dashed p-3" data-testid="decision-room-reject-all-section">
          <Button
            size="sm" variant="outline" disabled={!!busyKey}
            onClick={() => submit("all_options_rejected", null)}
            data-testid="decision-room-reject-all-button"
          >
            None of these work for me
          </Button>
        </div>
      )}

      {canRespond && room.allow_change_requests && (
        <div className="rounded-lg border p-4 space-y-2" data-testid="decision-room-change-request-section">
          <div className="text-sm font-medium text-slate-700">Request a change</div>
          {changeRequestSubmitted && <p className="text-xs text-emerald-700" data-testid="decision-room-change-request-submitted-note">A change request is on file — our team will follow up.</p>}
          <Textarea
            rows={3} value={changeComment} onChange={(e) => setChangeComment(e.target.value)}
            placeholder="Tell us what you'd like changed…" data-testid="decision-room-change-request-textarea"
          />
          <Button
            size="sm" disabled={!!busyKey || !changeComment.trim()}
            onClick={() => submit("change_requested", null, changeComment)}
            data-testid="decision-room-change-request-submit-button"
          >
            Submit change request
          </Button>
        </div>
      )}

      {(room.allow_customer_questions || questions.length > 0) && (
        <div className="rounded-lg border p-4 space-y-3" data-testid="decision-room-questions-section">
          <div className="text-sm font-medium text-slate-700 flex items-center gap-1"><MessageCircleQuestion className="size-4" />Questions</div>
          {canRespond && room.allow_customer_questions && typeof onSubmitQuestion === "function" && (
            <div className="space-y-2">
              <Select value={questionOptionId} onValueChange={setQuestionOptionId}>
                <SelectTrigger className="h-8 text-xs w-64" data-testid="decision-room-question-option-select"><SelectValue placeholder="About: Overall" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">About: Overall</SelectItem>
                  {(room.options || []).map((o) => <SelectItem key={o.id} value={o.id}>About: {o.customer_label}</SelectItem>)}
                </SelectContent>
              </Select>
              <Textarea rows={2} value={questionText} onChange={(e) => setQuestionText(e.target.value)} placeholder="Ask a question…" data-testid="decision-room-question-textarea" />
              <Button size="sm" disabled={!!busyKey || !questionText.trim()} onClick={submitQuestion} data-testid="decision-room-question-submit-button">Ask</Button>
            </div>
          )}
          {questions.length > 0 && (
            <div className="space-y-2" data-testid="decision-room-questions-list">
              {questions.map((q) => (
                <div key={q.id} className="rounded border p-2 text-sm" data-testid={`decision-room-question-${q.id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span>{q.customer_message}</span>
                    <StatusPill kind="decision_review_status" value={q.status === "open" ? "pending_review" : "acknowledged"} />
                  </div>
                  {q.staff_response && <div className="mt-1 text-slate-600 text-xs border-t pt-1" data-testid={`decision-room-question-${q.id}-response`}>Our team: {q.staff_response}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {overlays.filter((o) => o.status !== "withdrawn").length > 0 && (
        <div className="rounded-lg border p-4 space-y-2" data-testid="decision-room-overlays-list">
          <div className="text-sm font-medium text-slate-700">Your comments &amp; pins</div>
          {overlays.filter((o) => o.status !== "withdrawn").map((o) => (
            <div key={o.id} className="flex items-center justify-between gap-2 text-sm rounded border p-2" data-testid={`decision-room-overlay-${o.id}`}>
              <span>{o.overlay_type === "pin" ? `Pin #${o.marker_number}` : "Comment"}: {o.customer_message}</span>
              {canRespond && typeof onWithdrawOverlay === "function" && (
                <Button size="sm" variant="ghost" className="h-6 px-2" onClick={() => onWithdrawOverlay(o.id)} data-testid={`decision-room-overlay-${o.id}-withdraw-button`}>
                  <X className="size-3.5" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {!canRespond && <p className="text-xs text-slate-400 italic" data-testid="decision-room-readonly-note">This is a read-only historical record. New decisions are no longer accepted here.</p>}
    </div>
  );
}
