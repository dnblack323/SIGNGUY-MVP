import { CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Generic stage timeline for record workspaces (Webstores now, Order Workspace later).
 * Display only: the stages, the current stage, the one next action and its blockers
 * all come from the backend read model.
 */
export default function WorkspaceTimeline({
  title = "Progress",
  stages = [],
  currentKey,
  nextAction,
  blockers = [],
  facts = [],
  action = null,
  testId = "workspace-timeline",
}) {
  const currentIndex = Math.max(0, stages.findIndex((stage) => stage.key === currentKey));
  return (
    <Card data-testid={testId}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <ol className="flex flex-wrap gap-x-1 gap-y-2" data-testid={`${testId}-stages`}>
          {stages.map((stage, index) => {
            const done = index < currentIndex;
            const current = index === currentIndex;
            return (
              <li
                key={stage.key}
                className="flex items-center gap-1"
                data-testid={`${testId}-stage-${stage.key}`}
                aria-current={current ? "step" : undefined}
              >
                <span
                  className={`flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs ${
                    current
                      ? "border-sky-700 bg-sky-700 font-medium text-white"
                      : done
                        ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                        : "border-slate-200 bg-white text-slate-500"
                  }`}
                >
                  {done && <CheckCircle2 className="size-3.5" />}
                  {stage.label}
                </span>
                {index < stages.length - 1 && <span className="h-px w-3 bg-slate-300" aria-hidden />}
              </li>
            );
          })}
        </ol>
        {nextAction && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-slate-50 p-3" data-testid={`${testId}-next-action`}>
            <div className="min-w-0">
              <div className="text-xs font-medium uppercase text-muted-foreground">{nextAction.heading || "Next step"}</div>
              <div className="mt-1 font-medium">{nextAction.text}</div>
              {nextAction.note && <div className="mt-1 text-xs text-muted-foreground">{nextAction.note}</div>}
            </div>
            {action}
          </div>
        )}
        {blockers.length > 0 && (
          <div data-testid={`${testId}-blockers`}>
            <div className="text-xs font-medium uppercase text-muted-foreground">Still open</div>
            <ul className="mt-1 space-y-1">
              {blockers.map((blocker) => (
                <li key={blocker.key} className="text-muted-foreground">
                  {blocker.text}
                </li>
              ))}
            </ul>
          </div>
        )}
        {facts.length > 0 && (
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {facts.map((fact) => (
              <div key={fact.label}>
                <dt className="text-xs font-medium uppercase text-muted-foreground">{fact.label}</dt>
                <dd className="font-semibold">{fact.value || "—"}</dd>
              </div>
            ))}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
