import { useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import api, { extractError } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/auth/AuthContext";

const NAMESPACES = [
  {
    key: "company_profile",
    title: "Company Profile",
    fields: [
      { key: "phone", label: "Phone", type: "text" },
      { key: "website", label: "Website", type: "text" },
      { key: "address_line1", label: "Address line 1", type: "text" },
      { key: "address_line2", label: "Address line 2", type: "text" },
      { key: "city", label: "City", type: "text" },
      { key: "state", label: "State / Region", type: "text" },
      { key: "postal_code", label: "Postal code", type: "text" },
      { key: "country", label: "Country", type: "text" },
    ],
  },
  {
    key: "invoicing_defaults",
    title: "Invoicing Defaults",
    fields: [
      { key: "payment_terms", label: "Default payment terms", type: "text", placeholder: "e.g. Net 30" },
      { key: "invoice_footer", label: "Invoice footer note", type: "textarea" },
    ],
  },
  {
    key: "branding",
    title: "Branding",
    fields: [
      { key: "primary_color", label: "Primary color (hex)", type: "text", placeholder: "#123456" },
      { key: "email_signature", label: "Email signature", type: "textarea" },
    ],
  },
];

function NamespaceCard({ ns, canWrite }) {
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    api.get(`/settings/${ns.key}`).then((r) => {
      if (alive) setValues(r.data?.values || {});
    }).catch(() => {});
    return () => { alive = false; };
  }, [ns.key]);

  const upd = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }));

  async function save() {
    setBusy(true);
    try {
      await api.put(`/settings/${ns.key}`, values);
      toast.success("Saved");
    } catch (err) {
      toast.error(extractError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card data-testid={`settings-namespace-${ns.key}`}>
      <CardHeader><CardTitle>{ns.title}</CardTitle></CardHeader>
      <CardContent className="grid gap-3">
        {ns.fields.map((f) => (
          <div key={f.key} className="grid gap-1.5">
            <Label>{f.label}</Label>
            {f.type === "textarea" ? (
              <Textarea
                value={values[f.key] ?? ""}
                onChange={upd(f.key)}
                data-testid={`setting-input-${ns.key}-${f.key}`}
                disabled={!canWrite}
              />
            ) : (
              <Input
                value={values[f.key] ?? ""}
                onChange={upd(f.key)}
                placeholder={f.placeholder}
                data-testid={`setting-input-${ns.key}-${f.key}`}
                disabled={!canWrite}
              />
            )}
          </div>
        ))}
        {canWrite && (
          <div className="flex justify-end">
            <Button onClick={save} disabled={busy} data-testid={`setting-save-${ns.key}`}>
              {busy ? "Saving…" : "Save changes"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function CompanySettingsPage() {
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("settings:write");
  return (
    <div className="space-y-4" data-testid="company-settings-page">
      <PageHeader
        title="Company Settings"
        subtitle="Your business info, invoicing defaults, and branding."
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {NAMESPACES.map((ns) => (
          <NamespaceCard key={ns.key} ns={ns} canWrite={canWrite} />
        ))}
      </div>
    </div>
  );
}
