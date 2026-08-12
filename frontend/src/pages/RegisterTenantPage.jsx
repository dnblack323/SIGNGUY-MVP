import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { Loader2 } from "lucide-react";
import SignGuyLogo from "@/components/brand/SignGuyLogo";
import { toast } from "sonner";

export default function RegisterTenantPage() {
  const [form, setForm] = useState({ tenant_name: "", tenant_slug: "", owner_full_name: "", owner_email: "", owner_password: "" });
  const [submitting, setSubmitting] = useState(false);
  const { registerTenant } = useAuth();
  const navigate = useNavigate();

  const upd = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function onSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await registerTenant({
        ...form,
        tenant_slug: form.tenant_slug.trim().toLowerCase().replace(/[^a-z0-9-]/g, "-"),
      });
      toast.success("Shop created");
      navigate("/", { replace: true });
    } catch (err) {
      toast.error(extractError(err, "Could not register shop"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-dvh grid place-items-center px-4 py-10 header-wash">
      <Card className="w-full max-w-[480px]">
        <CardHeader>
          <div className="flex flex-col items-center gap-2 text-center">
            <SignGuyLogo variant="full" className="h-12 w-full max-w-[240px]" testId="register-logo" />
            <div>
              <CardTitle className="font-display">Create your shop</CardTitle>
              <CardDescription>Start a new SignGuy AI workspace</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="grid gap-3" data-testid="register-form">
            <div className="grid gap-1.5">
              <Label>Shop name</Label>
              <Input value={form.tenant_name} onChange={upd("tenant_name")} required data-testid="register-tenant-name-input" />
            </div>
            <div className="grid gap-1.5">
              <Label>Shop slug (short, lowercase, no spaces)</Label>
              <Input value={form.tenant_slug} onChange={upd("tenant_slug")} required data-testid="register-tenant-slug-input" />
            </div>
            <div className="grid gap-1.5">
              <Label>Your name</Label>
              <Input value={form.owner_full_name} onChange={upd("owner_full_name")} required data-testid="register-owner-name-input" />
            </div>
            <div className="grid gap-1.5">
              <Label>Email</Label>
              <Input type="email" value={form.owner_email} onChange={upd("owner_email")} required data-testid="register-owner-email-input" />
            </div>
            <div className="grid gap-1.5">
              <Label>Password (min 8 chars)</Label>
              <Input type="password" value={form.owner_password} onChange={upd("owner_password")} required minLength={8} data-testid="register-owner-password-input" />
            </div>
            <Button type="submit" disabled={submitting} data-testid="register-submit-button">
              {submitting && <Loader2 className="size-4 mr-2 animate-spin" />}
              Create shop
            </Button>
            <div className="text-sm text-muted-foreground pt-1">
              Already have an account? <Link className="link-underline" to="/login">Sign in</Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
