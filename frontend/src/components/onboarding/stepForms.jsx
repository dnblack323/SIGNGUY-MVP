import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Save } from "lucide-react";
import { toast } from "sonner";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

/**
 * Inline controls for Quick Start steps. Every form reads and writes the
 * feature that owns the data (settings, Pricing Foundation, employees,
 * production workflows, customers, orders) — onboarding keeps no copy.
 */

const HEX = /^#(?:[0-9a-fA-F]{3}){1,2}$/;

function Field({ label, children, hint }) {
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      {children}
      {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

function SaveBar({ busy, label = "Save and continue", disabled }) {
  return (
    <Button type="submit" disabled={busy || disabled} className="w-fit" data-testid="onboarding-save">
      <Save className="size-4 mr-2" />{busy ? "Saving…" : label}
    </Button>
  );
}

// Run a save, confirm it, then hand control back so the page can refresh and advance.
function useSaver(onSaved) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const run = async (fn, message) => {
    setBusy(true);
    setError(null);
    try {
      const result = await fn();
      toast.success(message);
      await onSaved?.(result);
    } catch (err) {
      const text = extractError(err);
      setError(text);
      toast.error(text);
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, run };
}

function FormError({ error }) {
  return error ? <div role="alert" className="text-sm text-destructive" data-testid="onboarding-form-error">{error}</div> : null;
}

function useNamespace(namespace) {
  const q = useQuery({ queryKey: ["settings-namespace", namespace], queryFn: async () => (await api.get(`/settings/${namespace}`)).data?.values || {} });
  return q;
}

function useDraft(source, keys) {
  const [draft, setDraft] = useState({});
  useEffect(() => {
    if (source) setDraft(Object.fromEntries(keys.map((k) => [k, source[k] ?? ""])));
    // keys is a static literal per form
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);
  return [draft, (k) => (e) => setDraft((d) => ({ ...d, [k]: e?.target ? e.target.value : e })), setDraft];
}

// Never send blanks: a blank box must not wipe a value saved elsewhere in Settings.
const filled = (obj) => Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, typeof v === "string" ? v.trim() : v]).filter(([, v]) => v !== "" && v != null));

function SettingsForm({ namespace, fields, validate, onSaved, message, label }) {
  const ns = useNamespace(namespace);
  const keys = fields.map((f) => f.key);
  const [draft, bind] = useDraft(ns.data, keys);
  const { busy, error, run } = useSaver(onSaved);
  const [problem, setProblem] = useState(null);
  const submit = (e) => {
    e.preventDefault();
    const values = filled(draft);
    const invalid = validate?.(values);
    setProblem(invalid || null);
    if (invalid) return;
    if (!Object.keys(values).length) { setProblem("Enter at least one value to save."); return; }
    run(async () => {
      const res = await api.put(`/settings/${namespace}`, values);
      await ns.refetch();
      return res.data;
    }, message);
  };
  return (
    <form onSubmit={submit} className="grid gap-3 md:grid-cols-2" data-testid={`onboarding-form-${namespace}`}>
      {fields.map((f) => (
        <Field key={f.key} label={f.label} hint={f.hint}>
          {f.type === "textarea" ? (
            <Textarea rows={3} value={draft[f.key] ?? ""} onChange={bind(f.key)} />
          ) : (
            <Input value={draft[f.key] ?? ""} onChange={bind(f.key)} placeholder={f.placeholder} />
          )}
        </Field>
      ))}
      <div className="md:col-span-2 grid gap-2">
        <FormError error={problem || error} />
        <SaveBar busy={busy} label={label} />
      </div>
    </form>
  );
}

const COMPANY = [
  { key: "shop_name", label: "Shop name" },
  { key: "legal_name", label: "Legal name", hint: "Optional. Used on invoices if different from the shop name." },
];
const CONTACT = [
  { key: "phone", label: "Phone" },
  { key: "email", label: "Business email" },
  { key: "website", label: "Website" },
  { key: "address_line1", label: "Street address" },
  { key: "city", label: "City" },
  { key: "state", label: "State / Region" },
  { key: "postal_code", label: "Postal code" },
];

export function CompanyForm({ onSaved }) {
  return (
    <SettingsForm
      namespace="company_profile" fields={COMPANY} onSaved={onSaved} message="Business information saved"
      validate={(v) => (v.shop_name || v.legal_name ? null : "Enter a shop name or legal name.")}
    />
  );
}

