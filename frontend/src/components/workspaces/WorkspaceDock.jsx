import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Pin,
  PinOff,
  RefreshCw,
  RotateCcw,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/context/WorkspaceContext";

function errorText(error) {
  if (!error) return "";
  if (typeof error === "string") return error;
  return error.message || "Workspace Dock action could not be completed.";
}

function WorkspaceTab({ workspace, index, all, compact = false }) {
  const { activate, close, pin, reorder } = useWorkspace();
  const ids = all.map((item) => item.id);
  const canMoveLeft = index > 0;
  const canMoveRight = index < all.length - 1;

  const move = (direction) => {
    const next = [...ids];
    const swapIndex = index + direction;
    [next[index], next[swapIndex]] = [next[swapIndex], next[index]];
    reorder(next);
  };

  return (
    <div
      data-testid="workspace-tab"
      data-active={workspace.active ? "true" : "false"}
      data-dirty={workspace.dirty ? "true" : "false"}
      className={cn(
        "group flex min-w-0 items-center gap-1 rounded-md border px-2 py-1 text-xs shadow-sm",
        workspace.active
          ? "border-cyan-500 bg-white text-slate-950"
          : "border-slate-300 bg-slate-100 text-slate-600 hover:bg-white",
        compact ? "w-full" : "max-w-[240px]",
      )}
    >
      <button
        type="button"
        onClick={() => activate(workspace)}
        className="flex min-w-0 flex-1 items-center gap-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
        title={workspace.label}
        aria-current={workspace.active ? "page" : undefined}
      >
        {workspace.pinned && <Pin className="size-3 shrink-0 text-cyan-600" aria-hidden="true" />}
        {workspace.dirty && <span className="size-1.5 shrink-0 rounded-full bg-amber-500" aria-label="Unsaved changes" />}
        <span className="truncate">{workspace.label}</span>
      </button>
      <div className="flex shrink-0 items-center gap-0.5">
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="size-6"
          aria-label={workspace.pinned ? "Unpin workspace" : "Pin workspace"}
          onClick={() => pin(workspace, !workspace.pinned)}
        >
          {workspace.pinned ? <PinOff className="size-3" /> : <Pin className="size-3" />}
        </Button>
        {!compact && (
          <>
            <Button type="button" size="icon" variant="ghost" className="size-6" aria-label="Move workspace left" disabled={!canMoveLeft} onClick={() => move(-1)}>
              <ChevronLeft className="size-3" />
            </Button>
            <Button type="button" size="icon" variant="ghost" className="size-6" aria-label="Move workspace right" disabled={!canMoveRight} onClick={() => move(1)}>
              <ChevronRight className="size-3" />
            </Button>
          </>
        )}
        <Button type="button" size="icon" variant="ghost" className="size-6" aria-label="Close workspace" onClick={() => close(workspace)}>
          <X className="size-3" />
        </Button>
      </div>
    </div>
  );
}

function RecentList({ compact = false }) {
  const { recent_workspaces, reopenRecent, removeRecent } = useWorkspace();
  if (!recent_workspaces.length) return <div className="px-2 py-3 text-xs text-slate-500">No recent work yet.</div>;
  return (
    <div className="space-y-1" data-testid="workspace-recent-list">
      {recent_workspaces.map((workspace) => (
        <div key={workspace.id} className={cn("flex items-center gap-2 rounded-md px-2 py-1 text-xs", compact ? "bg-slate-50" : "hover:bg-slate-100")}>
          <button type="button" className="min-w-0 flex-1 truncate text-left" title={workspace.label} onClick={() => reopenRecent(workspace)}>
            {workspace.label}
          </button>
          <Button type="button" size="icon" variant="ghost" className="size-6" aria-label="Reopen recent workspace" onClick={() => reopenRecent(workspace)}>
            <RotateCcw className="size-3" />
          </Button>
          <Button type="button" size="icon" variant="ghost" className="size-6" aria-label="Remove recent workspace" onClick={() => removeRecent(workspace)}>
            <X className="size-3" />
          </Button>
        </div>
      ))}
    </div>
  );
}

