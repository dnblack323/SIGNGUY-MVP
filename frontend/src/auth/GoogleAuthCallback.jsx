import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";

/**
 * Lands here when the URL fragment contains `#session_id=...` after the
 * user completes Google Sign-In via Emergent-managed Google Auth.
 * Exchanges the one-time session_id for our own app JWT, then continues
 * into the dashboard exactly like a normal email/password login.
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
        const sessionId = new URLSearchParams(window.location.hash.slice(1)).get("session_id");
        if (!sessionId) throw new Error("Missing session_id");
        const { data } = await api.post("/auth/google/session", { session_id: sessionId });
        localStorage.setItem("signguy.token", data.access_token);
        window.history.replaceState(null, "", window.location.pathname + window.location.search);
        await refresh();
        navigate("/", { replace: true });
      } catch {
        setErrorMsg("Google sign-in failed. Redirecting back to login…");
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
