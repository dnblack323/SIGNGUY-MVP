import { useEffect, useState, useCallback } from "react";
import { Bell } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import NotificationPanel from "@/components/notifications/NotificationPanel";
import api from "@/lib/api";

export default function NotificationBell() {
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
          data-testid="notification-bell"
          className="relative size-9 grid place-items-center rounded-lg hover:bg-muted/60 transition-colors"
          aria-label="Notifications"
        >
          <Bell className="size-4" />
          {count > 0 && (
            <span
              data-testid="notification-unread-badge"
              className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 grid place-items-center rounded-full text-[10px] font-semibold bg-primary text-primary-foreground"
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
