import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, CheckCircle2, ChevronRight, CircleDashed, ExternalLink, HelpCircle, Lock, PauseCircle, SkipForward } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/layout/PageHeader";
import ContextualHelp from "@/components/help/ContextualHelp";
import { STEP_FORMS } from "@/components/onboarding/stepForms";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { getOnboardingDashboard, helpHref, saveOnboardingPosition, updateOnboardingTask } from "@/lib/onboarding";

const STATUS_LABEL = {
  completed: "Done",
  skipped: "Skipped",
  deferred: "Later",
  blocked: "Blocked",
  in_progress: "In progress",
  not_started: "To do",
};

function StatusIcon({ status, className }) {
  if (status === "completed") return <CheckCircle2 className={cn("size-4 text-emerald-600", className)} aria-hidden="true" />;
  if (status === "blocked") return <Lock className={cn("size-4 text-muted-foreground", className)} aria-hidden="true" />;
  if (status === "deferred") return <PauseCircle className={cn("size-4 text-amber-600", className)} aria-hidden="true" />;
  if (status === "skipped") return <SkipForward className={cn("size-4 text-muted-foreground", className)} aria-hidden="true" />;
  return <CircleDashed className={cn("size-4 text-muted-foreground", className)} aria-hidden="true" />;
}

function StepRail({ stages, tasks, activeKey, onSelect }) {
  return (
    <nav aria-label="Setup steps" className="space-y-4" data-testid="onboarding-rail">
      {stages.map((stage) => (
        <div key={stage.key} className="space-y-1" data-testid={`onboarding-stage-${stage.key}`}>
          <div className="flex items-baseline justify-between px-1">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{stage.title}</div>
            <div className="text-xs text-muted-foreground tabular-nums">{stage.completed_tasks}/{stage.total_tasks}</div>
          </div>
          <ul className="space-y-0.5">
            {tasks.filter((t) => t.stage === stage.key).map((t) => (
              <li key={t.task_key}>
                <button
                  type="button"
                  onClick={() => onSelect(t.task_key)}
                  aria-current={t.task_key === activeKey ? "step" : undefined}
                  data-testid={`onboarding-step-${t.task_key}`}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted",
                    t.task_key === activeKey && "bg-muted font-medium",
                  )}
                >
                  <StatusIcon status={t.status} />
                  <span className="min-w-0 flex-1 truncate">{t.title}</span>
                  {t.level === "required" && t.status !== "completed" && <span className="text-[10px] uppercase text-muted-foreground">Required</span>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function StepPanel({ task, canWrite, onSaved, onStatus, busy }) {
  const Form = task.form ? STEP_FORMS[task.form] : null;
  const done = task.status === "completed";
  const blocked = task.status === "blocked";
  const isManual = task.detect === "manual";
  return (
    <Card data-testid={`onboarding-panel-${task.task_key}`}>
      <CardHeader className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-lg">{task.title}</CardTitle>
          <Badge variant={done ? "secondary" : blocked ? "destructive" : "outline"} data-testid="onboarding-step-status">{STATUS_LABEL[task.status] || task.status}</Badge>
          <Badge variant="outline">{task.level === "required" ? "Required" : task.level === "recommended" ? "Recommended" : "Optional"}</Badge>
        </div>
        <dl className="grid gap-1 text-sm">
          <div><dt className="inline font-medium">What this sets up: </dt><dd className="inline text-muted-foreground">{task.what}</dd></div>
          <div><dt className="inline font-medium">Why it matters: </dt><dd className="inline text-muted-foreground">{task.why}</dd></div>
        </dl>
      </CardHeader>
      <CardContent className="space-y-4">
        {blocked && (
          <Alert data-testid="onboarding-blocked"><Lock className="size-4" /><AlertTitle>Not available yet</AlertTitle><AlertDescription>{task.blocked_reason}</AlertDescription></Alert>
        )}
        {done && (
          <Alert data-testid="onboarding-complete"><CheckCircle2 className="size-4" /><AlertTitle>This step is complete</AlertTitle>
            <AlertDescription>{task.canonical_complete ? "Detected from your saved settings. Change it below or in the linked area at any time." : "Marked as reviewed."}</AlertDescription>
          </Alert>
        )}
        {!blocked && Form && canWrite && <Form onSaved={onSaved} />}
        {!blocked && Form && !canWrite && <div className="text-sm text-muted-foreground">Only an owner or admin can change this setup.</div>}
        {!blocked && !Form && !isManual && (
          <p className="text-sm text-muted-foreground">Set this up in {task.route_label || "the linked area"}; this step completes automatically once saved there.</p>
        )}
        {!blocked && !Form && isManual && !done && (
          <p className="text-sm text-muted-foreground">There is no saved record to check for this step. Open it, look it over, then mark it reviewed.</p>
        )}
        <div className="flex flex-wrap items-center gap-2 border-t pt-3">
          {task.route && (
            <Button asChild variant="outline" size="sm"><Link to={task.route} data-testid="onboarding-open-feature"><ExternalLink className="size-4 mr-2" />Open {task.route_label}</Link></Button>
          )}
          {isManual && !blocked && canWrite && !done && (
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => onStatus("completed")} data-testid="onboarding-mark-reviewed">Mark as reviewed</Button>
          )}
          {!done && !blocked && canWrite && task.level !== "required" && (
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => onStatus("skipped")} data-testid="onboarding-skip"><SkipForward className="size-4 mr-2" />Skip</Button>
          )}
          {!done && !blocked && canWrite && (
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => onStatus("deferred")} data-testid="onboarding-later">Do this later</Button>
          )}
          <Link to={helpHref(task.help_slug)} className="ml-auto inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline" data-testid="onboarding-help-link">
            <HelpCircle className="size-4" />Help
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

export default function OnboardingPage() {
  const { hasPerm, user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const canRead = hasPerm("onboarding:read");
  const canWrite = hasPerm("onboarding:write") && ["owner", "admin"].includes(user?.role);
  const dashboard = useQuery({ queryKey: ["onboarding-dashboard"], queryFn: getOnboardingDashboard, enabled: canRead });
  const data = dashboard.data;
  const tasks = useMemo(() => data?.tasks || [], [data?.tasks]);
  const [activeKey, setActiveKey] = useState(null);
  const lastSaved = useRef(null);

  // Resume priority: ?step= link, saved position, then the next recommended step.
  useEffect(() => {
    if (!data || activeKey) return;
    const wanted = params.get("step");
    const pick = [wanted, data.instance?.current_task_key, data.recommended_next_task?.task_key, tasks[0]?.task_key]
      .find((k) => k && tasks.some((t) => t.task_key === k));
    if (pick) setActiveKey(pick);
  }, [data, tasks, params, activeKey]);

  const refresh = useCallback(() => qc.invalidateQueries({ queryKey: ["onboarding-dashboard"] }), [qc]);

  const select = useCallback((key) => {
    setActiveKey(key);
    setParams({ step: key }, { replace: true });
    if (canWrite && lastSaved.current !== key) {
      lastSaved.current = key;
      saveOnboardingPosition({ task_key: key }).catch(() => {});
    }
  }, [canWrite, setParams]);

  const index = tasks.findIndex((t) => t.task_key === activeKey);
  const task = tasks[index];
  const goNext = useCallback(() => { if (index >= 0 && index < tasks.length - 1) select(tasks[index + 1].task_key); }, [index, tasks, select]);
  const goBack = useCallback(() => { if (index > 0) select(tasks[index - 1].task_key); }, [index, tasks, select]);

  const status = useMutation({
    mutationFn: ({ key, value }) => updateOnboardingTask(key, { status: value }),
    onSuccess: async (_res, vars) => {
      await refresh();
      toast.success(vars.value === "completed" ? "Marked as reviewed" : vars.value === "skipped" ? "Step skipped" : "We'll remind you later");
      if (vars.value !== "completed") goNext();
    },
    onError: (err) => toast.error(extractError(err)),
  });

  const afterSave = useCallback(async () => {
    await refresh();
    goNext();
  }, [refresh, goNext]);

  const leave = async () => {
    if (canWrite && activeKey) await saveOnboardingPosition({ task_key: activeKey, dismiss_prompt: true }).catch(() => {});
    await refresh();
    navigate("/");
  };

  if (!canRead) {
    return (
      <div className="space-y-4" data-testid="onboarding-page">
        <PageHeader title="Guided Setup" subtitle="Guided setup is available to internal shop users." />
        <Alert><HelpCircle className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account cannot read onboarding.</AlertDescription></Alert>
      </div>
    );
  }

  const quick = data?.stages?.[0];
  return (
    <div className="space-y-5" data-testid="onboarding-page">
      <PageHeader
        title="Guided Setup"
        subtitle="Get your shop running in minutes. Everything you enter here is saved to the real settings and records — you can change it later in the same place."
        actions={<><ContextualHelp surfaceKey="onboarding.dashboard" module="onboarding" /><Button variant="outline" size="sm" onClick={leave} data-testid="onboarding-resume-later">Resume later</Button></>}
      />

      {dashboard.isError && (
        <Alert variant="destructive" role="alert"><AlertTitle>Could not load setup</AlertTitle><AlertDescription>{extractError(dashboard.error)}</AlertDescription></Alert>
      )}

      {data && (
        <>
          <div className="space-y-1.5" data-testid="onboarding-summary">
            <Progress value={data.progress.percent_complete} data-testid="onboarding-progress" />
            <div className="flex flex-wrap justify-between gap-2 text-sm text-muted-foreground" data-testid="onboarding-progress-text">
              <span>{data.progress.completed_tasks} of {data.progress.total_tasks} complete</span>
              <span>{quick?.required_complete ? "Quick Start complete — your shop is ready to work." : `Quick Start: ${quick?.completed_required_tasks}/${quick?.required_tasks} required steps`}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
            <Card className="order-2 h-fit lg:order-1 lg:sticky lg:top-4"><CardContent className="p-3">
              <StepRail stages={data.stages} tasks={tasks} activeKey={activeKey} onSelect={select} />
            </CardContent></Card>

            <div className="order-1 min-w-0 space-y-3 lg:order-2">
              {task && (
                <>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <span>{data.stages.find((s) => s.key === task.stage)?.title}</span><ChevronRight className="size-3" /><span>Step {tasks.filter((t) => t.stage === task.stage).findIndex((t) => t.task_key === task.task_key) + 1} of {tasks.filter((t) => t.stage === task.stage).length}</span>
                  </div>
                  <StepPanel
                    key={task.task_key}
                    task={task}
                    canWrite={canWrite}
                    busy={status.isPending}
                    onSaved={afterSave}
                    onStatus={(value) => status.mutate({ key: task.task_key, value })}
                  />
                  <div className="flex items-center justify-between">
                    <Button variant="outline" size="sm" onClick={goBack} disabled={index <= 0} data-testid="onboarding-back"><ArrowLeft className="size-4 mr-2" />Back</Button>
                    <Button variant="outline" size="sm" onClick={goNext} disabled={index >= tasks.length - 1} data-testid="onboarding-next">Next<ArrowRight className="size-4 ml-2" /></Button>
                  </div>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
