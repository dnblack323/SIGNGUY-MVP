import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { Loader2, Building2 } from "lucide-react";
import { toast } from "sonner";

function handleGoogleLogin() {
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const redirectUrl = window.location.origin + "/";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

export default function LoginPage() {
  const [tenantSlug, setTenantSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { login, user, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/";

  useEffect(() => { if (!loading && user) navigate(from, { replace: true }); }, [user, loading, navigate, from]);

  async function onSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login(tenantSlug.trim().toLowerCase(), email, password);
      toast.success("Signed in");
      navigate(from, { replace: true });
    } catch (err) {
      toast.error(extractError(err, "Invalid shop, email, or password"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-dvh grid place-items-center px-4 py-10 header-wash">
      <Card className="w-full max-w-[420px]">
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground"><Building2 className="size-4" /></div>
            <div>
              <CardTitle className="font-display">SignGuy AI</CardTitle>
              <CardDescription>Sign in to your shop</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="grid gap-3" data-testid="login-form">
            <div className="grid gap-1.5">
              <Label htmlFor="tenant-slug">Shop</Label>
              <Input id="tenant-slug" data-testid="login-tenant-slug-input" type="text" value={tenantSlug} onChange={(e) => setTenantSlug(e.target.value)} placeholder="your-shop-slug" required autoComplete="organization" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" data-testid="login-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" data-testid="login-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
            </div>
            <Button type="submit" disabled={submitting} data-testid="login-submit-button">
              {submitting && <Loader2 className="size-4 mr-2 animate-spin" />}
              Sign in
            </Button>
            <div className="relative py-1 text-center text-xs text-muted-foreground">
              <span className="bg-card px-2 relative z-10">or</span>
              <div className="absolute inset-x-0 top-1/2 h-px bg-border" />
            </div>
            <Button type="button" variant="outline" onClick={handleGoogleLogin} data-testid="login-google-button">
              <svg className="size-4 mr-2" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.1 29.5 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z" />
                <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 15.9 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.1 29.5 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
                <path fill="#4CAF50" d="M24 44c5.4 0 10.3-2.1 13.9-5.4l-6.4-5.4C29.6 34.7 26.9 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.6 5.1C9.6 39.6 16.2 44 24 44z" />
                <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.3-4.2 5.7l6.4 5.4C41.5 35.9 44 30.4 44 24c0-1.3-.1-2.7-.4-3.5z" />
              </svg>
              Continue with Google
            </Button>
            <div className="flex justify-between text-sm text-muted-foreground pt-1">
              <Link className="link-underline" to="/forgot-password" data-testid="login-forgot-link">Forgot password?</Link>
              <Link className="link-underline" to="/register" data-testid="login-register-link">Create a shop</Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
