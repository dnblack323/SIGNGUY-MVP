import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import api, { extractError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { toast } from "sonner";

export default function SupportModeBanner() {
  const { user } = useAuth();
  const impersonation = user?.impersonation;
  if (!impersonation?.is_impersonating) return null;

  async function exitSupportMode() {
    const platformToken = localStorage.getItem("signguy.platformToken");
    if (!platformToken) {
      localStorage.removeItem("signguy.token");
      window.location.href = "/login";
      return;
    }
    localStorage.setItem("signguy.token", platformToken);
    localStorage.removeItem("signguy.platformToken");
    try {
      if (impersonation.impersonation_log_id) {
        await api.post(`/platform-admin/impersonation-logs/${impersonation.impersonation_log_id}/end`);
      }
    } catch (err) {
      toast.error(extractError(err, "Support-mode exit was restored locally, but logging failed."));
    } finally {
      window.location.href = "/platform-admin";
    }
  }

  return (
    <div className="flex items-center justify-center gap-3 border-b border-blue-200 bg-blue-50 px-4 py-2 text-sm text-blue-950" data-testid="support-mode-banner">
      <ShieldCheck className="size-4 shrink-0" />
      <span>Support mode active. You are viewing this account as a tenant user.</span>
      <Button type="button" size="sm" variant="outline" className="h-8 border-blue-300 bg-white" onClick={exitSupportMode}>
        Exit Support Mode
      </Button>
    </div>
  );
}
