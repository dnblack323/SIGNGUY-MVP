import { useEffect, useState, useCallback } from "react";
import { Bell } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import NotificationPanel from "@/components/notifications/NotificationPanel";
import api from "@/lib/api";
import { cn } from "@/lib/utils";

export default function NotificationBell({
  className,
  iconClassName,
  badgeClassName,
  testId = "notification-bell",
  tooltip,
}) {
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await api.get("/notifications/unread-count");
      setCount(Number(res.data?.unread || 0));
    } catch {
      /* silent — bell is best-effort */
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 60_000);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid={testId}
          className={cn("relative grid size-9 place-items-center rounded-lg transition-colors hover:bg-muted/60", className)}
          aria-label="Notifications"
          title={tooltip}
        >
          <Bell className={cn("size-4", iconClassName)} />
          {count > 0 && (
            <span
              data-testid="notification-unread-badge"
              className={cn(
                "absolute -right-0.5 -top-0.5 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground",
                badgeClassName,
              )}
            >
              {count > 99 ? "99+" : count}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        side="bottom"
        className="w-[360px] p-0"
        data-testid="notification-popover"
      >
        <NotificationPanel onChange={refresh} onClose={() => setOpen(false)} />
      </PopoverContent>
    </Popover>
  );
}
