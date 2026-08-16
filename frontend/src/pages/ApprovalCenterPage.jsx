import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, MessageSquareReply, Plus, Search } from "lucide-react";
import { toast } from "sonner";

import api, { extractError } from "@/lib/api";
import DecisionRoomsPage from "@/pages/DecisionRoomsPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import ApprovalTargetSelector, { APPROVAL_TARGET_TYPES, approvalTargetTypeLabel } from "@/components/approvals/ApprovalTargetSelector";

function ApprovalWorkDialog({ open, onOpenChange, initialTarget, onCreated }) {
  const navigate = useNavigate();
  const [targetType, setTargetType] = useState(initialTarget?.target_type || "quote");
  const [selectedTarget, setSelectedTarget] = useState(initialTarget || null);
  const [title, setTitle] = useState(initialTarget?.title || "");
  const [intro, setIntro] = useState("");
  const [allowComments, setAllowComments] = useState(true);
  const [allowQuestions, setAllowQuestions] = useState(true);
  const [allowChanges, setAllowChanges] = useState(true);

  useEffect(() => {
    if (initialTarget) {
      setTargetType(initialTarget.target_type || "quote");
      setSelectedTarget(initialTarget);
      setTitle(initialTarget.title || initialTarget.label || "");
    }
  }, [initialTarget]);

  const createWork = useMutation({
    mutationFn: async () => (await api.post("/approval-center/work", {
      target_type: selectedTarget?.target_type || targetType,
      target_id: selectedTarget?.id,
      title: title || selectedTarget?.label,
      customer_safe_intro: intro || null,
      allow_customer_comments: allowComments,
      allow_customer_questions: allowQuestions,
      allow_change_requests: allowChanges,
      allow_reject_all: false,
    })).data,
    onSuccess: (room) => {
      toast.success("Approval work created");
      onCreated?.();
      onOpenChange(false);
      navigate(`/decision-rooms/${room.id}`);
    },
    onError: (error) => toast.error(extractError(error)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px]" data-testid="approval-work-dialog">
        <DialogHeader>
          <DialogTitle>Create approval work</DialogTitle>
          <DialogDescription>
            Select the commercial record once; the Decision Room keeps the linked customer, quote, order, or item context.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-2 sm:grid-cols-[180px_1fr]">
            <div className="grid gap-1.5">
              <Label>Target type</Label>
              <Select
                value={targetType}
                onValueChange={(value) => {
                  setTargetType(value);
                  setSelectedTarget(null);
                }}
              >
                <SelectTrigger data-testid="approval-target-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {APPROVAL_TARGET_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <ApprovalTargetSelector
            targetType={targetType}
            selectedTarget={selectedTarget}
            onSelect={(target) => {
              setSelectedTarget(target);
              if (!title) setTitle(target.label);
            }}
            enabled={open}
            testIdPrefix="approval-target"
          />
          <div className="grid gap-1.5">
            <Label>Approval title</Label>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} data-testid="approval-work-title" />
          </div>
          <div className="grid gap-1.5">
            <Label>Customer-safe intro</Label>
            <Textarea rows={3} value={intro} onChange={(event) => setIntro(event.target.value)} />
          </div>
          <div className="grid gap-2 text-sm sm:grid-cols-3">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={allowComments} onChange={(event) => setAllowComments(event.target.checked)} />
              Comments
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={allowQuestions} onChange={(event) => setAllowQuestions(event.target.checked)} />
              Questions
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={allowChanges} onChange={(event) => setAllowChanges(event.target.checked)} />
              Change requests
            </label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            onClick={() => createWork.mutate()}
            disabled={!selectedTarget?.id || createWork.isPending}
            data-testid="approval-work-create"
          >
            Create Decision Room
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AuthorityQueue() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("all");
  const [unresolvedOnly, setUnresolvedOnly] = useState(true);
  const [newOpen, setNewOpen] = useState(false);
  const [searchParams] = useSearchParams();

  const initialTarget = useMemo(() => {
    const targetType = searchParams.get("target_type");
    const targetId = searchParams.get("target_id");
    if (!targetType || !targetId) return null;
    return {
      id: targetId,
      target_type: targetType,
      label: searchParams.get("title") || targetId,
      title: searchParams.get("title") || "",
      customer_id: searchParams.get("customer_id") || undefined,
    };
  }, [searchParams]);

  useEffect(() => {
    if (searchParams.get("new") === "1") setNewOpen(true);
  }, [searchParams]);

  const queue = useQuery({
    queryKey: ["approval-center-authority-queue", search, kind, unresolvedOnly],
    queryFn: async () => (await api.get("/approval-center/queue", {
      params: {
        search: search || undefined,
        kind: kind === "all" ? undefined : kind,
        unresolved_only: unresolvedOnly,
      },
    })).data,
  });

  const applyDecision = useMutation({
    mutationFn: async (item) => (await api.post(
      `/decision-rooms/${item.decision_room_id}/decisions/${item.record_id}/apply`,
      {},
    )).data,
    onSuccess: () => {
      toast.success("Decision applied");
      qc.invalidateQueries({ queryKey: ["approval-center-authority-queue"] });
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const acknowledgeReview = useMutation({
    mutationFn: async (item) => (await api.post(`/decision-room-review-queue/${item.record_type}/${item.record_id}/acknowledge`, {})).data,
    onSuccess: () => {
      toast.success("Review item updated");
      qc.invalidateQueries({ queryKey: ["approval-center-authority-queue"] });
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const respondQuestion = useMutation({
    mutationFn: async ({ item, staff_response }) => (await api.post(
      `/decision-rooms/${item.decision_room_id}/questions/${item.record_id}/respond`,
      { staff_response },
    )).data,
    onSuccess: () => {
      toast.success("Response saved");
      qc.invalidateQueries({ queryKey: ["approval-center-authority-queue"] });
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const resolveQuestion = useMutation({
    mutationFn: async (item) => (await api.post(`/decision-rooms/${item.decision_room_id}/questions/${item.record_id}/resolve`, {})).data,
    onSuccess: () => {
      toast.success("Question resolved");
      qc.invalidateQueries({ queryKey: ["approval-center-authority-queue"] });
    },
    onError: (error) => toast.error(extractError(error)),
  });
  const transitionProof = useMutation({
    mutationFn: async ({ item, target, reason }) => (await api.post(
      `/proofs/${item.record_id}/transition`,
      { target, reason: reason || null },
    )).data,
    onSuccess: () => {
      toast.success("Proof updated");
      qc.invalidateQueries({ queryKey: ["approval-center-authority-queue"] });
    },
    onError: (error) => toast.error(extractError(error)),
  });

  const items = queue.data?.items || [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative w-80 max-w-full">
            <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
            <Input
              className="pl-8"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search approvals, rooms, customers, or messages"
              data-testid="approval-queue-search"
            />
          </div>
          <Select value={kind} onValueChange={setKind}>
            <SelectTrigger className="w-48" data-testid="approval-queue-kind">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All approval work</SelectItem>
              <SelectItem value="approval_record">Approval records</SelectItem>
              <SelectItem value="decision_room_activity">Decision Room activity</SelectItem>
              <SelectItem value="signature_request">Signature requests</SelectItem>
              <SelectItem value="proof">Proofs</SelectItem>
            </SelectContent>
          </Select>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={unresolvedOnly}
              onChange={(event) => setUnresolvedOnly(event.target.checked)}
              data-testid="approval-queue-unresolved"
            />
            Unresolved only
          </label>
        </div>
        <Button onClick={() => setNewOpen(true)} data-testid="approval-center-new-work">
          <Plus className="size-4 mr-1" /> New approval work
        </Button>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Authority Queue</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="approval-authority-queue">
              <thead className="text-left text-xs text-muted-foreground border-b">
                <tr>
                  <th className="py-2 pr-3 font-medium">Activity</th>
                  <th className="py-2 pr-3 font-medium">Target</th>
                  <th className="py-2 pr-3 font-medium">Customer</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Submitted</th>
                  <th className="py-2 pr-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr><td colSpan={6} className="py-6 text-center text-muted-foreground">No approval work found.</td></tr>
                ) : items.map((item) => (
                  <tr key={item.id} className="border-b last:border-0">
                    <td className="py-2 pr-3">
                      <div className="font-medium">{item.title}</div>
                      <div className="text-xs text-muted-foreground">{item.queue_type.replaceAll("_", " ")} · {item.activity_type}</div>
                      {item.source_summary && <div className="text-xs text-muted-foreground">{item.source_summary}</div>}
                    </td>
                    <td className="py-2 pr-3">
                      <div>{approvalTargetTypeLabel(item.target_type)}</div>
                      <div className="text-xs text-muted-foreground">{item.target_id || item.record_id}</div>
                    </td>
                    <td className="py-2 pr-3">{item.customer_name || item.customer_id || "—"}</td>
                    <td className="py-2 pr-3"><Badge variant="outline">{item.status || "open"}</Badge></td>
                    <td className="py-2 pr-3 text-muted-foreground">{item.submitted_at ? String(item.submitted_at).slice(0, 16) : "—"}</td>
                    <td className="py-2 pr-3">
                      <div className="flex justify-end gap-2">
                        {item.queue_type === "decision_room_activity" && item.record_type === "customer_decision" && item.activity_type === "option_selected" && item.status !== "applied" && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => applyDecision.mutate(item)}
                            disabled={applyDecision.isPending}
                            data-testid={`approval-queue-apply-${item.record_id}`}
                          >
                            <CheckCircle2 className="size-4 mr-1" /> Apply
                          </Button>
                        )}
                        {item.queue_type === "decision_room_activity" && ["customer_decision", "overlay"].includes(item.record_type) && item.unresolved && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => acknowledgeReview.mutate(item)}
                            disabled={acknowledgeReview.isPending}
                            data-testid={`approval-queue-acknowledge-${item.record_id}`}
                          >
                            Review
                          </Button>
                        )}
                        {item.queue_type === "decision_room_activity" && item.record_type === "question" && item.unresolved && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                const staff_response = window.prompt("Customer-safe response");
                                if (staff_response?.trim()) respondQuestion.mutate({ item, staff_response: staff_response.trim() });
                              }}
                              disabled={respondQuestion.isPending}
                              data-testid={`approval-queue-respond-${item.record_id}`}
                            >
                              <MessageSquareReply className="size-4 mr-1" /> Respond
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => resolveQuestion.mutate(item)}
                              disabled={resolveQuestion.isPending}
                              data-testid={`approval-queue-resolve-${item.record_id}`}
                            >
                              Resolve
                            </Button>
                          </>
                        )}
                        {item.queue_type === "proof" && ["sent", "viewed"].includes(item.status) && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => transitionProof.mutate({ item, target: "approved" })}
                              disabled={transitionProof.isPending}
                              data-testid={`approval-queue-proof-approve-${item.record_id}`}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                const reason = window.prompt("Reason for requested changes");
                                if (reason?.trim()) transitionProof.mutate({ item, target: "changes_requested", reason: reason.trim() });
                              }}
                              disabled={transitionProof.isPending}
                              data-testid={`approval-queue-proof-changes-${item.record_id}`}
                            >
                              Changes
                            </Button>
                          </>
                        )}
                        <Button asChild size="sm" variant="ghost">
                          <Link to={item.source_url || "/approval-center"}>
                            <ExternalLink className="size-4 mr-1" /> Open
                          </Link>
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <ApprovalWorkDialog
        open={newOpen}
        onOpenChange={setNewOpen}
        initialTarget={initialTarget}
        onCreated={() => qc.invalidateQueries({ queryKey: ["approval-center-authority-queue"] })}
      />
    </div>
  );
}

export default function ApprovalCenterPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") === "decision-rooms" ? "decision-rooms" : "approval-queue";
  return (
    <div className="space-y-4" data-testid="approval-center-page">
      <Tabs
        value={tab}
        onValueChange={(next) => setSearchParams(next === "decision-rooms" ? { tab: "decision-rooms" } : { tab: "queue" })}
        data-testid="approval-center-tabs"
      >
        <TabsList>
          <TabsTrigger value="approval-queue" data-testid="approval-center-tab-queue">Approval Queue</TabsTrigger>
          <TabsTrigger value="decision-rooms" data-testid="approval-center-tab-decision-rooms">Decision Rooms</TabsTrigger>
        </TabsList>
        <TabsContent value="approval-queue">
          <AuthorityQueue />
        </TabsContent>
        <TabsContent value="decision-rooms">
          <DecisionRoomsPage />
        </TabsContent>
      </Tabs>
    </div>
  );
}
