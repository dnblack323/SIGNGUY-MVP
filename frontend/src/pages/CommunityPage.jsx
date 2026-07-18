import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import EmptyState from "@/components/common/EmptyState";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Bug, Handshake, Heart, LifeBuoy, MessageSquare, Send, ShieldCheck, Sparkles, ThumbsUp } from "lucide-react";
import { toast } from "sonner";

const TAB_FROM_PATH = {
  "/help/bugs": "bugs",
  "/help/feature-requests": "features",
  "/help/contact": "support",
};

function Field({ label, children }) {
  return <div className="grid gap-1.5"><Label className="text-xs">{label}</Label>{children}</div>;
}

function SmallSelect({ value, onChange, children }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm">
      {children}
    </select>
  );
}

function RowCard({ title, meta, children, right }) {
  return (
    <div className="rounded border bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-medium truncate">{title}</div>
          {meta && <div className="text-xs text-muted-foreground">{meta}</div>}
        </div>
        {right}
      </div>
      {children && <div className="mt-2 text-sm text-slate-700">{children}</div>}
    </div>
  );
}

function useCommunityData() {
  const [data, setData] = useState({ loading: true, spaces: [], posts: [], features: [], bugs: [], support: [] });
  const load = useCallback(async () => {
    const [spaces, posts, features, bugs, support] = await Promise.all([
      api.get("/community/spaces"),
      api.get("/community/posts"),
      api.get("/community/feature-requests"),
      api.get("/community/bug-reports"),
      api.get("/community/support"),
    ]);
    setData({
      loading: false,
      spaces: spaces.data.items || [],
      posts: posts.data.items || [],
      features: features.data.items || [],
      bugs: bugs.data.items || [],
      support: support.data.items || [],
    });
  }, []);
  useEffect(() => { load().catch((e) => { setData((d) => ({ ...d, loading: false })); toast.error(extractError(e)); }); }, [load]);
  return { ...data, load };
}

function CommunityTab({ spaces, posts, load }) {
  const tenantSpaces = spaces.filter((s) => s.scope_type !== "founders");
  const [form, setForm] = useState({ space_id: "", title: "", body: "", post_type: "discussion" });
  const selectedSpace = form.space_id || tenantSpaces[0]?.id || "";
  async function submit(e) {
    e.preventDefault();
    try {
      await api.post("/community/posts", { ...form, space_id: selectedSpace });
      setForm({ space_id: selectedSpace, title: "", body: "", post_type: "discussion" });
      await load();
      toast.success("Post created");
    } catch (err) { toast.error(extractError(err)); }
  }
  async function vote(postId, active = true) {
    try {
      await api.post(`/community/posts/${postId}/vote`, { active });
      await load();
    } catch (err) { toast.error(extractError(err)); }
  }
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <form onSubmit={submit} className="rounded border bg-white p-3 space-y-3">
        <Field label="Space">
          <SmallSelect value={selectedSpace} onChange={(value) => setForm((f) => ({ ...f, space_id: value }))}>
            {tenantSpaces.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </SmallSelect>
        </Field>
        <Field label="Type">
          <SmallSelect value={form.post_type} onChange={(value) => setForm((f) => ({ ...f, post_type: value }))}>
            <option value="discussion">Discussion</option>
            <option value="question">Question</option>
            <option value="showcase">Showcase</option>
          </SmallSelect>
        </Field>
        <Field label="Title"><Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} required /></Field>
        <Field label="Body"><Textarea rows={5} value={form.body} onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))} required /></Field>
        <Button type="submit" disabled={!selectedSpace}><Send className="size-4 mr-1" />Post</Button>
      </form>
      <div className="space-y-3">
        {posts.length === 0 ? <EmptyState icon={MessageSquare} title="No community posts" /> : posts.map((p) => (
          <RowCard
            key={p.id}
            title={p.title}
            meta={`${p.post_type} - ${p.status} - ${p.comment_count || 0} comments`}
            right={<Button size="sm" variant="outline" onClick={() => vote(p.id, true)}><ThumbsUp className="size-4 mr-1" />{p.vote_count || 0}</Button>}
          >
            <p className="whitespace-pre-wrap">{p.body}</p>
            {p.pinned && <Badge className="mt-2" variant="secondary">Pinned</Badge>}
          </RowCard>
        ))}
      </div>
    </div>
  );
}