export function ContactForm({ onSaved }) {
  return (
    <SettingsForm
      namespace="company_profile" fields={CONTACT} onSaved={onSaved} message="Contact details saved"
      validate={(v) => {
        if (v.email && !/^\S+@\S+\.\S+$/.test(v.email)) return "Enter a valid email address.";
        if (!v.address_line1) return "Street address is required to finish this step.";
        if (!v.phone && !v.email) return "Add a phone number or an email address.";
        return null;
      }}
    />
  );
}

export function BrandingForm({ onSaved }) {
  return (
    <SettingsForm
      namespace="branding" onSaved={onSaved} message="Branding saved"
      fields={[
        { key: "primary_color", label: "Brand color (hex)", placeholder: "#1d4ed8" },
        { key: "email_signature", label: "Email signature", type: "textarea" },
      ]}
      validate={(v) => (v.primary_color && !HEX.test(v.primary_color) ? "Brand color must be a hex value like #1d4ed8." : null)}
    />
  );
}

export function PaymentPrefsForm({ onSaved }) {
  return (
    <SettingsForm
      namespace="invoicing_defaults" onSaved={onSaved} message="Payment preferences saved"
      fields={[
        { key: "payment_terms", label: "Default payment terms", placeholder: "e.g. 50% deposit, balance due on delivery" },
        { key: "invoice_footer", label: "Invoice footer note", type: "textarea" },
      ]}
    />
  );
}

function ToggleForm({ namespace, toggles, onSaved, message }) {
  const ns = useNamespace(namespace);
  const { busy, error, run } = useSaver(onSaved);
  const [draft, setDraft] = useState({});
  useEffect(() => {
    if (ns.data) setDraft(Object.fromEntries(toggles.map((t) => [t.key, ns.data[t.key] ?? t.default])));
    // toggles is a static literal per form
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ns.data]);
  return (
    <form
      className="grid gap-3"
      data-testid={`onboarding-form-${namespace}`}
      onSubmit={(e) => { e.preventDefault(); run(async () => { await api.put(`/settings/${namespace}`, draft); await ns.refetch(); }, message); }}
    >
      {toggles.map((t) => (
        <div key={t.key} className="flex items-center justify-between gap-4 rounded-md border p-3">
          <div>
            <div className="text-sm font-medium">{t.label}</div>
            <div className="text-xs text-muted-foreground">{t.hint}</div>
          </div>
          <Switch checked={!!draft[t.key]} onCheckedChange={(v) => setDraft((d) => ({ ...d, [t.key]: v }))} aria-label={t.label} />
        </div>
      ))}
      <FormError error={error} />
      <SaveBar busy={busy} />
    </form>
  );
}

export function PortalPrefsForm({ onSaved }) {
  return (
    <ToggleForm
      namespace="portal" onSaved={onSaved} message="Portal preferences saved"
      toggles={[
        { key: "enabled", label: "Enable the customer portal", hint: "Customers can sign in to review their orders.", default: true },
        { key: "allow_proof_approvals", label: "Proof approvals", hint: "Customers approve artwork online.", default: true },
        { key: "allow_invoice_payments", label: "Invoice payments", hint: "Needs a payment provider later; harmless to leave on.", default: false },
      ]}
    />
  );
}

export function NotificationsForm({ onSaved }) {
  return (
    <ToggleForm
      namespace="notifications" onSaved={onSaved} message="Notification preferences saved"
      toggles={[
        { key: "notify_proof_approvals", label: "Proof approvals and changes", hint: "Tell the team when a customer responds to a proof.", default: true },
        { key: "notify_payments", label: "Payments received", hint: "Tell the team when an invoice is paid.", default: true },
        { key: "notify_portal_messages", label: "Customer messages", hint: "Tell the team about new portal messages.", default: true },
      ]}
    />
  );
}

const RATE_FIELDS = [
  { key: "production_hourly_rate", label: "Production labor ($/hr)" },
  { key: "design_hourly_rate", label: "Design labor ($/hr)" },
  { key: "install_hourly_rate", label: "Installation labor ($/hr)" },
  { key: "default_markup_multiplier", label: "Default markup multiplier", hint: "1.0 = no markup. 2.0 = double cost." },
  { key: "deposit_percentage", label: "Deposit (%)", hint: "Share of an order asked up front." },
];

