import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";

/**
 * Lands here when Google redirects back with `?code=...&state=...`.
 * Exchanges the one-time authorization code for our own app JWT, then
 * continues into the dashboard exactly like a normal email/password login.
 */
export default function GoogleAuthCallback() {
  const hasProcessed = useRef(false);
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [errorMsg, setErrorMsg] = useState(null);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    (async () => {
      try {
        const params = new URLSearchParams(window.location.search);
        const code = params.get("code");
        const state = params.get("state");
        if (!code || !state) throw new Error("Missing Google authorization response");
        const redirectUri = `${window.location.origin}/auth/google/callback`;
        const { data } = await api.post("/auth/google/callback", {
          code,
          state,
          redirect_uri: redirectUri,
        });
        localStorage.setItem("signguy.token", data.access_token);
        window.history.replaceState(null, "", window.location.pathname);
        await refresh();
        navigate("/", { replace: true });
      } catch {
        setErrorMsg("Google sign-in failed. Redirecting back to login...");
        setTimeout(() => navigate("/login", { replace: true }), 1800);
      }
    })();
  }, [refresh, navigate]);

  if (!errorMsg) return null;
  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-rose-600" data-testid="google-auth-callback-error">
      {errorMsg}
    </div>
  );
}
