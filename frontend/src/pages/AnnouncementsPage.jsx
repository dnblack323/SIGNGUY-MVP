import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { Megaphone, Plus, Send } from "lucide-react";
import { toast } from "sonner";
import { relativeTime } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";

function NewAnnouncementDialog({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", body: "" });
  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/announcements", { ...form, audience: "all" });
      toast.success("Announcement drafted");
      setOpen(false);
      setForm({ title: "", body: "" });
      onCreated?.(data);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button data-testid="announcements-create-button"><Plus className="size-4 mr-1" />New announcement</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>New announcement</DialogTitle>
          <DialogDescription>Drafted first — publish when ready to notify the team.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5"><Label>Title*</Label><Input required value={form.title} onChange={upd("title")} data-testid="announcement-title-input" /></div>
          <div className="grid gap-1.5"><Label>Message*</Label><Textarea required rows={4} value={form.body} onChange={upd("body")} data-testid="announcement-body-input" /></div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy} data-testid="announcement-submit-button">{busy ? "Saving…" : "Save draft"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function AnnouncementsPage() {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canManage = hasPerm("employee:manage");
  const { data, isLoading, error } = useQuery({
    queryKey: ["announcements"],
    queryFn: async () => (await api.get("/announcements")).data,
  });
  const items = data?.items || [];

  async function publish(id) {
    try {
      await api.post(`/announcements/${id}/publish`);
      toast.success("Announcement published");
      qc.invalidateQueries({ queryKey: ["announcements"] });
    } catch (err) { toast.error(extractError(err)); }
  }

  return (
    <div className="space-y-4" data-testid="announcements-page">
      <PageHeader title="Announcements" subtitle="Broadcast news to your team." actions={canManage && <NewAnnouncementDialog onCreated={() => qc.invalidateQueries({ queryKey: ["announcements"] })} />} />
      {isLoading ? <TableSkeleton /> : error ? (
        <EmptyState title="Couldn’t load announcements" description="Please try again." />
      ) : items.length === 0 ? (
        <EmptyState icon={Megaphone} title="No announcements yet" description="Create your first team announcement." action={canManage ? <NewAnnouncementDialog onCreated={() => qc.invalidateQueries({ queryKey: ["announcements"] })} /> : null} />
      ) : (
        <div className="rounded-xl border bg-card divide-y" data-testid="announcements-list">
          {items.map((a) => (
            <div key={a.id} className="p-4 flex items-start justify-between gap-3" data-testid={`announcement-row-${a.id}`}>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <div className="font-medium">{a.title}</div>
                  <StatusPill kind="announcement" value={a.status} />
                </div>
                <div className="text-sm text-muted-foreground mt-1 whitespace-pre-wrap">{a.body}</div>
                <div className="text-xs text-muted-foreground mt-1">{a.status === "published" ? `Published ${relativeTime(a.published_at)}` : `Drafted ${relativeTime(a.created_at)}`}</div>
              </div>
              {canManage && a.status === "draft" && (
                <Button size="sm" variant="outline" onClick={() => publish(a.id)} data-testid={`announcement-publish-${a.id}`}>
                  <Send className="size-3.5 mr-1" />Publish
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
