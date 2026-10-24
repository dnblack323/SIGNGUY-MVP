import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAssistantSavedRecord } from "@/lib/businessAssistant";
import { extractError } from "@/lib/api";

export default function SavedActionRecord({ proposalId, identity }) {
  const [state, setState] = useState({ identity, proposalId, record: null, error: "" });
  useEffect(() => {
    let active = true;
    getAssistantSavedRecord(proposalId).then((record) => { if (active) setState({ identity, proposalId, record, error: "" }); }).catch((err) => { if (active) setState({ identity, proposalId, record: null, error: extractError(err, "Saved record is unavailable") }); });
    return () => { active = false; };
  }, [identity, proposalId]);
  const current = state.identity === identity && state.proposalId === proposalId ? state : {};
  return <section className="rounded border bg-background p-4 space-y-2" data-testid="assistant-saved-record">
    <h2 className="font-semibold">Saved application record</h2>
    {current.error && <p role="alert">{current.error}</p>}
    {current.record ? <><h3>{current.record.subject || current.record.title}</h3><p className="whitespace-pre-wrap">{current.record.content}</p>{current.record.due_at && <p>Due: {current.record.due_at}</p>}{current.record.sent === false && <p>Draft saved. No email was sent.</p>}<p className="text-xs">Record ID: {current.record.id}</p>{current.record.destinations.map((ref) => <Link className="underline mr-2" key={ref.id} to={ref.route}>{ref.label}</Link>)}</> : !current.error && <p>Loading actual saved record…</p>}
  </section>;
}