export function LaborRatesForm({ onSaved }) {
  const pricing = useQuery({ queryKey: ["pricing-settings"], queryFn: async () => (await api.get("/pricing/settings")).data });
  const [draft, bind] = useDraft(pricing.data?.shop_defaults, RATE_FIELDS.map((f) => f.key));
  const { busy, error, run } = useSaver(onSaved);
  const [problem, setProblem] = useState(null);
  const submit = (e) => {
    e.preventDefault();
    const body = {};
    for (const f of RATE_FIELDS) {
      const raw = String(draft[f.key] ?? "").trim();
      if (raw === "") continue;
      const n = Number(raw);
      if (!Number.isFinite(n) || n < 0) { setProblem(`${f.label} must be a positive number.`); return; }
      if (f.key === "default_markup_multiplier" && n < 1) { setProblem("Markup multiplier must be at least 1."); return; }
      if (f.key === "deposit_percentage" && n > 100) { setProblem("Deposit cannot exceed 100%."); return; }
      body[f.key] = n;
    }
    if (!Object.keys(body).some((k) => k.endsWith("_hourly_rate"))) { setProblem("Enter at least one hourly labor rate."); return; }
    setProblem(null);
    run(async () => { const res = await api.patch("/pricing/settings/shop-defaults", body); await pricing.refetch(); return res.data; }, "Labor and pricing basics saved to Pricing Foundation");
  };
  return (
    <form onSubmit={submit} className="grid gap-3 md:grid-cols-2" data-testid="onboarding-form-labor-rates">
      {RATE_FIELDS.map((f) => (
        <Field key={f.key} label={f.label} hint={f.hint}>
          <Input inputMode="decimal" value={draft[f.key] ?? ""} onChange={bind(f.key)} />
        </Field>
      ))}
      <div className="md:col-span-2 grid gap-2">
        <FormError error={problem || error} />
        <SaveBar busy={busy} />
      </div>
    </form>
  );
}

