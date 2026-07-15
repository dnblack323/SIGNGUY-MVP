import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import portalApi, { portalExtractError } from "./portalApi";
import DecisionRoomCustomerView from "@/components/decisionRoom/DecisionRoomCustomerView";

/**
 * EC10 Phase 10E-1 — Customer Portal Decision Room detail (read-only).
 */
export default function PortalDecisionRoomPage() {
  const { id } = useParams();
  const [room, setRoom] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let live = true;
    portalApi.get(`/portal/decision-rooms/${id}`)
      .then((r) => live && setRoom(r.data))
      .catch((e) => live && setErr(portalExtractError(e, "This Decision Room is not available.")));
    return () => { live = false; };
  }, [id]);

  if (err) return <div className="p-6 text-sm text-rose-700" data-testid="portal-decision-room-error">{err}</div>;
  if (!room) return <div className="p-6 text-sm text-slate-500" data-testid="portal-decision-room-loading">Loading…</div>;
  return <DecisionRoomCustomerView room={room} />;
}
