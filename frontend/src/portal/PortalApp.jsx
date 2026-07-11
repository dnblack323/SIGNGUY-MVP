import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { PortalAuthProvider, usePortalAuth } from "./PortalAuthContext";
import portalApi, { portalExtractError } from "./portalApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";

function Shell({ children }) {
  const { identity, logout } = usePortalAuth();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900" data-testid="portal-shell">
      <header className="border-b bg-white">
        <div className="max-w-5xl mx-auto flex items-center justify-between px-4 py-3">
          <Link to="/portal" className="font-semibold" data-testid="portal-logo">SignGuy Portal</Link>
          <nav className="flex gap-3 text-sm">
            <Link to="/portal/quotes" data-testid="portal-nav-quotes">Quotes</Link>
            <Link to="/portal/orders" data-testid="portal-nav-orders">Orders</Link>
            <Link to="/portal/invoices" data-testid="portal-nav-invoices">Invoices</Link>
            <Link to="/portal/proofs" data-testid="portal-nav-proofs">Proofs</Link>
            <Link to="/portal/documents" data-testid="portal-nav-documents">Documents</Link>
            <Link to="/portal/messages" data-testid="portal-nav-messages">Messages</Link>
            <Link to="/portal/profile" data-testid="portal-nav-profile">Profile</Link>
          </nav>
          <div className="flex items-center gap-2 text-xs">
            {identity && <span className="text-slate-600">{identity.full_name || identity.email}</span>}
            <Button size="sm" variant="outline" onClick={logout} data-testid="portal-logout">Logout</Button>
          </div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}

function Guard({ children }) {
  const { identity, loading } = usePortalAuth();
  const loc = useLocation();
  if (loading) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  if (!identity) return <Navigate to={`/portal/login?next=${encodeURIComponent(loc.pathname)}`} replace />;
  return <Shell>{children}</Shell>;
}

function LoginPage() {
  const { login, requestMagicLink } = usePortalAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  async function doLogin(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await login({ email, password, tenant_slug: tenantSlug || undefined });
      toast.success("Signed in"); nav("/portal");
    } catch (err) { toast.error(portalExtractError(err)); }
    setBusy(false);
  }
  async function doMagic() {
    if (!email) return toast.error("Enter your email first");
    try { await requestMagicLink({ email, tenant_slug: tenantSlug || undefined }); toast.success("Check your email for a sign-in link."); }
    catch (err) { toast.error(portalExtractError(err)); }
  }
  return (
    <div className="min-h-screen grid place-items-center bg-slate-50">
      <Card className="w-full max-w-sm" data-testid="portal-login-card">
        <CardHeader><CardTitle>Portal sign-in</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={doLogin} className="space-y-3">
            <div className="grid gap-1.5"><Label>Email</Label><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="portal-login-email" required /></div>
            <div className="grid gap-1.5"><Label>Password (optional)</Label><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="portal-login-password" /></div>
            <div className="grid gap-1.5"><Label className="text-xs text-slate-500">Tenant slug (if prompted)</Label><Input value={tenantSlug} onChange={(e) => setTenantSlug(e.target.value)} data-testid="portal-login-tenant" /></div>
            <Button type="submit" className="w-full" disabled={busy || !password} data-testid="portal-login-submit">Sign in with password</Button>
            <Button type="button" variant="outline" className="w-full" onClick={doMagic} data-testid="portal-login-magic">Email me a sign-in link</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function VerifyPage() {
  const { verifyMagicLink } = usePortalAuth();
  const nav = useNavigate();
  const [status, setStatus] = useState("verifying");
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("t");
    if (!t) { setStatus("invalid"); return; }
    verifyMagicLink(t).then(() => { setStatus("ok"); nav("/portal"); })
      .catch(() => setStatus("failed"));
  }, [verifyMagicLink, nav]);
  return (
    <div className="min-h-screen grid place-items-center p-6 text-sm" data-testid="portal-verify">
      {status === "verifying" && "Verifying your sign-in link…"}
      {status === "invalid" && "Missing token."}
      {status === "failed" && <span>That sign-in link is invalid or expired. <Link className="underline" to="/portal/login">Try again</Link></span>}
    </div>
  );
}

function useList(path) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    let live = true;
    portalApi.get(path).then((r) => live && setData(r.data)).catch((e) => live && setErr(portalExtractError(e)));
    return () => { live = false; };
  }, [path]);
  return { data, err };
}

