import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import portalApi, { API, portalExtractError } from "./portalApi";
import DecisionRoomCustomerView from "@/components/decisionRoom/DecisionRoomCustomerView";

/**
 * EC10 Phase 10E-1/10E-2 — Customer Portal Decision Room detail.
 */
export default function PortalDecisionRoomPage() {
  const { id } = useParams();
  const [room, setRoom] = useState(null);
  const [myDecisions, setMyDecisions] = useState([]);
  const [err, setErr] = useState(null);

  function load() {
    portalApi.get(`/portal/decision-rooms/${id}`)
      .then((r) => setRoom(r.data))
      .catch((e) => setErr(portalExtractError(e, "This Decision Room is not available.")));
    portalApi.get(`/portal/decision-rooms/${id}/decisions`)
      .then((r) => setMyDecisions(r.data.items || []))
      .catch(() => setMyDecisions([]));
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

  if (err) return <div className="p-6 text-sm text-rose-700" data-testid="portal-decision-room-error">{err}</div>;
  if (!room) return <div className="p-6 text-sm text-slate-500" data-testid="portal-decision-room-loading">Loading…</div>;
  return (
    <DecisionRoomCustomerView
      room={room}
      authToken={localStorage.getItem("sg_portal_token")}
      buildMediaUrl={(fileId) => `${API}/portal/decision-rooms/${id}/media/${fileId}`}
      myDecisions={myDecisions}
      onSubmitDecision={onSubmitDecision}
    />
  );
}

