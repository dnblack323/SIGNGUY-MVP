import { useEffect, useState, useCallback } from "react";
import { CheckCheck, X } from "lucide-react";
import api from "@/lib/api";
import { cn } from "@/lib/utils";

function severityDot(s) {
  const color =
    s === "error" ? "bg-red-500" :
    s === "warning" ? "bg-amber-500" :
    s === "success" ? "bg-emerald-500" :
    "bg-blue-500";
  return <span className={cn("inline-block size-2 rounded-full mt-1.5 mr-2 shrink-0", color)} />;
}

export default function NotificationPanel({ onChange, onClose }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/notifications", { params: { limit: 20 } });
      setItems(res.data?.items || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const markAllRead = async () => {
    const unread = items.filter((n) => n.status === "unread").map((n) => n.id);
    if (unread.length === 0) return;
    await api.post("/notifications/read-many", { ids: unread });
    await load();
    onChange?.();
  };

  const markRead = async (id) => {
    await api.post(`/notifications/${id}/read`);
    await load();
    onChange?.();
  };

  const dismiss = async (id) => {
    await api.post(`/notifications/${id}/dismiss`);
    await load();
    onChange?.();
  };

  return (
    <div data-testid="notification-panel" className="flex flex-col max-h-[420px]">
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <div className="text-sm font-semibold">Notifications</div>
        <button
          type="button"
          onClick={markAllRead}
          data-testid="notifications-mark-all-read"
          className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <CheckCheck className="size-3.5" /> Mark all read
        </button>
      </div>
      <div className="overflow-y-auto flex-1">
        {loading && <div className="p-4 text-xs text-muted-foreground">Loading…</div>}
        {!loading && items.length === 0 && (
          <div data-testid="notifications-empty" className="p-6 text-center text-xs text-muted-foreground">
            You're all caught up.
          </div>
        )}
        {items.map((n) => (
          <div
            key={n.id}
            data-testid={`notification-item-${n.id}`}
            className={cn(
              "px-3 py-2 border-b flex items-start gap-1",
              n.status === "unread" ? "bg-muted/30" : "bg-transparent",
            )}
          >
            {severityDot(n.severity)}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{n.title}</div>
              {n.body && <div className="text-xs text-muted-foreground line-clamp-2">{n.body}</div>}
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">
                {n.module} · {new Date(n.created_at).toLocaleString()}
              </div>
            </div>
            <div className="flex flex-col gap-1">
              {n.status === "unread" && (
                <button
                  type="button"
                  onClick={() => markRead(n.id)}
                  data-testid={`notification-mark-read-${n.id}`}
                  className="text-[10px] px-1.5 py-0.5 rounded border hover:bg-muted"
                >
                  Read
                </button>
              )}
              <button
                type="button"
                onClick={() => dismiss(n.id)}
                data-testid={`notification-dismiss-${n.id}`}
                className="text-[10px] px-1.5 py-0.5 rounded border hover:bg-muted inline-flex items-center gap-0.5"
              >
                <X className="size-3" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
