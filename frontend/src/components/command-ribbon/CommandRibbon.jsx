import { useEffect, useRef, useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { commandDisabledState, splitPrimaryAndOverflow, visibleCommandGroups } from "@/lib/commandRibbon";

function commandIsActive(command, pathname) {
  if (typeof command.active === "boolean") return command.active;
  return !!command.to && pathname === command.to;
}

function RibbonCommandButton({ command, entitlements }) {
  const navigate = useNavigate();
  const location = useLocation();
  const Icon = command.icon;
  const state = commandDisabledState(command, entitlements);
  const active = commandIsActive(command, location.pathname);
  const title = state.reason || command.tooltip || command.label;

  const execute = () => {
    if (state.disabled) return;
    if (command.onSelect) command.onSelect(command);
    else if (command.to) navigate(command.to);
  };

  const button = (
    <Button
      type="button"
      variant={active ? "secondary" : "ghost"}
      size="sm"
      aria-label={command.label}
      aria-current={active ? "page" : undefined}
      aria-disabled={state.disabled || undefined}
      title={title}
      data-testid={command.testId || `ribbon-command-${command.id}`}
      data-command-id={command.id}
      data-active={active ? "true" : "false"}
      onClick={execute}
      className={cn(
        "h-10 min-w-[66px] flex-col gap-0.5 rounded-md px-1.5 py-1 text-center",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        state.disabled && "cursor-not-allowed opacity-55",
        active && "bg-muted text-foreground",
      )}
    >
      {Icon && <Icon className="size-3.5 shrink-0" aria-hidden="true" />}
      <span className="overflow-hidden text-[10px] leading-tight whitespace-normal [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]">{command.label}</span>
      {command.badge && <Badge variant="outline" className="h-4 px-1 text-[9px]">{command.badge}</Badge>}
    </Button>
  );

  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent side="bottom">{title}</TooltipContent>
    </Tooltip>
  );
}

function DropdownCommand({ command, entitlements }) {
  const navigate = useNavigate();
  const Icon = command.icon;
  const state = commandDisabledState(command, entitlements);

  const execute = () => {
    if (state.disabled) return;
    if (command.onSelect) command.onSelect(command);
    else if (command.to) navigate(command.to);
  };

  return (
    <DropdownMenuItem
      disabled={state.disabled}
      onSelect={execute}
      data-testid={command.testId || `ribbon-menu-command-${command.id}`}
    >
      {Icon && <Icon className="size-4" aria-hidden="true" />}
      <span>{command.label}</span>
      {state.reason && <span className="ml-auto text-xs text-muted-foreground">{state.reason}</span>}
    </DropdownMenuItem>
  );
}

function RibbonDropdownButton({ command, entitlements }) {
  const Icon = command.icon;
  const children = command.children || [];
  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-label={command.label}
              data-testid={command.testId || `ribbon-command-${command.id}`}
              className="h-10 min-w-[66px] flex-col gap-0.5 rounded-md px-1.5 py-1 text-center focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              {Icon && <Icon className="size-3.5 shrink-0" aria-hidden="true" />}
              <span className="overflow-hidden text-[10px] leading-tight whitespace-normal [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]">{command.label}</span>
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent side="bottom">{command.tooltip || command.label}</TooltipContent>
      </Tooltip>
      <DropdownMenuContent align="start" data-testid={`ribbon-dropdown-${command.id}`}>
        <DropdownMenuLabel>{command.label}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {children.map((child) => <DropdownCommand key={child.id} command={child} entitlements={entitlements} />)}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function OverflowMenu({ commands, entitlements }) {
  if (!commands.length) return null;
  const menuCommands = commands.flatMap((command) => (
    command.children?.length
      ? command.children.map((child) => ({ ...child, groupLabel: command.groupLabel }))
      : [command]
  ));
  return (
    <div className="border-l pl-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-10 min-w-[66px] flex-col gap-0.5 rounded-md px-1.5 py-1"
            aria-label="More commands"
            data-testid="ribbon-overflow-trigger"
          >
            <MoreHorizontal className="size-3.5" aria-hidden="true" />
            <span className="text-[10px] leading-tight">More</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" data-testid="ribbon-overflow-menu">
          {menuCommands.map((command, index) => (
            <div key={command.id}>
              {index === 0 || menuCommands[index - 1].groupLabel !== command.groupLabel ? (
                <DropdownMenuLabel>{command.groupLabel}</DropdownMenuLabel>
              ) : null}
              <DropdownCommand command={command} entitlements={entitlements} />
            </div>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function responsiveCommandCap(width) {
  if (!width) return 10;
  if (width < 480) return 3;
  if (width < 640) return 4;
  if (width < 900) return 6;
  if (width < 1100) return 8;
  if (width < 1320) return 11;
  return 12;
}

export default function CommandRibbon({
  groups,
  entitlements = {},
  maxPrimaryCommands = 12,
  "data-testid": testId = "command-ribbon",
}) {
  const auth = useAuth();
  const visibleGroups = visibleCommandGroups(groups, auth);
  const ribbonRef = useRef(null);
  const [ribbonWidth, setRibbonWidth] = useState(
    typeof window === "undefined" ? 0 : window.innerWidth,
  );
  const effectiveMaxPrimaryCommands = Math.min(maxPrimaryCommands, responsiveCommandCap(ribbonWidth));
  const { primaryGroups, overflowCommands } = splitPrimaryAndOverflow(visibleGroups, effectiveMaxPrimaryCommands);

  useEffect(() => {
    if (!ribbonRef.current || typeof window === "undefined") return undefined;
    const updateWidth = () => {
      setRibbonWidth(ribbonRef.current?.getBoundingClientRect().width || window.innerWidth);
    };
    updateWidth();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateWidth);
      return () => window.removeEventListener("resize", updateWidth);
    }
    const observer = new ResizeObserver(updateWidth);
    observer.observe(ribbonRef.current);
    return () => observer.disconnect();
  }, []);

  if (!primaryGroups.length && !overflowCommands.length) return null;

  return (
    <TooltipProvider delayDuration={250}>
      <section
        ref={ribbonRef}
        aria-label="Page commands"
        data-testid={testId}
        className="rounded-lg border bg-card text-card-foreground shadow-sm"
      >
        <div className="flex max-w-full items-stretch gap-1 overflow-hidden px-2 py-1">
          {primaryGroups.map((group) => (
            <div key={group.id} className="flex shrink-0 flex-col gap-0.5 border-r pr-1 last:border-r-0" data-testid={`ribbon-group-${group.id}`}>
              <div className="flex items-start gap-1">
                {group.commands.map((command) => (
                  command.children?.length ? (
                    <RibbonDropdownButton key={command.id} command={command} entitlements={entitlements} />
                  ) : (
                    <RibbonCommandButton key={command.id} command={command} entitlements={entitlements} />
                  )
                ))}
              </div>
              <div className="text-center text-[8.5px] font-medium uppercase tracking-wide text-muted-foreground">{group.label}</div>
            </div>
          ))}
          <OverflowMenu commands={overflowCommands} entitlements={entitlements} />
        </div>
      </section>
    </TooltipProvider>
  );
}
