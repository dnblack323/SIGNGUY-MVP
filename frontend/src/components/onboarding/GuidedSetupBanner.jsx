import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/AuthContext";
import { getOnboardingDashboard, saveOnboardingPosition } from "@/lib/onboarding";

/**
 * A dismissible invitation on Home. It never redirects, never reopens after
 * "Not now", and disappears on its own once every required Quick Start step is done.
 */
export default function GuidedSetupBanner() {
  const { hasPerm, user } = useAuth();
  const qc = useQueryClient();
  const isAdmin = ["owner", "admin"].includes(user?.role) && hasPerm("onboarding:write");
  const dashboard = useQuery({ queryKey: ["onboarding-dashboard"], queryFn: getOnboardingDashboard, enabled: isAdmin, staleTime: 60_000 });
  const dismiss = useMutation({
    mutationFn: () => saveOnboardingPosition({ dismiss_prompt: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["onboarding-dashboard"] }),
  });
  const data = dashboard.data;
  if (!isAdmin || !data?.prompt?.show) return null;
  const quick = data.stages[0];
  const resume = data.prompt.resume_task_key;
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-4 sm:flex-row sm:items-center sm:justify-between" data-testid="guided-setup-banner">
      <div className="flex items-start gap-3">
        <Sparkles className="mt-0.5 size-5 text-muted-foreground" aria-hidden="true" />
        <div>
          <div className="font-medium">{resume ? "Pick up your guided setup" : "Set up your shop in a few minutes"}</div>
          <div className="text-sm text-muted-foreground">{quick.completed_required_tasks} of {quick.required_tasks} required Quick Start steps done. You can leave and come back at any time.</div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button asChild size="sm"><Link to={resume ? `/onboarding?step=${resume}` : "/onboarding"} data-testid="guided-setup-start">{resume ? "Resume setup" : "Start guided setup"}</Link></Button>
        <Button size="sm" variant="ghost" onClick={() => dismiss.mutate()} disabled={dismiss.isPending} data-testid="guided-setup-dismiss"><X className="size-4 mr-1" />Not now</Button>
      </div>
    </div>
  );
}