export function WorkflowForm({ onSaved }) {
  const workflows = useQuery({ queryKey: ["onboarding-workflows"], queryFn: async () => (await api.get("/production-workflows")).data?.items || [] });
  const qc = useQueryClient();
  const items = workflows.data || [];
  const current = items.find((w) => w.is_tenant_default);
  // Listing workflows seeds the shop's starter set, so progress must be re-read once it loads.
  useEffect(() => {
    if (workflows.isSuccess) qc.invalidateQueries({ queryKey: ["onboarding-dashboard"] });
  }, [workflows.isSuccess, qc]);
  const [choice, setChoice] = useState(null);
  const selected = items.find((w) => w.id === (choice || current?.id));
  const { busy, error, run } = useSaver(onSaved);
  if (workflows.isLoading) return <div className="text-sm text-muted-foreground">Loading workflows…</div>;
  return (
    <form
      className="grid gap-3" data-testid="onboarding-form-workflow"
      onSubmit={(e) => { e.preventDefault(); run(async () => { await api.post(`/production-workflows/${selected.id}/set-default`); await workflows.refetch(); }, "Default production workflow saved"); }}
    >
      <Field label="Default production workflow" hint={current ? `Currently: ${current.name}` : undefined}>
        <select className="h-9 rounded-md border bg-background px-2 text-sm" value={selected?.id || ""} onChange={(e) => setChoice(e.target.value)} data-testid="onboarding-workflow-select">
          {items.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
      </Field>
      {selected && (
        <div className="flex flex-wrap gap-1.5" data-testid="onboarding-workflow-stages">
          {(selected.stages || []).filter((s) => s.active !== false).map((s) => (
            <span key={s.stage_key || s.display_name} className="rounded-full border px-2.5 py-0.5 text-xs">{s.display_name}</span>
          ))}
        </div>
      )}
      <FormError error={error} />
      <SaveBar busy={busy} disabled={!selected} label="Use this workflow and continue" />
    </form>
  );
}

export function EmployeeForm({ onSaved }) {
  const existing = useQuery({ queryKey: ["onboarding-employees"], queryFn: async () => (await api.get("/employees")).data?.items || [] });
  const [draft, setDraft] = useState({ name: "", email: "", role_label: "" });
  const { busy, error, run } = useSaver(onSaved);
  const [problem, setProblem] = useState(null);
  const submit = (e) => {
    e.preventDefault();
    if (!draft.name.trim()) { setProblem("Employee name is required."); return; }
    if (draft.email && !/^\S+@\S+\.\S+$/.test(draft.email)) { setProblem("Enter a valid email address."); return; }
    setProblem(null);
    run(async () => {
      const res = await api.post("/employees", filled(draft));
      setDraft({ name: "", email: "", role_label: "" });
      await existing.refetch();
      return res.data;
    }, "Employee added");
  };
  const bind = (k) => (e) => setDraft((d) => ({ ...d, [k]: e.target.value }));
  return (
    <div className="grid gap-4">
      <form onSubmit={submit} className="grid gap-3 md:grid-cols-3" data-testid="onboarding-form-employee">
        <Field label="Name"><Input value={draft.name} onChange={bind("name")} /></Field>
        <Field label="Email"><Input value={draft.email} onChange={bind("email")} /></Field>
        <Field label="Role / title"><Input value={draft.role_label} onChange={bind("role_label")} placeholder="e.g. Installer" /></Field>
        <div className="md:col-span-3 grid gap-2"><FormError error={problem || error} /><SaveBar busy={busy} label="Add employee" /></div>
      </form>
      <div className="text-sm text-muted-foreground" data-testid="onboarding-employee-list">
        {(existing.data || []).length ? `On your team: ${(existing.data || []).slice(0, 5).map((e) => e.name).join(", ")}` : "No employees yet."}
      </div>
    </div>
  );
}

export function CustomerForm({ onSaved }) {
  const [draft, setDraft] = useState({ name: "", company: "", email: "", phone: "" });
  const { busy, error, run } = useSaver(onSaved);
  const [problem, setProblem] = useState(null);
  const submit = (e) => {
    e.preventDefault();
    if (!draft.name.trim()) { setProblem("Customer name is required."); return; }
    if (draft.email && !/^\S+@\S+\.\S+$/.test(draft.email)) { setProblem("Enter a valid email address."); return; }
    setProblem(null);
    run(async () => (await api.post("/customers", filled(draft))).data, "Customer created");
  };
  const bind = (k) => (e) => setDraft((d) => ({ ...d, [k]: e.target.value }));
  return (
    <form onSubmit={submit} className="grid gap-3 md:grid-cols-2" data-testid="onboarding-form-customer">
      <Field label="Contact name"><Input value={draft.name} onChange={bind("name")} /></Field>
      <Field label="Company"><Input value={draft.company} onChange={bind("company")} /></Field>
      <Field label="Email"><Input value={draft.email} onChange={bind("email")} /></Field>
      <Field label="Phone"><Input value={draft.phone} onChange={bind("phone")} /></Field>
      <div className="md:col-span-2 grid gap-2"><FormError error={problem || error} /><SaveBar busy={busy} label="Create customer" /></div>
    </form>
  );
}

export function OrderForm({ onSaved }) {
  const customers = useQuery({ queryKey: ["onboarding-customers"], queryFn: async () => (await api.get("/customers", { params: { page_size: 50 } })).data });
  const list = customers.data?.items || [];
  const [customerId, setCustomerId] = useState("");
  const [jobName, setJobName] = useState("");
  const { busy, error, run } = useSaver(onSaved);
  const [problem, setProblem] = useState(null);
  const [created, setCreated] = useState(null);
  const chosen = customerId || list[0]?.id || "";
  const submit = (e) => {
    e.preventDefault();
    if (!chosen) { setProblem("Create a customer first."); return; }
    if (!jobName.trim()) { setProblem("Give the order a name."); return; }
    setProblem(null);
    run(async () => {
      const res = await api.post("/orders", { customer_id: chosen, job_name: jobName.trim() });
      setCreated(res.data);
      return res.data;
    }, "Order created");
  };
  return (
    <form onSubmit={submit} className="grid gap-3 md:grid-cols-2" data-testid="onboarding-form-order">
      <Field label="Customer">
        <select className="h-9 rounded-md border bg-background px-2 text-sm" value={chosen} onChange={(e) => setCustomerId(e.target.value)} data-testid="onboarding-order-customer">
          {list.map((c) => <option key={c.id} value={c.id}>{c.company || c.name}</option>)}
        </select>
      </Field>
      <Field label="Order name" hint="You can add line items and pricing on the order itself."><Input value={jobName} onChange={(e) => setJobName(e.target.value)} placeholder="e.g. Lobby sign" /></Field>
      <div className="md:col-span-2 grid gap-2">
        <FormError error={problem || error} />
        <div className="flex flex-wrap items-center gap-3">
          <SaveBar busy={busy} label="Create order" />
          {created?.id && <Link className="text-sm underline" to={`/orders/${created.id}`}>Open the new order</Link>}
        </div>
      </div>
    </form>
  );
}

export const STEP_FORMS = {
  company: CompanyForm,
  contact: ContactForm,
  branding: BrandingForm,
  labor_rates: LaborRatesForm,
  workflow: WorkflowForm,
  employee: EmployeeForm,
  payment_prefs: PaymentPrefsForm,
  portal_prefs: PortalPrefsForm,
  notifications: NotificationsForm,
  customer: CustomerForm,
  order: OrderForm,
};
