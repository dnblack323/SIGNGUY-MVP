import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cancelAssistantProposal, confirmAssistantProposal, editAssistantProposal, executeAssistantProposal } from "@/lib/businessAssistant";
import { extractError } from "@/lib/api";

export default function ActionProposal({ proposal, onUpdated }) {
  const [draft, setDraft] = useState(proposal.editable_payload || {});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setDraft(proposal.editable_payload || {}); }, [proposal.id, proposal.revision, proposal.editable_payload]);
  const editable = ["internal_task", "internal_note", "email_draft"].includes(proposal.action_type) && ["proposed", "edited", "confirmed"].includes(proposal.status);
  const dirty = JSON.stringify(draft) !== JSON.stringify(proposal.editable_payload || {});
  const change = (key) => (event) => setDraft((old) => ({ ...old, [key]: event.target.value || (key === "due_at" ? null : "") }));
  const act = async (kind) => {
    if (busy) return;
    setBusy(true); setError("");
    try {
      let next;
      if (kind === "edit") next = await editAssistantProposal(proposal.id, { revision: proposal.revision, editable_payload: draft });
      else if (kind === "confirm") next = await confirmAssistantProposal(proposal.id, proposal.revision);
      else if (kind === "cancel") next = await cancelAssistantProposal(proposal.id);
      else {
        const receipt = await executeAssistantProposal(proposal.id, `assistant-exec-${proposal.id}`);
        next = { ...proposal, status: receipt.status, result: receipt.canonical_result, failure_reason: receipt.failure_reason };
      }
      await onUpdated?.(next);
    } catch (err) { setError(extractError(err, "Unable to complete this action. Reload its current status before retrying.")); }
    finally { setBusy(false); }
  };
  return <Card data-testid="assistant-action-proposal" className="border-amber-300">
    <CardHeader><CardTitle className="text-base">{proposal.title} · {proposal.status}</CardTitle></CardHeader>
    <CardContent className="space-y-3">
      <p>{proposal.summary}</p>
      <p className="text-sm">{proposal.action_type === "email_draft" ? "Save one draft only. No email will be sent." : "Creates one application record only after interface confirmation."}</p>
      <div>{(proposal.target_refs || []).map((ref) => <p key={`${ref.type}:${ref.id}`}>Destination: {ref.route ? <Link className="underline" to={ref.route}>{ref.label || ref.type}</Link> : ref.label || ref.id}</p>)}</div>
      {proposal.action_type === "internal_task" && <p>Shop timezone: {draft.timezone || "shown in the saved due date"}. Date-only tasks use 9am.</p>}
      {editable ? <div className="space-y-2">
        <label className="block">Title<Input aria-label="Action title" value={draft.title || ""} onChange={change("title")} /></label>
        {proposal.action_type === "email_draft" && <label className="block">Subject<Input aria-label="Draft subject" value={draft.subject || ""} onChange={change("subject")} /></label>}
        <label className="block">{proposal.action_type === "email_draft" ? "Professional draft" : "Exact content"}<Textarea aria-label="Action content" value={draft.body || ""} onChange={change("body")} /></label>
        {proposal.action_type === "internal_task" && <><label className="block">Due date/time (shop timezone; date-only means 9am)<Input aria-label="Task due date" value={draft.due_at || ""} onChange={change("due_at")} placeholder="tomorrow or ISO date/time" /></label><label className="block">Priority<select aria-label="Task priority" value={draft.priority || "normal"} onChange={change("priority")}>{["low", "normal", "high", "rush"].map((value) => <option key={value}>{value}</option>)}</select></label></>}
        {dirty && <Button onClick={() => act("edit")} disabled={busy}>Save preview changes</Button>}
      </div> : <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(proposal.editable_payload || proposal.preview || {}, null, 2)}</pre>}
      <p className="text-xs">Preview expires after 30 minutes. Confirmation expires after 5 minutes. Editing removes the previous confirmation.</p>
      {(proposal.warnings || []).map((warning) => <p className="text-xs" key={warning}>{warning}</p>)}
      {error && <p role="alert">{error}</p>}
      {proposal.failure_reason && <p role="alert">{proposal.failure_reason}</p>}
      {proposal.result?.assistant_summary && <p role="status">{proposal.result.assistant_summary}</p>}
      {proposal.result?.route && <Link className="underline" to={proposal.result.route}>Open saved record</Link>}
      <div className="flex gap-2">
        {["proposed", "edited"].includes(proposal.status) && <Button disabled={busy || dirty} onClick={() => act("confirm")}>Confirm this preview</Button>}
        {proposal.status === "confirmed" && <Button disabled={busy || dirty} onClick={() => act("execute")}>Create confirmed record</Button>}
        {["failed", "executing"].includes(proposal.status) && <Button variant="outline" disabled={busy} onClick={() => act("execute")}>Check saved outcome</Button>}
        {["proposed", "edited", "confirmed"].includes(proposal.status) && <Button variant="outline" disabled={busy} onClick={() => act("cancel")}>Cancel</Button>}
      </div>
    </CardContent>
  </Card>;
}
