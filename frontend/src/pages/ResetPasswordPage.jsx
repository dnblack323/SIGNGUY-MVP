import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api, { extractError } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import SignGuyLogo from "@/components/brand/SignGuyLogo";
import { toast } from "sonner";

export default function ResetPasswordPage() {
  const [sp] = useSearchParams();
  const [token, setToken] = useState(sp.get("token") || "");
  const [pw, setPw] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  async function onSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: pw });
      toast.success("Password updated. Please sign in.");
      navigate("/login");
    } catch (err) {
      toast.error(extractError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-dvh grid place-items-center px-4 py-10 header-wash">
      <Card className="w-full max-w-[440px]">
        <CardHeader className="items-center text-center">
          <SignGuyLogo variant="full" className="h-12 w-full max-w-[240px]" testId="reset-password-logo" />
          <CardTitle className="font-display">Set new password</CardTitle>
          <CardDescription>Use the token from your email.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="grid gap-3">
            <div className="grid gap-1.5">
              <Label>Reset token</Label>
              <Input value={token} onChange={(e) => setToken(e.target.value)} required data-testid="reset-token-input" />
            </div>
            <div className="grid gap-1.5">
              <Label>New password</Label>
              <Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} required minLength={8} data-testid="reset-password-input" />
            </div>
            <Button type="submit" disabled={submitting} data-testid="reset-submit-button">
              {submitting && <Loader2 className="size-4 mr-2 animate-spin" />}Update password
            </Button>
            <div className="text-sm text-muted-foreground pt-1">
              <Link className="link-underline" to="/login">Back to sign in</Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
