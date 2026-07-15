import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import portalApi, { API, portalExtractError } from "./portalApi";
import DecisionRoomCustomerView from "@/components/decisionRoom/DecisionRoomCustomerView";

/**
 * EC10 Phase 10E-1/10E-2/10E-3 — Customer Portal Decision Room detail.
 */
export default function PortalDecisionRoomPage() {
  const { id } = useParams();
  const [room, setRoom] = useState(null);
  const [myDecisions, setMyDecisions] = useState([]);
  const [myQuestions, setMyQuestions] = useState([]);
  const [myOverlays, setMyOverlays] = useState([]);
  const [mySavedForLater, setMySavedForLater] = useState([]);
  const [err, setErr] = useState(null);

  function load() {
    portalApi.get(`/portal/decision-rooms/${id}`)
      .then((r) => setRoom(r.data))
      .catch((e) => setErr(portalExtractError(e, "This Decision Room is not available.")));
    portalApi.get(`/portal/decision-rooms/${id}/decisions`).then((r) => setMyDecisions(r.data.items || [])).catch(() => setMyDecisions([]));
    portalApi.get(`/portal/decision-rooms/${id}/questions`).then((r) => setMyQuestions(r.data.items || [])).catch(() => setMyQuestions([]));
    portalApi.get(`/portal/decision-rooms/${id}/overlays`).then((r) => setMyOverlays(r.data.items || [])).catch(() => setMyOverlays([]));
    portalApi.get(`/portal/decision-rooms/${id}/save-for-later`).then((r) => setMySavedForLater(r.data.items || [])).catch(() => setMySavedForLater([]));
  }

  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function onSubmitDecision({ action_type, option_id, comment }) {
    try {
      await portalApi.post(`/portal/decision-rooms/${id}/decisions`, {
        action_type, option_id, comment, idempotency_key: `${crypto.randomUUID()}`,
      });
      toast.success("Your response has been recorded");
      load();
    } catch (e) {
      toast.error(portalExtractError(e, "Something went wrong"));
      throw e;
    }
  }

  async function onSubmitQuestion({ customer_message, option_id }) {
    try {
      await portalApi.post(`/portal/decision-rooms/${id}/questions`, {
        customer_message, option_id, idempotency_key: `${crypto.randomUUID()}`,
      });
      toast.success("Your question has been sent");
      load();
    } catch (e) {
      toast.error(portalExtractError(e, "Something went wrong"));
      throw e;
    }
  }

  async function onAddOverlay({ overlay_type, normalized_x, normalized_y, customer_message, source_file_id }) {
    try {
      await portalApi.post(`/portal/decision-rooms/${id}/overlays`, {
        overlay_type, normalized_x, normalized_y, customer_message, source_file_id, idempotency_key: `${crypto.randomUUID()}`,
      });
      toast.success(overlay_type === "pin" ? "Pin added" : "Comment added");
      load();
    } catch (e) {
      toast.error(portalExtractError(e, "Something went wrong"));
      throw e;
    }
  }

  async function onWithdrawOverlay(overlayId) {
    try {
      await portalApi.post(`/portal/decision-rooms/${id}/overlays/${overlayId}/withdraw`);
      toast.success("Withdrawn");
      load();
    } catch (e) {
      toast.error(portalExtractError(e, "Something went wrong"));
    }
  }

  async function onSaveForLater({ note }) {
    try {
      await portalApi.post(`/portal/decision-rooms/${id}/save-for-later`, { note, idempotency_key: `${crypto.randomUUID()}` });
      toast.success("Saved for later — no selection was submitted");
      load();
    } catch (e) {
      toast.error(portalExtractError(e, "Something went wrong"));
      throw e;
    }
  }

  if (err) return <div className="p-6 text-sm text-rose-700" data-testid="portal-decision-room-error">{err}</div>;
  if (!room) return <div className="p-6 text-sm text-slate-500" data-testid="portal-decision-room-loading">Loading…</div>;
  return (
    <DecisionRoomCustomerView
      room={room}
      authToken={localStorage.getItem("sg_portal_token")}
      buildMediaUrl={(fileId) => `${API}/portal/decision-rooms/${id}/media/${fileId}`}
      myDecisions={myDecisions} onSubmitDecision={onSubmitDecision}
      myQuestions={myQuestions} onSubmitQuestion={onSubmitQuestion}
      myOverlays={myOverlays} onAddOverlay={onAddOverlay} onWithdrawOverlay={onWithdrawOverlay}
      mySavedForLater={mySavedForLater} onSaveForLater={onSaveForLater}
    />
  );
}