function DirtyDialog() {
  const { dirtyPrompt, setDirtyPrompt } = useWorkspace();
  return (
    <AlertDialog open={Boolean(dirtyPrompt)} onOpenChange={(open) => !open && setDirtyPrompt(null)}>
      <AlertDialogContent data-testid="workspace-dirty-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>Unsaved workspace changes</AlertDialogTitle>
          <AlertDialogDescription>
            {dirtyPrompt?.message || "This workspace has unsaved local changes. Continue without saving?"}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => setDirtyPrompt(null)}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              const action = dirtyPrompt?.action;
              setDirtyPrompt(null);
              action?.();
            }}
          >
            Continue
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function LimitDialog() {
  const { limitError, setLimitError, open_workspaces, close } = useWorkspace();
  const unpinned = open_workspaces.filter((workspace) => !workspace.pinned);
  return (
    <AlertDialog open={Boolean(limitError)} onOpenChange={(open) => !open && setLimitError(null)}>
      <AlertDialogContent data-testid="workspace-limit-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>Workspace limit reached</AlertDialogTitle>
          <AlertDialogDescription>
            {errorText(limitError)} Close an unpinned workspace before opening another one.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="max-h-52 space-y-1 overflow-y-auto">
          {unpinned.map((workspace) => (
            <button
              key={workspace.id}
              type="button"
              className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm hover:bg-slate-50"
              onClick={() => {
                setLimitError(null);
                close(workspace);
              }}
            >
              <span className="truncate">{workspace.label}</span>
              <X className="size-4" />
            </button>
          ))}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => setLimitError(null)}>Cancel</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function MobileOpenWork() {
  const { open_workspaces, loading } = useWorkspace();
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button
          type="button"
          className="fixed bottom-4 left-4 z-40 h-10 rounded-full border border-slate-300 bg-slate-950 px-4 text-white shadow-lg md:hidden"
          data-testid="mobile-open-work-trigger"
        >
          Open Work ({open_workspaces.length})
        </Button>
      </SheetTrigger>
      <SheetContent side="bottom" className="max-h-[80dvh] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Open Work</SheetTitle>
          <SheetDescription>Switch, close, pin, or reopen work without changing the page layout.</SheetDescription>
        </SheetHeader>
        <div className="mt-4 space-y-4" data-testid="mobile-open-work-drawer">
          <section>
            <h3 className="mb-2 text-sm font-semibold">Open</h3>
            {loading && <div className="text-xs text-slate-500">Loading workspaces...</div>}
            <div className="space-y-2">
              {open_workspaces.map((workspace, index) => (
                <WorkspaceTab key={workspace.id} workspace={workspace} index={index} all={open_workspaces} compact />
              ))}
            </div>
          </section>
          <section>
            <h3 className="mb-2 text-sm font-semibold">Recent Work</h3>
            <RecentList compact />
          </section>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default function WorkspaceDock({ sidebarCollapsed }) {
  const { open_workspaces, loading, error, refresh } = useWorkspace();
  const leftOffset = sidebarCollapsed ? "lg:left-[76px]" : "lg:left-[260px]";
  return (
    <TooltipProvider delayDuration={200}>
      <div
        className={cn(
          "fixed inset-x-0 bottom-0 z-30 hidden border-t border-slate-300 bg-white/95 shadow-[0_-8px_24px_rgba(15,23,42,0.12)] backdrop-blur md:block",
          leftOffset,
        )}
        data-testid="workspace-dock"
      >
        <div className="flex min-h-14 items-center gap-2 px-3 py-2">
          <div className="shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">Open Work</div>
          {loading && <div className="text-xs text-slate-500">Loading...</div>}
          {error && (
            <div className="flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-xs text-amber-900" data-testid="workspace-api-error">
              <AlertTriangle className="size-3" />
              <span>{errorText(error)}</span>
              <Button type="button" size="icon" variant="ghost" className="size-6" aria-label="Retry workspace dock" onClick={refresh}>
                <RefreshCw className="size-3" />
              </Button>
            </div>
          )}
          <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {open_workspaces.map((workspace, index) => (
              <Tooltip key={workspace.id}>
                <TooltipTrigger asChild>
                  <div className="min-w-0">
                    <WorkspaceTab workspace={workspace} index={index} all={open_workspaces} />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="top">{workspace.label}</TooltipContent>
              </Tooltip>
            ))}
          </div>
          <div className="relative shrink-0">
            <details className="group" data-testid="workspace-recent-menu">
              <summary className="cursor-pointer list-none rounded-md border px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                Recent Work
              </summary>
              <div className="absolute bottom-9 right-0 w-80 rounded-md border bg-white p-2 shadow-xl">
                <RecentList />
              </div>
            </details>
          </div>
        </div>
      </div>
      <MobileOpenWork />
      <DirtyDialog />
      <LimitDialog />
    </TooltipProvider>
  );
}
