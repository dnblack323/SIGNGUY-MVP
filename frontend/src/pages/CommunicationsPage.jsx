import { useCallback, useEffect, useState } from "react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { MessageSquare, NotebookPen, Send } from "lucide-react";
import { toast } from "sonner";

function Field({ label, children }) {
  return <div className="grid gap-1.5"><Label className="text-xs">{label}</Label>{children}</div>;
}

function Inbox() {
  const [threads, setThreads] = useState(null);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [compose, setCompose] = useState({ title: "", participant_user_ids: "", participant_employee_ids: "", body: "", visibility: "internal" });
  const [reply, setReply] = useState("");
  const load = useCallback(async () => {
    const { data } = await api.get("/communications/threads");
    setThreads(data.items || []);
    if (!selected && data.items?.[0]) setSelected(data.items[0]);
  }, [selected]);
  useEffect(() => { load().catch((e) => toast.error(extractError(e))); }, [load]);
  useEffect(() => {
    if (!selected?.id) return;
    api.get(`/communications/threads/${selected.id}/messages`).then((r) => setMessages(r.data.items || [])).catch((e) => toast.error(extractError(e)));
  }, [selected?.id]);
  async function createThread(e) {
    e.preventDefault();
    try {
      const payload = {
        thread_type: compose.participant_employee_ids ? "group" : "direct",
        title: compose.title,
        visibility: compose.visibility,
        participant_user_ids: compose.participant_user_ids.split(",").map((v) => v.trim()).filter(Boolean),
        participant_employee_ids: compose.participant_employee_ids.split(",").map((v) => v.trim()).filter(Boolean),
      };
      const { data } = await api.post("/communications/threads", payload);
      if (compose.body) await api.post(`/communications/threads/${data.id}/messages`, { body: compose.body });
      setCompose({ title: "", participant_user_ids: "", participant_employee_ids: "", body: "", visibility: "internal" });
      setSelected(data);
      await load();
    } catch (e2) { toast.error(extractError(e2)); }
  }
  async function sendReply(e) {
    e.preventDefault();
    if (!selected || !reply.trim()) return;
    try {
      await api.post(`/communications/threads/${selected.id}/messages`, { body: reply });
      setReply("");
      const { data } = await api.get(`/communications/threads/${selected.id}/messages`);
      setMessages(data.items || []);
      await load();
    } catch (e2) { toast.error(extractError(e2)); }
  }
  if (!threads) return <TableSkeleton />;
  return (
    <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
      <div className="space-y-3">
        <form onSubmit={createThread} className="rounded border bg-white p-3 space-y-2" data-testid="communications-compose-thread">
          <Field label="Thread title"><Input value={compose.title} onChange={(e) => setCompose((c) => ({ ...c, title: e.target.value }))} required /></Field>
          <Field label="Staff user IDs"><Input value={compose.participant_user_ids} onChange={(e) => setCompose((c) => ({ ...c, participant_user_ids: e.target.value }))} placeholder="comma-separated" /></Field>
          <Field label="Employee IDs"><Input value={compose.participant_employee_ids} onChange={(e) => setCompose((c) => ({ ...c, participant_employee_ids: e.target.value, visibility: e.target.value ? "employee_visible" : c.visibility }))} placeholder="comma-separated" /></Field>
          <Field label="First message"><Textarea rows={3} value={compose.body} onChange={(e) => setCompose((c) => ({ ...c, body: e.target.value }))} /></Field>
          <Button size="sm" type="submit"><MessageSquare className="size-4 mr-1" />Create thread</Button>
        </form>
        <div className="rounded border bg-white divide-y" data-testid="communications-thread-list">
          {threads.length === 0 ? <div className="p-3 text-sm text-slate-500">No threads.</div> : threads.map((t) => (
            <button key={t.id} className={`w-full text-left p-3 text-sm ${selected?.id === t.id ? "bg-slate-100" : ""}`} onClick={() => setSelected(t)}>
              <div className="font-medium truncate">{t.title}</div>
              <div className="text-xs text-slate-500 flex gap-2"><span>{t.thread_type}</span>{t.unread_count > 0 && <Badge>{t.unread_count}</Badge>}</div>
            </button>
          ))}
        </div>
      </div>
      <Card data-testid="communications-thread-detail">
        <CardHeader><CardTitle className="text-base">{selected?.title || "Select a thread"}</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {!selected ? <EmptyState title="No thread selected" /> : (
            <>
              <div className="space-y-2 max-h-[420px] overflow-auto">
                {messages.length === 0 ? <p className="text-sm text-slate-500 italic">No messages yet.</p> : messages.map((m) => (
                  <div key={m.id} className="rounded border p-2 text-sm">
                    <div className="text-xs text-slate-500">{m.sender_user_id ? "Staff" : "Employee"} · {new Date(m.created_at).toLocaleString()}</div>
                    <div className="whitespace-pre-wrap">{m.body}</div>
                  </div>
                ))}
              </div>
              <form onSubmit={sendReply} className="flex gap-2">
                <Input value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Reply" data-testid="communications-reply-input" />
                <Button type="submit"><Send className="size-4 mr-1" />Send</Button>
              </form>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Notes() {
  const [notes, setNotes] = useState(null);
  const [form, setForm] = useState({ title: "", body: "", visibility: "internal", task_id: "", order_id: "", work_order_id: "" });
  async function load() {
    const { data } = await api.get("/communications/notes");
    setNotes(data.items || []);
  }
  useEffect(() => { load().catch((e) => toast.error(extractError(e))); }, []);
  async function submit(e) {
    e.preventDefault();
    try {
      await api.post("/communications/notes", Object.fromEntries(Object.entries(form).filter(([, v]) => v !== "")));
      setForm({ title: "", body: "", visibility: "internal", task_id: "", order_id: "", work_order_id: "" });
      await load();
    } catch (e2) { toast.error(extractError(e2)); }
  }
  if (!notes) return <TableSkeleton />;
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <form onSubmit={submit} className="rounded border bg-white p-3 space-y-2" data-testid="communications-note-form">
        <Field label="Title"><Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} /></Field>
        <Field label="Body"><Textarea rows={4} required value={form.body} onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))} /></Field>
        <Field label="Visibility"><Input value={form.visibility} onChange={(e) => setForm((f) => ({ ...f, visibility: e.target.value }))} /></Field>
        <Field label="Task ID"><Input value={form.task_id} onChange={(e) => setForm((f) => ({ ...f, task_id: e.target.value }))} /></Field>
        <Field label="Order ID"><Input value={form.order_id} onChange={(e) => setForm((f) => ({ ...f, order_id: e.target.value }))} /></Field>
        <Field label="Work Order ID"><Input value={form.work_order_id} onChange={(e) => setForm((f) => ({ ...f, work_order_id: e.target.value }))} /></Field>
        <Button size="sm" type="submit"><NotebookPen className="size-4 mr-1" />Add note</Button>
      </form>
      <div className="rounded border bg-white divide-y" data-testid="communications-notes-list">
        {notes.length === 0 ? <div className="p-4 text-sm text-slate-500">No notes.</div> : notes.map((n) => (
          <div key={n.id} className="p-3 text-sm">
            <div className="flex items-center gap-2"><span className="font-medium">{n.title || "Untitled note"}</span><Badge variant="outline">{n.visibility}</Badge></div>
            <div className="mt-1 whitespace-pre-wrap">{n.body}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Digest() {
  const [digest, setDigest] = useState(null);
  useEffect(() => { api.get("/communications/digest/preview").then((r) => setDigest(r.data)).catch((e) => toast.error(extractError(e))); }, []);
  return (
    <Card data-testid="communications-digest">
      <CardHeader><CardTitle className="text-base">Daily Digest</CardTitle></CardHeader>
      <CardContent>
        {!digest ? <TableSkeleton /> : <pre className="text-xs bg-slate-50 border rounded p-3 overflow-auto">{JSON.stringify(digest.sections, null, 2)}</pre>}
      </CardContent>
    </Card>
  );
}

function Preferences() {
  const [prefs, setPrefs] = useState(null);
  useEffect(() => { api.get("/communications/preferences/me").then((r) => setPrefs(r.data)).catch((e) => toast.error(extractError(e))); }, []);
  async function save(next) {
    setPrefs(next);
    try { const { data } = await api.patch("/communications/preferences/me", next); setPrefs(data); }
    catch (e) { toast.error(extractError(e)); }
  }
  if (!prefs) return <TableSkeleton />;
  return (
    <Card data-testid="communications-preferences">
      <CardHeader><CardTitle className="text-base">Notification Preferences</CardTitle></CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {["in_app_messages", "task_notifications", "schedule_changes", "time_off_decisions", "appointment_reminders", "announcements", "daily_digest", "email_delivery"].map((key) => (
          <label key={key} className="flex items-center gap-2 text-sm">
            <Checkbox checked={!!prefs[key]} onCheckedChange={(v) => save({ ...prefs, [key]: !!v })} />
            {key.replaceAll("_", " ")}
          </label>
        ))}
        <Field label="Digest time"><Input value={prefs.digest_time || ""} onChange={(e) => setPrefs((p) => ({ ...p, digest_time: e.target.value }))} onBlur={() => save(prefs)} /></Field>
        <Field label="Quiet hours start"><Input value={prefs.quiet_hours?.start_time || ""} onChange={(e) => setPrefs((p) => ({ ...p, quiet_hours: { ...p.quiet_hours, start_time: e.target.value } }))} onBlur={() => save(prefs)} /></Field>
      </CardContent>
    </Card>
  );
}

export default function CommunicationsPage() {
  return (
    <div className="space-y-4" data-testid="communications-page">
      <PageHeader title="Messages & Notes" subtitle="Shared internal communication, linked notes, announcements, and digest." />
      <Tabs defaultValue="inbox">
        <TabsList>
          <TabsTrigger value="inbox">Inbox</TabsTrigger>
          <TabsTrigger value="notes">Notes</TabsTrigger>
          <TabsTrigger value="announcements">Announcements</TabsTrigger>
          <TabsTrigger value="digest">Digest</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
        </TabsList>
        <TabsContent value="inbox"><Inbox /></TabsContent>
        <TabsContent value="notes"><Notes /></TabsContent>
        <TabsContent value="announcements"><div className="rounded border bg-white p-4 text-sm">Announcements are managed from the existing Team Announcements page and included here through digest and notifications.</div></TabsContent>
        <TabsContent value="digest"><Digest /></TabsContent>
        <TabsContent value="preferences"><Preferences /></TabsContent>
      </Tabs>
    </div>
  );
}