function FoundersTab({ spaces, posts }) {
  const founderSpaces = spaces.filter((s) => s.scope_type === "founders");
  const founderPosts = posts.filter((p) => p.scope_type === "founders");
  if (founderSpaces.length === 0) {
    return <EmptyState icon={Handshake} title="No founder spaces available" description="Founder access is granted explicitly by platform admins." />;
  }
  return (
    <div className="space-y-3">
      {founderSpaces.map((s) => <RowCard key={s.id} title={s.name} meta="Founder-only space">{s.description}</RowCard>)}
      {founderPosts.map((p) => <RowCard key={p.id} title={p.title} meta={`${p.comment_count || 0} comments`}>{p.body}</RowCard>)}
    </div>
  );
}

function FeaturesTab({ features, load }) {
  const [form, setForm] = useState({ title: "", description: "", category: "general" });
  async function submit(e) {
    e.preventDefault();
    try {
      await api.post("/community/feature-requests", form);
      setForm({ title: "", description: "", category: "general" });
      await load();
      toast.success("Feature request submitted");
    } catch (err) { toast.error(extractError(err)); }
  }
  async function vote(id) {
    try {
      await api.post(`/community/feature-requests/${id}/vote`, { active: true });
      await load();
    } catch (err) { toast.error(extractError(err)); }
  }
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <form onSubmit={submit} className="rounded border bg-white p-3 space-y-3">
        <Field label="Title"><Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} required /></Field>
        <Field label="Category"><Input value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} /></Field>
        <Field label="Description"><Textarea rows={5} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} required /></Field>
        <Button type="submit"><Sparkles className="size-4 mr-1" />Submit</Button>
      </form>
      <div className="space-y-3">
        {features.length === 0 ? <EmptyState icon={Sparkles} title="No feature requests" /> : features.map((f) => (
          <RowCard key={f.id} title={f.title} meta={`${f.category || "general"} - ${f.status}`} right={<Button size="sm" variant="outline" onClick={() => vote(f.id)}><ThumbsUp className="size-4 mr-1" />{f.vote_count || 0}</Button>}>
            <p>{f.description}</p>
            {f.staff_response && <p className="mt-2 rounded bg-slate-50 p-2 text-xs">{f.staff_response}</p>}
          </RowCard>
        ))}
      </div>
    </div>
  );
}

function BugsTab({ bugs, load }) {
  const [form, setForm] = useState({ title: "", description: "", severity: "medium", reproducibility: "" });
  async function submit(e) {
    e.preventDefault();
    try {
      await api.post("/community/bug-reports", form);
      setForm({ title: "", description: "", severity: "medium", reproducibility: "" });
      await load();
      toast.success("Bug report submitted");
    } catch (err) { toast.error(extractError(err)); }
  }
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <form onSubmit={submit} className="rounded border bg-white p-3 space-y-3">
        <Field label="Title"><Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} required /></Field>
        <Field label="Severity">
          <SmallSelect value={form.severity} onChange={(value) => setForm((f) => ({ ...f, severity: value }))}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </SmallSelect>
        </Field>
        <Field label="Reproducibility"><Input value={form.reproducibility} onChange={(e) => setForm((f) => ({ ...f, reproducibility: e.target.value }))} /></Field>
        <Field label="Description"><Textarea rows={5} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} required /></Field>
        <Button type="submit"><Bug className="size-4 mr-1" />Report bug</Button>
      </form>
      <div className="space-y-3">
        {bugs.length === 0 ? <EmptyState icon={Bug} title="No bug reports" /> : bugs.map((b) => (
          <RowCard key={b.id} title={b.title} meta={`${b.severity} - ${b.status}`}>
            <p>{b.description}</p>
            {b.staff_response && <p className="mt-2 rounded bg-slate-50 p-2 text-xs">{b.staff_response}</p>}
          </RowCard>
        ))}
      </div>
    </div>
  );
}

