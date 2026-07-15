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
import FileAttachmentPicker from "@/components/intake/FileAttachmentPicker";
import IntakeItemForm from "@/components/intake/IntakeItemForm";
import { toast } from "sonner";
import { Plus, Trash2, Copy, LayoutList, LayoutGrid } from "lucide-react";
import { blankIntakeItem, INTAKE_SOURCE_TYPES, INTAKE_PRIORITIES } from "@/lib/intake";

export default function IntakeNewPage() {
  const navigate = useNavigate();
  const [detailed, setDetailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const [customerId, setCustomerId] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [sourceType, setSourceType] = useState("internal_user");
  const [priority, setPriority] = useState("normal");
  const [assignedUserId, setAssignedUserId] = useState("");
  const [requestedDueDate, setRequestedDueDate] = useState("");
  const [installationRequired, setInstallationRequired] = useState(false);
  const [installationLocation, setInstallationLocation] = useState("");
  const [installationNotes, setInstallationNotes] = useState("");
  const [customerNotes, setCustomerNotes] = useState("");
  const [internalNotes, setInternalNotes] = useState("");
  const [fileIds, setFileIds] = useState([]);
  const [questionnaireIds, setQuestionnaireIds] = useState([]);
  const [questionnaireInput, setQuestionnaireInput] = useState("");
  const [items, setItems] = useState([blankIntakeItem()]);

  const { data: customers } = useQuery({
    queryKey: ["customers", "all"],
    queryFn: async () => (await api.get("/customers", { params: { limit: 200 } })).data,
  });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: async () => (await api.get("/users")).data });

  function updateItem(idx, next) {
    setItems((arr) => arr.map((it, i) => (i === idx ? next : it)));
  }
  function addItem() { setItems((arr) => [...arr, blankIntakeItem()]); }
  function removeItem(idx) { setItems((arr) => arr.filter((_, i) => i !== idx)); }
  function duplicateItem(idx) {
    setItems((arr) => {
      const src = arr[idx];
      return [...arr, { ...src, _localId: `local-${Math.random().toString(36).slice(2)}` }];
    });
  }
  function addQuestionnaireRef() {
    if (questionnaireInput.trim()) {
      setQuestionnaireIds((ids) => [...ids, questionnaireInput.trim()]);
      setQuestionnaireInput("");
    }
  }

  function buildPayload() {
    return {
      source_type: sourceType, customer_id: customerId || undefined,
      contact_name: contactName || undefined, contact_email: contactEmail || undefined, contact_phone: contactPhone || undefined,
      project_name: projectName || undefined, project_description: projectDescription || undefined,
      priority, assigned_user_id: assignedUserId || undefined, requested_due_date: requestedDueDate || undefined,
      installation_required: installationRequired, installation_location: installationLocation || undefined,
      installation_notes: installationNotes || undefined, customer_notes: customerNotes || undefined,
      internal_notes: internalNotes || undefined, file_ids: fileIds, questionnaire_submission_ids: questionnaireIds,
      items: items.map(({ _localId, ...rest }) => rest),
    };
  }

  async function saveDraft() {
    setBusy(true);
    try {
      const { data } = await api.post("/intake", buildPayload());
      toast.success(`Intake IN-${data.intake_number} saved as draft`);
      navigate(`/intake/${data.id}`);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  async function submitForReview() {
    setBusy(true);
    try {
      const { data } = await api.post("/intake", buildPayload());
      await api.post(`/intake/${data.id}/transition`, { target: "submitted" });
      toast.success(`Intake IN-${data.intake_number} submitted for review`);
      navigate(`/intake/${data.id}`);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-4" data-testid="intake-new-page">
      <PageHeader
        title="New Intake" subtitle="Capture a request before it becomes a Quote or Order."
        actions={
          <Button variant="outline" onClick={() => setDetailed((d) => !d)} data-testid="intake-toggle-detailed-button">
            {detailed ? <LayoutList className="size-4 mr-1" /> : <LayoutGrid className="size-4 mr-1" />}
            {detailed ? "Switch to Quick" : "Switch to Detailed"}
          </Button>
        }
      />

      <div className="rounded-xl border bg-card p-4 grid gap-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="grid gap-1.5">
            <Label>Customer</Label>
            <Select value={customerId || "__none__"} onValueChange={(v) => setCustomerId(v === "__none__" ? "" : v)}>
              <SelectTrigger data-testid="intake-customer-select"><SelectValue placeholder="Existing customer (optional)" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">No customer — unlinked contact</SelectItem>
                {customers?.items?.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label>Source</Label>
            <Select value={sourceType} onValueChange={setSourceType}>
              <SelectTrigger data-testid="intake-source-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {INTAKE_SOURCE_TYPES.map((s) => <SelectItem key={s} value={s}>{s.replace(/_/g, " ")}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        {!customerId && (
          <div className="grid grid-cols-3 gap-3">
            <div className="grid gap-1.5"><Label>Contact name</Label><Input value={contactName} onChange={(e) => setContactName(e.target.value)} data-testid="intake-contact-name-input" /></div>
            <div className="grid gap-1.5"><Label>Contact email</Label><Input type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} data-testid="intake-contact-email-input" /></div>
            <div className="grid gap-1.5"><Label>Contact phone</Label><Input value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} data-testid="intake-contact-phone-input" /></div>
          </div>
        )}

        <div className="grid gap-1.5"><Label>Project name</Label><Input value={projectName} onChange={(e) => setProjectName(e.target.value)} data-testid="intake-project-name-input" /></div>
        <div className="grid gap-1.5"><Label>Project description</Label><Textarea rows={2} value={projectDescription} onChange={(e) => setProjectDescription(e.target.value)} data-testid="intake-project-description-input" /></div>

        <div className="grid grid-cols-3 gap-3">
          <div className="grid gap-1.5">
            <Label>Priority</Label>
            <Select value={priority} onValueChange={setPriority}>
              <SelectTrigger data-testid="intake-priority-select"><SelectValue /></SelectTrigger>
              <SelectContent>{INTAKE_PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label>Assigned to</Label>
            <Select value={assignedUserId || "__none__"} onValueChange={(v) => setAssignedUserId(v === "__none__" ? "" : v)}>
              <SelectTrigger data-testid="intake-assigned-user-select"><SelectValue placeholder="Unassigned" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Unassigned</SelectItem>
                {(users || []).map((u) => <SelectItem key={u.id} value={u.id}>{u.name || u.email}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5"><Label>Requested due date</Label><Input type="date" value={requestedDueDate} onChange={(e) => setRequestedDueDate(e.target.value)} data-testid="intake-due-date-input" /></div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="grid gap-1.5"><Label>Customer notes</Label><Textarea rows={2} value={customerNotes} onChange={(e) => setCustomerNotes(e.target.value)} data-testid="intake-customer-notes-input" /></div>
          <div className="grid gap-1.5"><Label>Internal notes</Label><Textarea rows={2} value={internalNotes} onChange={(e) => setInternalNotes(e.target.value)} data-testid="intake-internal-notes-input" /></div>
        </div>

        {detailed && (
          <>
            <div className="grid gap-1.5">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={installationRequired} onCheckedChange={(v) => setInstallationRequired(!!v)} data-testid="intake-installation-required-checkbox" />
                Installation required
              </label>
            </div>
            {installationRequired && (
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-1.5"><Label>Installation location</Label><Input value={installationLocation} onChange={(e) => setInstallationLocation(e.target.value)} data-testid="intake-installation-location-input" /></div>
                <div className="grid gap-1.5"><Label>Installation notes</Label><Input value={installationNotes} onChange={(e) => setInstallationNotes(e.target.value)} data-testid="intake-installation-notes-input" /></div>
              </div>
            )}
            <div className="grid gap-1.5">
              <Label>Intake-level files</Label>
              <FileAttachmentPicker fileIds={fileIds} onChange={setFileIds} testIdPrefix="intake-level-files" />
            </div>
            <div className="grid gap-1.5">
              <Label>Questionnaire submission references</Label>
              <div className="flex flex-wrap items-center gap-2">
                {questionnaireIds.map((id) => (
                  <span key={id} className="rounded-full bg-muted px-2.5 py-1 text-xs" data-testid={`intake-questionnaire-ref-${id}`}>{id}</span>
                ))}
                <Input className="w-56" value={questionnaireInput} onChange={(e) => setQuestionnaireInput(e.target.value)} placeholder="Questionnaire submission id" data-testid="intake-questionnaire-ref-input" />
                <Button type="button" size="sm" variant="outline" onClick={addQuestionnaireRef} data-testid="intake-questionnaire-ref-add-button">Add</Button>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="rounded-xl border bg-card p-4 grid gap-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm">Items ({items.length})</h3>
          <Button type="button" size="sm" variant="outline" onClick={addItem} data-testid="intake-add-item-button"><Plus className="size-4 mr-1" />Add another item</Button>
        </div>
        {items.map((item, idx) => (
          <div key={item._localId} className="relative">
            <IntakeItemForm item={item} onChange={(next) => updateItem(idx, next)} detailed={detailed} testIdPrefix={`intake-new-item-${idx}`} />
            <div className="absolute top-3 right-3 flex gap-1">
              <Button type="button" size="icon" variant="ghost" onClick={() => duplicateItem(idx)} data-testid={`intake-new-item-${idx}-duplicate-button`}><Copy className="size-4" /></Button>
              {items.length > 1 && (
                <Button type="button" size="icon" variant="ghost" onClick={() => removeItem(idx)} data-testid={`intake-new-item-${idx}-remove-button`}><Trash2 className="size-4" /></Button>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" disabled={busy} onClick={saveDraft} data-testid="intake-save-draft-button">Save Draft</Button>
        <Button type="button" disabled={busy} onClick={submitForReview} data-testid="intake-submit-for-review-button">Submit for Review</Button>
      </div>
    </div>
  );
}
