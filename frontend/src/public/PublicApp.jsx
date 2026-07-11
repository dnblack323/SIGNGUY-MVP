import { useEffect, useState } from "react";
import { Route, Routes, useParams, useSearchParams } from "react-router-dom";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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

export default function PublicApp() {
  return (
    <Routes>
      <Route path="proofs/:pid" element={<ProofAction />} />
      <Route path="quote-request" element={<QuoteRequest />} />
    </Routes>
  );
}
