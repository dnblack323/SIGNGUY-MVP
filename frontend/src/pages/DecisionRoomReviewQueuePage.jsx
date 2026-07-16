import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { CheckCircle2, Inbox, MessageSquarePlus, Search, UserRoundCheck } from "lucide-react";
import { relativeTime } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";

const ACTIVITY_TYPES = [
  ["all", "All activity"],
  ["option_selected", "Selected"],
  ["option_rejected", "Rejected option"],
  ["all_options_rejected", "Rejected all"],
  ["change_requested", "Change requests"],
  ["question", "Questions"],
  ["comment", "Comments"],
  ["pin", "Pins"],
  ["saved_for_later", "Saved"],
];

const STATUS_FILTERS = [
  ["all", "All statuses"],
  ["pending_review", "Pending review"],
  ["open", "Open"],
  ["answered", "Answered"],
  ["resolved", "Resolved"],
  ["reviewed", "Reviewed"],
  ["acknowledged", "Acknowledged"],
  ["superseded", "Superseded"],
  ["informational", "Informational"],
];

function titleFor(item) {
  return item.decision_room_title || item.decision_room_id || "Decision Room";
}

function describe(item) {
  const bits = [item.customer_name, item.option_label, item.proof_id && `Proof ${item.proof_id}`].filter(Boolean);
  return bits.length ? bits.join(" · ") : item.customer_id || item.source_access_mode || "Customer activity";
}

