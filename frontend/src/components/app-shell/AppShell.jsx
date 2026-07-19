import { NavLink, Outlet, useLocation } from "react-router-dom";
import { LogOut, Building2, ChevronsLeft, ShieldAlert } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { NAV_AREAS, filterFlyoutByPermissions } from "@/lib/navigation";
import NotificationBell from "@/components/notifications/NotificationBell";

function FlyoutPanel({ area, permissions, user, onNavigate }) {
  const entries = filterFlyoutByPermissions(area.flyout, permissions, user);
  if (!entries.length) return null;
  return (
    <div
      data-testid={`flyout-${area.key}`}
      className="absolute left-full top-0 ml-1 w-64 rounded-lg border bg-popover shadow-lg py-2 z-40"
    >
      <div className="px-3 pb-2 text-xs uppercase tracking-wide text-muted-foreground">
        {area.label}
      </div>
      {entries.map((e) => {
        const disabled = !!e.disabled;
        return (
          <NavLink
            key={e.key}
            to={disabled ? "#" : e.to}
            onClick={(evt) => { if (disabled) evt.preventDefault(); else onNavigate?.(); }}
            data-testid={e.testId}
            data-disabled={disabled ? "true" : "false"}
            className={({ isActive }) => cn(
              "block px-3 py-1.5 text-sm rounded-md mx-1",
              disabled ? "text-muted-foreground/60 cursor-not-allowed" : "hover:bg-muted/60",
              !disabled && isActive ? "bg-muted/80 text-foreground" : "text-muted-foreground",
            )}
          >
            {e.label}
            {disabled && <span className="ml-2 text-[10px] uppercase tracking-wider">soon</span>}
          </NavLink>
        );
      })}
    </div>
  );
}

function SidebarInner({ onNavigate }) {
  const { tenant, permissions, user, logout } = useAuth();
  const [openArea, setOpenArea] = useState(null);
  const location = useLocation();
  useEffect(() => {
    setOpenArea(null);
  }, [location.pathname]);
  return (
    <div className="flex h-full flex-col relative" data-testid="app-shell-sidebar" onMouseLeave={() => setOpenArea(null)}>
      <div className="px-4 py-4 border-b">
        <div className="flex items-center gap-2">
          <div className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Building2 className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="font-display font-semibold text-sm truncate" data-testid="sidebar-tenant-name">{tenant?.name || "SignGuy AI"}</div>
            <div className="text-[11px] text-muted-foreground truncate">{tenant?.slug}</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 px-2 py-2 space-y-0.5 overflow-visible" data-testid="sidebar-nav">
        {NAV_AREAS.map((area) => {
          const Icon = area.icon;
          if (area.home) {
            return (
              <NavLink
                key={area.key}
                to={area.to}
                end
                onClick={onNavigate}
                data-testid={area.testId}
                className={({ isActive }) => cn(
                  "h-10 px-3 rounded-lg flex items-center gap-3 text-sm transition-colors",
                  isActive ? "bg-muted/80 text-foreground" : "text-muted-foreground hover:text-foreground hover:bg-muted/60",
                )}
              >
                <Icon className="size-4" />
                <span>{area.label}</span>
              </NavLink>
            );
          }
          return (
            <div key={area.key}>
              <div
                className="relative"
                onMouseEnter={() => setOpenArea(area.key)}
              >
                <button
                  type="button"
                  data-testid={area.testId}
                  onClick={() => setOpenArea(openArea === area.key ? null : area.key)}
                  className={cn(
                    "w-full h-10 px-3 rounded-lg flex items-center gap-3 text-sm transition-colors",
                    openArea === area.key ? "bg-muted/80 text-foreground" : "text-muted-foreground hover:text-foreground hover:bg-muted/60",
                  )}
                >
                  <Icon className="size-4" />
                  <span>{area.label}</span>
                </button>
                {openArea === area.key && (
                  <FlyoutPanel area={area} permissions={permissions} user={user} onNavigate={onNavigate} />
                )}
              </div>
              {area.divider && (
                <div className="my-2 border-t border-border/60" data-testid="sidebar-divider" />
              )}
            </div>
          );
        })}
      </nav>
      <div className="border-t px-2 py-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="w-full h-11 px-2 rounded-lg hover:bg-muted/60 flex items-center gap-2 text-left" data-testid="sidebar-user-menu">
              <Avatar className="size-7"><AvatarFallback>{(user?.full_name || user?.email || "U").slice(0,1).toUpperCase()}</AvatarFallback></Avatar>
              <div className="min-w-0 flex-1">
                <div className="text-sm truncate">{user?.full_name || user?.email}</div>
                <div className="text-[11px] text-muted-foreground truncate">{user?.role}</div>
              </div>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" side="top" className="w-[240px]">
            <DropdownMenuLabel className="truncate">{user?.email}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout} data-testid="sidebar-logout">
              <LogOut className="size-4 mr-2" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const loc = useLocation();
  const { devBypass } = useAuth();
  return (
    <div className="min-h-dvh bg-background text-foreground">
      {devBypass && (
        <div className="w-full bg-amber-50 border-b border-amber-200 text-amber-900 text-xs px-4 py-1.5 flex items-center justify-center gap-2" data-testid="dev-bypass-banner">
          <ShieldAlert className="size-3.5" />
          <span><span className="font-semibold">Auth bypass ON</span> · you're browsing as Dev Shop owner. Set <span className="mono">AUTH_DEV_BYPASS=false</span> before deploying.</span>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr]">
        <aside className="hidden lg:flex flex-col border-r bg-[hsl(var(--sidebar))] h-dvh sticky top-0 z-20">
          <SidebarInner />
        </aside>

        <div className="min-w-0">
          <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60" data-testid="app-shell-topbar">
            <div className="h-14 px-4 md:px-6 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
                  <SheetTrigger asChild>
                    <Button variant="ghost" size="icon" className="lg:hidden" data-testid="sidebar-open-mobile">
                      <ChevronsLeft className="size-4 rotate-180" />
                    </Button>
                  </SheetTrigger>
                  <SheetContent side="left" className="p-0 w-[280px]">
                    <SidebarInner onNavigate={() => setMobileOpen(false)} />
                  </SheetContent>
                </Sheet>
                <div className="font-display font-semibold truncate" data-testid="topbar-page-title">
                  SignGuy AI
                </div>
              </div>
              <div className="flex items-center gap-2">
                <NotificationBell />
              </div>
            </div>
          </header>

          <main className="px-4 md:px-6 py-6 max-w-[1400px]" data-testid="app-shell-content" data-active-path={loc.pathname}>
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
