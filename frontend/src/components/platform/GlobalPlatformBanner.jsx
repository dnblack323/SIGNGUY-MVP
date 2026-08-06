import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Info, Wrench, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { cn } from "@/lib/utils";

const SEVERITY_STYLES = {
  info: "border-blue-200 bg-blue-50 text-blue-950",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  critical: "border-red-200 bg-red-50 text-red-950",
};

export default function GlobalPlatformBanner() {
  const [announcement, setAnnouncement] = useState(null);
  const [maintenance, setMaintenance] = useState(null);
  const [dismissed, setDismissed] = useState(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem("signguy.dismissedPlatformBanners") || "[]"));
    } catch {
      return new Set();
    }
  });

  useEffect(() => {
    let mounted = true;
    const load = () => Promise.allSettled([api.get("/platform/announcement"), api.get("/platform/maintenance")]).then((results) => {
      if (!mounted) return;
      if (results[0].status === "fulfilled") setAnnouncement(results[0].value.data);
      if (results[1].status === "fulfilled") setMaintenance(results[1].value.data);
    });
    load();
    const timer = window.setInterval(load, 60000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  const banners = useMemo(() => {
    const items = [];
    if (maintenance?.enabled) {
      items.push({
        id: `maintenance:${maintenance.started_at || "active"}`,
        icon: Wrench,
        message: maintenance.message || "SignGuy AI is in maintenance mode.",
        severity: "critical",
        dismissable: false,
      });
    }
    if (announcement?.active && announcement?.message) {
      items.push({
        id: `announcement:${announcement.updated_at || announcement.message}`,
        icon: announcement.severity === "info" ? Info : AlertTriangle,
        message: announcement.message,
        severity: announcement.severity || "info",
        dismissable: announcement.dismissable !== false,
      });
    }
    return items.filter((item) => !dismissed.has(item.id));
  }, [announcement, dismissed, maintenance]);

  if (banners.length === 0) return null;

  return (
    <div className="w-full" data-testid="global-platform-banner-stack">
      {banners.map((item) => {
        const Icon = item.icon;
        return (
          <div
            key={item.id}
            className={cn("flex min-h-10 items-center justify-center gap-3 border-b px-4 py-2 text-sm", SEVERITY_STYLES[item.severity] || SEVERITY_STYLES.info)}
            data-testid={`global-platform-banner-${item.severity}`}
          >
            <Icon className="size-4 shrink-0" />
            <div className="max-w-[1100px] leading-5">{item.message}</div>
            {item.dismissable && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7 shrink-0 text-current hover:bg-black/5"
                aria-label="Dismiss platform announcement"
                onClick={() => setDismissed((prev) => {
                  const next = new Set([...prev, item.id]);
                  localStorage.setItem("signguy.dismissedPlatformBanners", JSON.stringify([...next]));
                  return next;
                })}
              >
                <X className="size-4" />
              </Button>
            )}
          </div>
        );
      })}
    </div>
  );
}
