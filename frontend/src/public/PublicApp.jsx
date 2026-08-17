import { useEffect, useState } from "react";
import { Route, Routes, useParams, useSearchParams } from "react-router-dom";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import DecisionRoomCustomerView from "@/components/decisionRoom/DecisionRoomCustomerView";
import PublicWebstorePage from "@/pages/PublicWebstorePage";
import { API_BASE } from "@/lib/apiBase";
import { centsToDollarsString } from "@/lib/format";

const API = API_BASE;

function useTokenIntrospect(t) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (!t) { setErr("Missing token"); return; }
    axios.get(`${API}/public/token/introspect`, { params: { t } })
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "Invalid or expired token"));
  }, [t]);
  return { data, err };
}

function ProofAction() {
  const { pid } = useParams();
  const [sp] = useSearchParams();
  const t = sp.get("t");
  const { data, err } = useTokenIntrospect(t);
  const [reason, setReason] = useState("");
  const [name, setName] = useState("");
  const [done, setDone] = useState(null);

  async function submit(action) {
    try {
      const r = await axios.post(
        `${API}/public/proofs/${pid}/action`,
        { action, reason: reason || undefined, signer_name: name || undefined },
        { params: { t } },
      );
      setDone(r.data);
      toast.success(action === "approve" ? "Proof approved" : "Changes requested");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Something went wrong");
    }
  }

  if (err) return <div className="p-6 max-w-lg mx-auto text-rose-700" data-testid="public-proof-err">{err}</div>;
  if (!data) return <div className="p-6 text-slate-500">Loading…</div>;
  if (done) return <div className="p-6 max-w-lg mx-auto" data-testid="public-proof-done"><Card><CardHeader><CardTitle>Thank you</CardTitle></CardHeader><CardContent>Your response has been recorded.</CardContent></Card></div>;

  return (
    <div className="min-h-screen bg-slate-50 grid place-items-center p-6" data-testid="public-proof-page">
      <Card className="max-w-lg w-full">
        <CardHeader><CardTitle>Proof approval</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="text-sm text-slate-600">Please review and take action on this proof.</div>
          <div className="grid gap-2"><Label>Your name</Label><Input value={name} onChange={(e) => setName(e.target.value)} data-testid="public-proof-name" /></div>
          <div className="grid gap-2"><Label>Notes (required if requesting changes)</Label><Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="public-proof-reason" /></div>
          <div className="flex gap-2">
            <Button className="flex-1" onClick={() => submit("approve")} data-testid="public-proof-approve">Approve</Button>
            <Button className="flex-1" variant="outline" onClick={() => submit("request_changes")} disabled={!reason.trim()} data-testid="public-proof-request-changes">Request changes</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function QuoteRequest() {
  const [sp] = useSearchParams();
  const [form, setForm] = useState({
    tenant_slug: sp.get("tenant") || "",
    contact_name: "", contact_email: "", contact_phone: "",
    company: "", project_title: "", project_description: "",
    consent_marketing: false,
  });
  const [ref, setRef] = useState(null);
  async function submit(e) {
    e.preventDefault();
    try {
      const r = await axios.post(`${API}/public/quote-request`, form);
      setRef(r.data.reference);
      toast.success("Quote request received");
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  }
  if (ref) return (
    <div className="p-6 max-w-lg mx-auto" data-testid="public-qr-done">
      <Card><CardHeader><CardTitle>Thank you!</CardTitle></CardHeader>
        <CardContent>Reference: <span className="font-mono">{ref}</span>. We'll be in touch shortly.</CardContent></Card>
    </div>
  );
  return (
    <div className="min-h-screen bg-slate-50 grid place-items-center p-6" data-testid="public-qr-page">
      <Card className="max-w-lg w-full">
        <CardHeader><CardTitle>Request a quote</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            {!sp.get("tenant") && <div className="grid gap-1.5"><Label>Tenant slug</Label><Input required value={form.tenant_slug} onChange={(e) => setForm({ ...form, tenant_slug: e.target.value })} data-testid="public-qr-tenant" /></div>}
            <div className="grid gap-1.5"><Label>Name</Label><Input required value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} data-testid="public-qr-name" /></div>
            <div className="grid gap-1.5"><Label>Email</Label><Input type="email" required value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} data-testid="public-qr-email" /></div>
            <div className="grid gap-1.5"><Label>Phone</Label><Input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} data-testid="public-qr-phone" /></div>
            <div className="grid gap-1.5"><Label>Company</Label><Input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} /></div>
            <div className="grid gap-1.5"><Label>Project title</Label><Input value={form.project_title} onChange={(e) => setForm({ ...form, project_title: e.target.value })} data-testid="public-qr-project" /></div>
            <div className="grid gap-1.5"><Label>Description</Label><Textarea rows={3} value={form.project_description} onChange={(e) => setForm({ ...form, project_description: e.target.value })} /></div>
            <Button type="submit" data-testid="public-qr-submit">Submit</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function PublicQuote() {
  const { qid } = useParams();
  const [sp] = useSearchParams();
  const t = sp.get("t");
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [name, setName] = useState("");
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const [done, setDone] = useState(null);

  function load() {
    if (!t) { setErr("Missing access link token."); return; }
    axios.get(`${API}/public/quotes/${qid}`, { params: { t } })
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "This quote is not available."));
  }

  useEffect(() => { load(); }, [qid, t]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(action) {
    try {
      const r = await axios.post(
        `${API}/public/quotes/${qid}/approval`,
        { action, reason: reason || undefined, comment: comment || undefined, signer_name: name || undefined },
        { params: { t } },
      );
      setDone(r.data);
      toast.success(action === "approve" ? "Quote approved" : "Quote declined");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Something went wrong");
    }
  }

  if (err) return <div className="min-h-screen bg-slate-50 grid place-items-center p-6"><div className="text-rose-700 text-sm max-w-md text-center" data-testid="public-quote-error">{err}</div></div>;
  if (!data) return <div className="min-h-screen bg-slate-50 grid place-items-center p-6 text-sm text-slate-500" data-testid="public-quote-loading">Loading…</div>;
  if (done) return (
    <div className="min-h-screen bg-slate-50 grid place-items-center p-6" data-testid="public-quote-done">
      <Card className="max-w-lg w-full"><CardHeader><CardTitle>Thank you</CardTitle></CardHeader><CardContent>Your quote response has been recorded.</CardContent></Card>
    </div>
  );

  const quote = data.quote || {};
  const items = data.line_items || [];
  const total = data.totals?.total_cents ?? quote.total_cents ?? 0;
  const actionable = ["sent", "viewed"].includes(quote.status) && !quote.expired;

  return (
    <div className="min-h-screen bg-slate-50 py-8 px-4" data-testid="public-quote-page">
      <div className="max-w-3xl mx-auto space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Quote Q-{quote.number}</CardTitle>
            <div className="text-sm text-slate-600">{quote.job_name} · Revision {quote.revision_number}</div>
          </CardHeader>
          <CardContent className="space-y-4">
            {quote.notes_customer && <div className="text-sm">{quote.notes_customer}</div>}
            <div className="rounded-md border divide-y" data-testid="public-quote-line-items">
              {items.map((item) => (
                <div key={item.id} className="grid grid-cols-[1fr_80px_120px] gap-2 p-3 text-sm">
                  <div>
                    <div className="font-medium">{item.description}</div>
                    <div className="text-xs text-slate-500">{item.quantity} {item.unit_of_measure || "each"}</div>
                  </div>
                  <div className="text-right">{centsToDollarsString(item.unit_price_cents || 0)}</div>
                  <div className="text-right font-medium">{centsToDollarsString(item.line_total_cents || 0)}</div>
                </div>
              ))}
              <div className="grid grid-cols-[1fr_120px] gap-2 p-3 text-sm font-semibold">
                <div className="text-right">Total</div>
                <div className="text-right" data-testid="public-quote-total">{centsToDollarsString(total)}</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Respond</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {!actionable && <div className="text-sm text-slate-600" data-testid="public-quote-not-actionable">This quote is no longer open for approval.</div>}
            <div className="grid gap-1.5">
              <Label>Your name</Label>
              <Input value={name} onChange={(event) => setName(event.target.value)} data-testid="public-quote-name" />
            </div>
            <div className="grid gap-1.5">
              <Label>Comment</Label>
              <Textarea rows={3} value={comment} onChange={(event) => setComment(event.target.value)} data-testid="public-quote-comment" />
            </div>
            <div className="grid gap-1.5">
              <Label>Decline reason</Label>
              <Textarea rows={2} value={reason} onChange={(event) => setReason(event.target.value)} data-testid="public-quote-reason" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={() => submit("approve")} disabled={!actionable} data-testid="public-quote-approve">Approve quote</Button>
              <Button type="button" variant="outline" onClick={() => submit("decline")} disabled={!actionable || !reason.trim()} data-testid="public-quote-decline">Decline quote</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function PublicWrapInspection() {
  const { inspectionId } = useParams();
  const [sp] = useSearchParams();
  const t = sp.get("t");
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [form, setForm] = useState({ signer_name: "", signer_email: "", signature_data: "" });
  const [done, setDone] = useState(null);

  function load() {
    if (!t) { setErr("Missing access link token."); return; }
    axios.get(`${API}/public/wrap-inspections/${inspectionId}`, { params: { t } })
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "This inspection review is not available."));
  }

  useEffect(() => { load(); }, [inspectionId, t]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit() {
    try {
      const r = await axios.post(`${API}/public/wrap-inspections/${inspectionId}/signature`, form, { params: { t } });
      setDone(r.data);
      toast.success("Inspection acknowledged");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Something went wrong");
    }
  }

  if (err) return <div className="min-h-screen bg-slate-50 grid place-items-center p-6"><div className="text-rose-700 text-sm max-w-md text-center" data-testid="public-wrap-inspection-error">{err}</div></div>;
  if (!data) return <div className="min-h-screen bg-slate-50 grid place-items-center p-6 text-sm text-slate-500" data-testid="public-wrap-inspection-loading">Loading...</div>;
  if (done) return (
    <div className="min-h-screen bg-slate-50 grid place-items-center p-6" data-testid="public-wrap-inspection-done">
      <Card className="max-w-lg w-full"><CardHeader><CardTitle>Thank you</CardTitle></CardHeader><CardContent>Your inspection acknowledgment has been recorded.</CardContent></Card>
    </div>
  );

  const project = data.project || {};
  const vehicle = data.vehicle || {};
  const inspection = data.inspection || {};
  const token = data.token || {};
  const completed = token.status === "completed" || inspection.status === "signed" || inspection.status === "completed";
  const actionable = !completed && ["active", "viewed"].includes(token.status);

  return (
    <div className="min-h-screen bg-slate-50 py-8 px-4" data-testid="public-wrap-inspection-page">
      <div className="max-w-3xl mx-auto space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Wrap inspection review</CardTitle>
            <div className="text-sm text-slate-600">{project.project_name} · Version {inspection.version}</div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{inspection.status}</Badge>
              <Badge variant="outline">{token.status}</Badge>
            </div>
            <div className="grid gap-2 rounded-md border p-3 text-sm md:grid-cols-2">
              <div><span className="text-slate-500">Vehicle:</span> {[vehicle.year, vehicle.make, vehicle.model].filter(Boolean).join(" ") || "Vehicle"}</div>
              <div><span className="text-slate-500">Coverage:</span> {project.coverage_summary || project.project_type || "Wrap project"}</div>
              <div><span className="text-slate-500">Inspection:</span> {String(inspection.inspection_type || "").replace(/_/g, " ")}</div>
              <div><span className="text-slate-500">Expires:</span> {token.expires_at ? String(token.expires_at).slice(0, 16) : "No date"}</div>
            </div>
            <div className="rounded-md border divide-y" data-testid="public-wrap-inspection-damage">
              {(inspection.damage_items || []).map((item, idx) => (
                <div key={`${item.panel || "panel"}-${idx}`} className="p-3 text-sm">
                  <div className="font-medium">{item.panel || "Vehicle area"} · {item.type || "condition"}</div>
                  <div className="text-xs text-slate-500">{item.severity || "not rated"}{item.notes ? ` · ${item.notes}` : ""}</div>
                </div>
              ))}
              {(!inspection.damage_items || inspection.damage_items.length === 0) && <div className="p-3 text-sm text-slate-500">No damage items were recorded for this inspection version.</div>}
            </div>
            <div className="text-xs text-slate-500">This page is pinned to the issued inspection version. Later addenda require a new link.</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Acknowledgment</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {completed && <div className="text-sm text-slate-600" data-testid="public-wrap-inspection-completed">This inspection version has already been signed.</div>}
            <div className="grid gap-1.5">
              <Label>Your name</Label>
              <Input value={form.signer_name} onChange={(event) => setForm({ ...form, signer_name: event.target.value })} data-testid="public-wrap-inspection-name" />
            </div>
            <div className="grid gap-1.5">
              <Label>Email</Label>
              <Input type="email" value={form.signer_email} onChange={(event) => setForm({ ...form, signer_email: event.target.value })} data-testid="public-wrap-inspection-email" />
            </div>
            <div className="grid gap-1.5">
              <Label>Typed signature</Label>
              <Input value={form.signature_data} onChange={(event) => setForm({ ...form, signature_data: event.target.value })} data-testid="public-wrap-inspection-signature" />
            </div>
            <Button type="button" onClick={submit} disabled={!actionable || !form.signer_name.trim() || !form.signature_data.trim()} data-testid="public-wrap-inspection-submit">Sign inspection</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/**
 * EC10 Phase 10E-1/10E-2/10E-3 — Public Token access to a published
 * Decision Room, including customer decision submission (select/reject/
 * reject-all/request-change), questions, anchored comments/pins, and
 * save-for-later.
 */
function PublicDecisionRoom() {
  const { rid } = useParams();
  const [sp] = useSearchParams();
  const t = sp.get("t");
  const [room, setRoom] = useState(null);
  const [myDecisions, setMyDecisions] = useState([]);
  const [myQuestions, setMyQuestions] = useState([]);
  const [myOverlays, setMyOverlays] = useState([]);
  const [mySavedForLater, setMySavedForLater] = useState([]);
  const [err, setErr] = useState(null);

  function load() {
    axios.get(`${API}/public/decision-rooms/${rid}`, { params: { t } })
      .then((r) => setRoom(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "This Decision Room is not available."));
    axios.get(`${API}/public/decision-rooms/${rid}/decisions`, { params: { t } }).then((r) => setMyDecisions(r.data.items || [])).catch(() => setMyDecisions([]));
    axios.get(`${API}/public/decision-rooms/${rid}/questions`, { params: { t } }).then((r) => setMyQuestions(r.data.items || [])).catch(() => setMyQuestions([]));
    axios.get(`${API}/public/decision-rooms/${rid}/overlays`, { params: { t } }).then((r) => setMyOverlays(r.data.items || [])).catch(() => setMyOverlays([]));
    axios.get(`${API}/public/decision-rooms/${rid}/save-for-later`, { params: { t } }).then((r) => setMySavedForLater(r.data.items || [])).catch(() => setMySavedForLater([]));
  }

  useEffect(() => {
    if (!t) { setErr("Missing access link token."); return; }
    load();
  }, [rid, t]); // eslint-disable-line react-hooks/exhaustive-deps

  async function onSubmitDecision({ action_type, option_id, comment }) {
    try {
      await axios.post(
        `${API}/public/decision-rooms/${rid}/decisions`,
        { action_type, option_id, comment, idempotency_key: `${crypto.randomUUID()}` },
        { params: { t } },
      );
      toast.success("Your response has been recorded");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Something went wrong");
      throw e;
    }
  }

  async function onSubmitQuestion({ customer_message, option_id }) {
    try {
      await axios.post(
        `${API}/public/decision-rooms/${rid}/questions`,
        { customer_message, option_id, idempotency_key: `${crypto.randomUUID()}` },
        { params: { t } },
      );
      toast.success("Your question has been sent");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Something went wrong");
      throw e;
    }
  }

  async function onAddOverlay({ overlay_type, normalized_x, normalized_y, customer_message, source_file_id }) {
    try {
      await axios.post(
        `${API}/public/decision-rooms/${rid}/overlays`,
        { overlay_type, normalized_x, normalized_y, customer_message, source_file_id, idempotency_key: `${crypto.randomUUID()}` },
        { params: { t } },
      );
      toast.success(overlay_type === "pin" ? "Pin added" : "Comment added");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Something went wrong");
      throw e;
    }
  }

  async function onWithdrawOverlay(overlayId) {
    try {
      await axios.post(`${API}/public/decision-rooms/${rid}/overlays/${overlayId}/withdraw`, {}, { params: { t } });
      toast.success("Withdrawn");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Something went wrong");
    }
  }

  async function onSaveForLater({ note }) {
    try {
      await axios.post(
        `${API}/public/decision-rooms/${rid}/save-for-later`,
        { note, idempotency_key: `${crypto.randomUUID()}` },
        { params: { t } },
      );
      toast.success("Saved for later — no selection was submitted");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Something went wrong");
      throw e;
    }
  }

  if (err) return <div className="min-h-screen bg-slate-50 grid place-items-center p-6"><div className="text-rose-700 text-sm max-w-md text-center" data-testid="public-decision-room-error">{err}</div></div>;
  if (!room) return <div className="min-h-screen bg-slate-50 grid place-items-center p-6 text-sm text-slate-500" data-testid="public-decision-room-loading">Loading…</div>;
  return (
    <div className="min-h-screen bg-slate-50 py-8 px-4">
      <div className="max-w-3xl mx-auto">
        <DecisionRoomCustomerView
          room={room} buildMediaUrl={(fileId) => `${API}/public/decision-rooms/${rid}/media/${fileId}?t=${t}`}
          myDecisions={myDecisions} onSubmitDecision={onSubmitDecision}
          myQuestions={myQuestions} onSubmitQuestion={onSubmitQuestion}
          myOverlays={myOverlays} onAddOverlay={onAddOverlay} onWithdrawOverlay={onWithdrawOverlay}
          mySavedForLater={mySavedForLater} onSaveForLater={onSaveForLater}
        />
      </div>
    </div>
  );
}

export default function PublicApp() {
  return (
    <Routes>
      <Route path="proofs/:pid" element={<ProofAction />} />
      <Route path="quotes/:qid" element={<PublicQuote />} />
      <Route path="wrap-inspections/:inspectionId" element={<PublicWrapInspection />} />
      <Route path="quote-request" element={<QuoteRequest />} />
      <Route path="decision-rooms/:rid" element={<PublicDecisionRoom />} />
      <Route path="webstores/:slug" element={<PublicWebstorePage />} />
    </Routes>
  );
}
