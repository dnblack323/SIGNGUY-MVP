import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Loader2 } from "lucide-react";
import SignGuyLogo from "@/components/brand/SignGuyLogo";

export default function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="min-h-dvh grid place-items-center text-muted-foreground">
        <div className="flex flex-col items-center gap-3" data-testid="auth-loading-state">
          <SignGuyLogo variant="full" className="h-12 w-52" testId="auth-loading-logo" />
          <div className="flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin" />
            Loading...
          </div>
        </div>
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}