function SupportTab({ support, load }) {
  const [form, setForm] = useState({ request_type: "shop_configuration_question", subject: "", description: "" });
  const [route, setRoute] = useState(null);
  useEffect(() => {
    api.get("/community/support/route-preview", { params: { request_type: form.request_type } })
      .then((r) => setRoute(r.data))
      .catch(() => setRoute(null));
  }, [form.request_type]);
  async function submit(e) {
    e.preventDefault();
    try {
      await api.post("/community/support", form);
      setForm({ request_type: "shop_configuration_question", subject: "", description: "" });
      await load();
      toast.success("Support request created");
    } catch (err) { toast.error(extractError(err)); }
  }
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <form onSubmit={submit} className="rounded border bg-white p-3 space-y-3">
        <Field label="Request type">
          <SmallSelect value={form.request_type} onChange={(value) => setForm((f) => ({ ...f, request_type: value }))}>
            <option value="shop_configuration_question">Shop configuration question</option>
            <option value="internal_workflow_help">Internal workflow help</option>
            <option value="local_employee_access_help">Local employee access help</option>
            <option value="tenant_operational_issue">Tenant operational issue</option>
            <option value="product_bug">Product bug</option>
            <option value="feature_request">Feature request</option>
            <option value="login_platform_access_problem">Login or platform access</option>
            <option value="data_privacy_request">Privacy or data request</option>
          </SmallSelect>
        </Field>
        {route && <div className="rounded bg-slate-50 p-2 text-xs text-slate-600">Routes to: {route.destination_label}</div>}
        <Field label="Subject"><Input value={form.subject} onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))} required /></Field>
        <Field label="Description"><Textarea rows={5} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} required /></Field>
        <Button type="submit"><LifeBuoy className="size-4 mr-1" />Create request</Button>
      </form>
      <div className="space-y-3">
        {support.length === 0 ? <EmptyState icon={LifeBuoy} title="No support requests" /> : support.map((s) => (
          <RowCard key={s.id} title={s.subject} meta={`${s.request_type} - ${s.status}`} right={<Badge variant={s.destination_type === "platform_admin" ? "default" : "secondary"}>{s.destination_type === "platform_admin" ? "Platform" : "Tenant"}</Badge>}>
            <p>{s.description}</p>
          </RowCard>
        ))}
      </div>
    </div>
  );
}

export default function CommunityPage() {
  const location = useLocation();
  const initialTab = useMemo(() => TAB_FROM_PATH[location.pathname] || "community", [location.pathname]);
  const { loading, spaces, posts, features, bugs, support, load } = useCommunityData();
  if (loading) return <TableSkeleton />;
  return (
    <div className="space-y-4" data-testid="community-page">
      <PageHeader title="Community" subtitle="Shared shop community, founder access, feedback, bug reports, and support routing." />
      <Tabs defaultValue={initialTab} className="space-y-4">
        <TabsList className="flex flex-wrap justify-start">
          <TabsTrigger value="community"><MessageSquare className="size-4 mr-1" />Community</TabsTrigger>
          <TabsTrigger value="founders"><ShieldCheck className="size-4 mr-1" />Founders</TabsTrigger>
          <TabsTrigger value="bugs"><Bug className="size-4 mr-1" />Bugs</TabsTrigger>
          <TabsTrigger value="features"><Heart className="size-4 mr-1" />Features</TabsTrigger>
          <TabsTrigger value="support"><LifeBuoy className="size-4 mr-1" />Support</TabsTrigger>
        </TabsList>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">Workspace</CardTitle></CardHeader>
          <CardContent>
            <TabsContent value="community"><CommunityTab spaces={spaces} posts={posts} load={load} /></TabsContent>
            <TabsContent value="founders"><FoundersTab spaces={spaces} posts={posts} /></TabsContent>
            <TabsContent value="bugs"><BugsTab bugs={bugs} load={load} /></TabsContent>
            <TabsContent value="features"><FeaturesTab features={features} load={load} /></TabsContent>
            <TabsContent value="support"><SupportTab support={support} load={load} /></TabsContent>
          </CardContent>
        </Card>
      </Tabs>
    </div>
  );
}