export default function DecisionRoomReviewQueuePage() {
  const { user, hasPerm } = useAuth();
  const canWrite = hasPerm("decision_room:write");
  const qc = useQueryClient();
  const [activityType, setActivityType] = useState("all");
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [unresolvedOnly, setUnresolvedOnly] = useState(true);
  const [noteDrafts, setNoteDrafts] = useState({});

  const queryParams = useMemo(() => ({
    activity_type: activityType === "all" ? undefined : activityType,
    status: status === "all" ? undefined : status,
    search: search || undefined,
    unresolved_only: unresolvedOnly,
    limit: 100,
  }), [activityType, status, search, unresolvedOnly]);

  const queue = useQuery({
    queryKey: ["decision-room-review-queue", queryParams],
    queryFn: async () => (await api.get("/decision-room-review-queue", { params: queryParams })).data,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["decision-room-review-queue"] });
  const onError = (err) => toast.error(extractError(err));

  const acknowledge = useMutation({
    mutationFn: async (item) => (await api.post(`/decision-room-review-queue/${item.record_type}/${item.record_id}/acknowledge`)).data,
    onSuccess: () => { invalidate(); toast.success("Review item updated"); },
    onError,
  });
  const assignToMe = useMutation({
    mutationFn: async (item) => (await api.post(`/decision-room-review-queue/${item.record_type}/${item.record_id}/assign`, { assigned_user_id: user?.id })).data,
    onSuccess: () => { invalidate(); toast.success("Assigned"); },
    onError,
  });
  const addNote = useMutation({
    mutationFn: async ({ item, note }) => (await api.post(`/decision-room-review-queue/${item.record_type}/${item.record_id}/notes`, { note })).data,
    onSuccess: (_data, vars) => {
      setNoteDrafts((prev) => ({ ...prev, [`${vars.item.record_type}:${vars.item.record_id}`]: "" }));
      toast.success("Note added");
    },
    onError,
  });
  const applyDecision = useMutation({
    mutationFn: async (item) => (await api.post(`/decision-rooms/${item.decision_room_id}/decisions/${item.record_id}/apply`, { note: "Applied from Decision Review Queue" })).data,
    onSuccess: () => { invalidate(); toast.success("Decision applied"); },
    onError,
  });

  const items = queue.data?.items || [];

  return (
    <div className="space-y-4" data-testid="decision-room-review-queue-page">
      <PageHeader
        title="Decision Review Queue"
        subtitle="Internal triage for Decision Room customer activity."
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-sm">
          <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search room, customer, option, message" className="pl-9" data-testid="decision-review-search" />
        </div>
        <Select value={activityType} onValueChange={setActivityType}>
          <SelectTrigger className="w-[190px]" data-testid="decision-review-activity-filter"><SelectValue /></SelectTrigger>
          <SelectContent>{ACTIVITY_TYPES.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-[180px]" data-testid="decision-review-status-filter"><SelectValue /></SelectTrigger>
          <SelectContent>{STATUS_FILTERS.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
        </Select>
        <Button variant={unresolvedOnly ? "default" : "outline"} size="sm" onClick={() => setUnresolvedOnly((v) => !v)} data-testid="decision-review-unresolved-toggle">
          Unresolved only
        </Button>
      </div>

      {queue.isLoading ? <TableSkeleton /> : items.length === 0 ? (
        <EmptyState icon={Inbox} title="No review items" description="Customer decisions, questions, pins, comments, and saved-for-later activity will appear here." />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="decision-review-table">
            <TableHeader><TableRow>
              <TableHead>Activity</TableHead>
              <TableHead>Room</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Submitted</TableHead>
              <TableHead>Assigned</TableHead>
              <TableHead className="w-[300px]">Internal note</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map((item) => {
                const key = `${item.record_type}:${item.record_id}`;
                const canAcknowledge = ["customer_decision", "overlay"].includes(item.record_type) && item.unresolved;
                const canApply = item.record_type === "customer_decision" && item.activity_type === "option_selected" && item.status !== "applied" && item.status !== "superseded";
                return (
                  <TableRow key={key} data-testid={`decision-review-row-${item.record_id}`}>
                    <TableCell className="align-top">
                      <div className="font-medium capitalize">{String(item.activity_type || item.record_type).replace(/_/g, " ")}</div>
                      <div className="text-xs text-muted-foreground max-w-[260px] truncate" title={item.customer_message || ""}>
                        {item.customer_message || describe(item)}
                      </div>
                    </TableCell>
                    <TableCell className="align-top">
                      <Link className="font-medium hover:underline" to={`/decision-rooms/${item.decision_room_id}`}>{titleFor(item)}</Link>
                      <div className="text-xs text-muted-foreground">{describe(item)}</div>
                    </TableCell>
                    <TableCell className="align-top"><StatusPill kind="decision_review_status" value={item.status} /></TableCell>
                    <TableCell className="align-top text-sm text-muted-foreground">{relativeTime(item.submitted_at)}</TableCell>
                    <TableCell className="align-top text-sm text-muted-foreground">{item.assigned_user_id || "Unassigned"}</TableCell>
                    <TableCell className="align-top">
                      <Textarea
                        value={noteDrafts[key] || ""}
                        onChange={(e) => setNoteDrafts((prev) => ({ ...prev, [key]: e.target.value }))}
                        rows={2}
                        placeholder="Staff-only note"
                        data-testid={`decision-review-note-${item.record_id}`}
                      />
                    </TableCell>
                    <TableCell className="align-top">
                      <div className="flex justify-end gap-2">
                        {canWrite && (
                          <Button size="icon" variant="outline" title="Assign to me" onClick={() => assignToMe.mutate(item)} data-testid={`decision-review-assign-${item.record_id}`}>
                            <UserRoundCheck className="size-4" />
                          </Button>
                        )}
                        {canWrite && (
                          <Button size="icon" variant="outline" title="Add internal note" disabled={!noteDrafts[key]?.trim()} onClick={() => addNote.mutate({ item, note: noteDrafts[key] })} data-testid={`decision-review-add-note-${item.record_id}`}>
                            <MessageSquarePlus className="size-4" />
                          </Button>
                        )}
                        {canWrite && canAcknowledge && (
                          <Button size="icon" title="Mark reviewed" onClick={() => acknowledge.mutate(item)} data-testid={`decision-review-ack-${item.record_id}`}>
                            <CheckCircle2 className="size-4" />
                          </Button>
                        )}
                        {canWrite && canApply && (
                          <Button size="sm" onClick={() => applyDecision.mutate(item)} data-testid={`decision-review-apply-${item.record_id}`}>
                            Apply
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