function Dashboard() {
  const { identity } = usePortalAuth();
  return (
    <div className="space-y-4" data-testid="portal-dashboard">
      <h1 className="text-2xl font-semibold">Welcome, {identity?.full_name || identity?.email}</h1>
      <p className="text-slate-600 text-sm">Use the nav above to view quotes, orders, invoices, proofs and documents.</p>
    </div>
  );
}

function ListPage({ path, title, testId, cols }) {
  const { data, err } = useList(path);
  return (
    <div className="space-y-4" data-testid={testId}>
      <h1 className="text-xl font-semibold">{title}</h1>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      {!data ? <div className="text-sm text-slate-500">Loading…</div> :
        (data.items || []).length === 0 ? <div className="text-sm text-slate-500 italic">Nothing here yet.</div> : (
          <div className="rounded border bg-white divide-y">
            {data.items.map((it) => (
              <div key={it.id} className="p-3 text-sm flex items-center justify-between" data-testid={`${testId}-row-${it.id}`}>
                <div>
                  <div className="font-medium">{cols.title(it)}</div>
                  <div className="text-xs text-slate-500">{cols.sub(it)}</div>
                </div>
                <div className="text-xs text-slate-500">{cols.right(it)}</div>
              </div>
            ))}
          </div>
        )
      }
    </div>
  );
}

function Profile() {
  const { identity, refresh } = usePortalAuth();
  const [name, setName] = useState(identity?.full_name || "");
  const [phone, setPhone] = useState(identity?.phone || "");
  async function save() {
    try { await portalApi.patch("/portal/profile", { full_name: name, phone }); toast.success("Saved"); refresh(); }
    catch (e) { toast.error(portalExtractError(e)); }
  }
  return (
    <div className="space-y-4 max-w-lg" data-testid="portal-profile">
      <h1 className="text-xl font-semibold">Profile</h1>
      <div className="grid gap-2"><Label>Full name</Label><Input value={name} onChange={(e) => setName(e.target.value)} data-testid="portal-profile-name" /></div>
      <div className="grid gap-2"><Label>Phone</Label><Input value={phone} onChange={(e) => setPhone(e.target.value)} data-testid="portal-profile-phone" /></div>
      <Button onClick={save} data-testid="portal-profile-save">Save</Button>
    </div>
  );
}

export default function PortalApp() {
  return (
    <PortalAuthProvider>
      <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route path="verify" element={<VerifyPage />} />
        <Route path="" element={<Guard><Dashboard /></Guard>} />
        <Route path="quotes" element={<Guard><ListPage path="/portal/quotes" title="Quotes" testId="portal-quotes" cols={{title:(q)=>`Q-${q.number} · ${q.status}`, sub:(q)=>q.notes_customer||"", right:(q)=>`$${((q.total_cents||0)/100).toFixed(2)}`}} /></Guard>} />
        <Route path="orders" element={<Guard><ListPage path="/portal/orders" title="Orders" testId="portal-orders" cols={{title:(o)=>`O-${o.number} · ${o.status}`, sub:(o)=>o.job_name||"", right:(o)=>`$${((o.total_cents||0)/100).toFixed(2)}`}} /></Guard>} />
        <Route path="invoices" element={<Guard><ListPage path="/portal/invoices" title="Invoices" testId="portal-invoices" cols={{title:(i)=>`I-${i.number} · ${i.document_status}/${i.financial_status}`, sub:(i)=>i.title||"", right:(i)=>`Balance $${((i.balance_due_cents||0)/100).toFixed(2)}`}} /></Guard>} />
        <Route path="proofs" element={<Guard><ListPage path="/portal/proofs" title="Proofs" testId="portal-proofs" cols={{title:(p)=>`P-${p.number} · ${p.status}`, sub:(p)=>p.title||"", right:(p)=>`v${p.current_version}`}} /></Guard>} />
        <Route path="documents" element={<Guard><ListPage path="/portal/documents" title="Documents" testId="portal-documents" cols={{title:(d)=>d.title, sub:(d)=>d.category, right:(d)=>`v${d.version}`}} /></Guard>} />
        <Route path="messages" element={<Guard><ListPage path="/portal/messages" title="Messages" testId="portal-messages" cols={{title:(m)=>m.subject, sub:(m)=>m.status, right:(m)=>m.created_at?.slice(0,10)}} /></Guard>} />
        <Route path="profile" element={<Guard><Profile /></Guard>} />
      </Routes>
    </PortalAuthProvider>
  );
}
