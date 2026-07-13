import { useState } from "react";
import { Link } from "react-router-dom";
import api, { extractError } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Building2, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function ForgotPasswordPage() {
  const [tenantSlug, setTenantSlug] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [devToken, setDevToken] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const { data } = await api.post("/auth/request-password-reset", { tenant_slug: tenantSlug.trim().toLowerCase(), email });
      setDone(true);
      if (data?.dev_reset_token) setDevToken(data.dev_reset_token);
      toast.success("If that shop and email match, a reset was created.");
    } catch (err) {
      toast.error(extractError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-dvh grid place-items-center px-4 py-10 header-wash">
      <Card className="w-full max-w-[440px]">
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground"><Building2 className="size-4" /></div>
            <div>
              <CardTitle className="font-display">Reset your password</CardTitle>
              <CardDescription>We'll email you a one-time token (60 min).</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {!done ? (
            <form onSubmit={onSubmit} className="grid gap-3">
              <div className="grid gap-1.5">
                <Label>Shop</Label>
                <Input type="text" value={tenantSlug} onChange={(e) => setTenantSlug(e.target.value)} placeholder="your-shop-slug" required data-testid="forgot-tenant-slug-input" />
              </div>
              <div className="grid gap-1.5">
                <Label>Email</Label>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="forgot-email-input" />
              </div>
              <Button type="submit" disabled={submitting} data-testid="forgot-submit-button">
                {submitting && <Loader2 className="size-4 mr-2 animate-spin" />}Send reset
              </Button>
              <div className="text-sm text-muted-foreground pt-1">
                <Link className="link-underline" to="/login">Back to sign in</Link>
              </div>
            </form>
          ) : (
            <div className="text-sm text-muted-foreground">
              A reset token has been created if the email exists.
              {devToken && (
                <div className="mt-3 rounded-md bg-muted p-3">
                  <div className="font-medium text-foreground text-sm">Dev token (SendGrid not configured):</div>
                  <div className="mono text-xs break-all mt-1">{devToken}</div>
                  <div className="mt-2"><Link className="link-underline" to={`/reset-password?token=${encodeURIComponent(devToken)}`}>Use token →</Link></div>
                </div>
              )}
              <div className="mt-3"><Link className="link-underline" to="/login">Back to sign in</Link></div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
