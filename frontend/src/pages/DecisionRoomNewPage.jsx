import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

/**
 * EC10 Phase 10D — create a Decision Room in `draft` status. Commercial/
 * intake context (quote/order/order item/intake) is optional here and can
 * be attached/changed later while still a draft — the backend validates
 * every reference against the tenant regardless.
 */
export default function DecisionRoomNewPage() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [title, setTitle] = useState("");
  const [internalName, setInternalName] = useState("");
  const [customerSafeIntro, setCustomerSafeIntro] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [quoteId, setQuoteId] = useState("");
  const [orderId, setOrderId] = useState("");
  const [intakeId, setIntakeId] = useState("");
  const [expirationAt, setExpirationAt] = useState("");
  const [requireInternalAcceptance, setRequireInternalAcceptance] = useState(true);
  const [allowSaveForLater, setAllowSaveForLater] = useState(false);
  const [allowComments, setAllowComments] = useState(false);
  const [allowQuestions, setAllowQuestions] = useState(false);
  const [allowChangeRequests, setAllowChangeRequests] = useState(false);
  const [allowRejectAll, setAllowRejectAll] = useState(false);

  const { data: customers } = useQuery({ queryKey: ["customers", "all"], queryFn: async () => (await api.get("/customers", { params: { limit: 200 } })).data });
  const { data: quotes } = useQuery({ queryKey: ["quotes", "all"], queryFn: async () => (await api.get("/quotes", { params: { limit: 200 } })).data });
  const { data: orders } = useQuery({ queryKey: ["orders", "all"], queryFn: async () => (await api.get("/orders", { params: { limit: 200 } })).data });

  async function create() {
    if (!title.trim()) { toast.error("Title is required"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/decision-rooms", {
        title, internal_name: internalName || undefined, customer_safe_intro: customerSafeIntro || undefined,
        customer_id: customerId || undefined, quote_id: quoteId || undefined, order_id: orderId || undefined,
        intake_id: intakeId || undefined, expiration_at: expirationAt || undefined,
        require_internal_acceptance: requireInternalAcceptance, allow_save_for_later: allowSaveForLater,
        allow_customer_comments: allowComments, allow_customer_questions: allowQuestions, allow_change_requests: allowChangeRequests,
        allow_reject_all: allowRejectAll,
      });
      toast.success("Decision Room created as draft");
      navigate(`/decision-rooms/${data.id}`);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-4" data-testid="decision-room-new-page">
      <PageHeader title="New Decision Room" subtitle="Internal authoring only — no customer sees this yet." />
      <div className="rounded-xl border bg-card p-4 grid gap-3">
        <div className="grid gap-1.5"><Label>Title</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} data-testid="decision-room-title-input" /></div>
        <div className="grid gap-1.5"><Label>Internal name (staff only)</Label><Input value={internalName} onChange={(e) => setInternalName(e.target.value)} data-testid="decision-room-internal-name-input" /></div>
        <div className="grid gap-1.5"><Label>Customer-safe introduction</Label><Textarea rows={2} value={customerSafeIntro} onChange={(e) => setCustomerSafeIntro(e.target.value)} data-testid="decision-room-intro-input" /></div>

        <div className="grid grid-cols-2 gap-3">
          <div className="grid gap-1.5">
            <Label>Customer</Label>
            <Select value={customerId || "__none__"} onValueChange={(v) => setCustomerId(v === "__none__" ? "" : v)}>
              <SelectTrigger data-testid="decision-room-customer-select"><SelectValue placeholder="Select a customer" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">None yet</SelectItem>
                {customers?.items?.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Expiration date</Label><Input type="date" value={expirationAt} onChange={(e) => setExpirationAt(e.target.value)} data-testid="decision-room-expiration-input" /></div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="grid gap-1.5">
            <Label>Quote (optional)</Label>
            <Select value={quoteId || "__none__"} onValueChange={(v) => setQuoteId(v === "__none__" ? "" : v)}>
              <SelectTrigger data-testid="decision-room-quote-select"><SelectValue placeholder="None" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">None</SelectItem>
                {quotes?.items?.map((q) => <SelectItem key={q.id} value={q.id}>Q-{q.number}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label>Order (optional)</Label>
            <Select value={orderId || "__none__"} onValueChange={(v) => setOrderId(v === "__none__" ? "" : v)}>
              <SelectTrigger data-testid="decision-room-order-select"><SelectValue placeholder="None" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">None</SelectItem>
                {orders?.items?.map((o) => <SelectItem key={o.id} value={o.id}>O-{o.number}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Intake id (optional)</Label><Input value={intakeId} onChange={(e) => setIntakeId(e.target.value)} placeholder="Intake submission id" data-testid="decision-room-intake-input" /></div>
        </div>

        <div className="grid grid-cols-2 gap-2 pt-2">
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={requireInternalAcceptance} onCheckedChange={(v) => setRequireInternalAcceptance(!!v)} data-testid="decision-room-require-acceptance-checkbox" />Require internal acceptance before a decision applies</label>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={allowSaveForLater} onCheckedChange={(v) => setAllowSaveForLater(!!v)} data-testid="decision-room-allow-save-checkbox" />Allow save for later</label>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={allowComments} onCheckedChange={(v) => setAllowComments(!!v)} data-testid="decision-room-allow-comments-checkbox" />Allow customer comments</label>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={allowQuestions} onCheckedChange={(v) => setAllowQuestions(!!v)} data-testid="decision-room-allow-questions-checkbox" />Allow customer questions</label>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={allowChangeRequests} onCheckedChange={(v) => setAllowChangeRequests(!!v)} data-testid="decision-room-allow-change-requests-checkbox" />Allow customer change requests</label>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={allowRejectAll} onCheckedChange={(v) => setAllowRejectAll(!!v)} data-testid="decision-room-allow-reject-all-checkbox" />Allow customer to reject all options</label>
        </div>
        <p className="text-xs text-muted-foreground">Select/reject/reject-all/change-request are live (Phase 10E-2). Save for later and comments/questions have no effect yet (Phase 10E-3).</p>
      </div>
      <div className="flex justify-end">
        <Button disabled={busy} onClick={create} data-testid="decision-room-create-button">Create draft</Button>
      </div>
    </div>
  );
}
