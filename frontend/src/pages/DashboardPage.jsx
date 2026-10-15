import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Settings2 } from "lucide-react";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { CardsSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import DashboardCustomizer from "@/components/home/DashboardCustomizer";
import { KpiWidget, ListWidget, SummaryWidget } from "@/components/home/HomeWidgets";
import { toast } from "sonner";

// Shared by Finance, Shop Operations and Team dashboards.
export function DashboardStatCard({ label, value, helper, icon: Icon, to, testId }) {
  return (
    <Link
      to={to}
      className="block rounded-lg border bg-card p-4 shadow-[0_1px_0_rgba(15,23,42,0.04)] transition-colors hover:bg-muted/30"
      data-testid={testId}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-medium text-muted-foreground">{label}</div>
          <div className="mt-2 text-3xl font-semibold tabular-nums font-display" data-testid="dashboard-stat-card-value">{value}</div>
          {helper && <div className="mt-1 text-xs text-muted-foreground">{helper}</div>}
        </div>
        {Icon && (
          <div className="grid size-9 place-items-center rounded-lg bg-muted text-muted-foreground">
            <Icon className="size-4" aria-hidden="true" />
          </div>
        )}
      </div>
    </Link>
  );
}

export function DashboardListCard({ title, testId, empty, children, viewAllTo }) {
  return (
    <div className="rounded-lg border bg-card" data-testid={testId}>
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="font-medium">{title}</div>
        {viewAllTo && <Link className="text-xs text-muted-foreground hover:underline" to={viewAllTo}>View all</Link>}
      </div>
      <div>{children || <div className="px-4 py-6 text-sm text-muted-foreground">{empty}</div>}</div>
    </div>
  );
}

function localDayBounds() {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { day_start: start.toISOString(), day_end: end.toISOString() };
}

/**
 * F2 — Customizable Home. The backend decides which widgets this user may
 * use and supplies their data; the layout is saved per user and per shop.
 */
export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [customizing, setCustomizing] = useState(false);
  const day = useMemo(localDayBounds, []);
  const queryKey = ["home-dashboard", day.day_start];

  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: async () => (await api.get("/dashboard/home", { params: day })).data,
  });

  const saveLayout = useMutation({
    mutationFn: async (layout) => (await api.put("/dashboard/home/layout", layout)).data.layout,
    onSuccess: (layout) => {
      queryClient.setQueryData(queryKey, (current) => (current ? { ...current, layout } : current));
      queryClient.invalidateQueries({ queryKey: ["home-dashboard"] });
    },
    onError: (err) => toast.error(extractError(err, "Couldn't save your Home layout.")),
  });
  const resetLayout = useMutation({
    mutationFn: async () => (await api.delete("/dashboard/home/layout")).data.layout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["home-dashboard"] });
      setCustomizing(false);
      toast.success("Home restored to the default layout.");
    },
    onError: (err) => toast.error(extractError(err, "Couldn't restore the default layout.")),
  });

  const customizeButton = (
    <Button type="button" variant="outline" size="sm" onClick={() => setCustomizing(true)} disabled={!data} data-testid="home-customize-button">
      <Settings2 className="size-4" aria-hidden="true" />
      Customize
    </Button>
  );

  if (isLoading) {
    return (
      <div className="space-y-4" data-testid="home-dashboard-page">
        <PageHeader title="Home" subtitle="Your shop at a glance." testId="dashboard-header" />
        <CardsSkeleton />
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="space-y-4" data-testid="home-dashboard-page">
        <PageHeader title="Home" subtitle="Your shop at a glance." testId="dashboard-header" />
        <EmptyState title="Couldn't load Home" description="Try refreshing the page." />
      </div>
    );
  }

  const byKey = new Map(data.widgets.map((w) => [w.key, w]));
  const hidden = new Set(data.layout.hidden);
  const collapsed = new Set(data.layout.collapsed);
  const visible = data.layout.order.filter((key) => byKey.has(key) && !hidden.has(key)).map((key) => byKey.get(key));
  const kpis = visible.filter((w) => w.kind === "kpi");
  const summaries = visible.filter((w) => w.kind === "summary");
  const lists = visible.filter((w) => w.kind === "list");

  const toggleCollapsed = (key) => {
    const next = new Set(collapsed);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    saveLayout.mutate({ ...data.layout, collapsed: [...next] });
  };
  const listWidgets = lists.map((w) => (
    <ListWidget key={w.key} widget={w} data={data.data[w.key]} collapsed={collapsed.has(w.key)} onToggleCollapsed={() => toggleCollapsed(w.key)} />
  ));

  return (
    <div className="mx-auto max-w-[1540px] space-y-3" data-testid="home-dashboard-page">
      <PageHeader title="Home" subtitle="Your shop at a glance." actions={customizeButton} testId="dashboard-header" />

      {visible.length === 0 ? (
        <div className="rounded-lg border bg-card px-4 py-10 text-center" data-testid="home-all-hidden">
          <p className="text-sm text-muted-foreground">All Home widgets are hidden.</p>
          <Button type="button" size="sm" className="mt-3" onClick={() => setCustomizing(true)}>Customize Home</Button>
        </div>
      ) : (
        <>
          {kpis.length > 0 && (
            <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6" data-testid="home-kpi-zone">
              {kpis.map((w) => <KpiWidget key={w.key} widget={w} data={data.data[w.key]} />)}
            </div>
          )}
          {summaries.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
              <div className={`grid content-start gap-3 lg:col-span-8 ${summaries.length > 1 ? "md:grid-cols-2" : ""}`} data-testid="home-summary-zone">
                {summaries.map((w) => <SummaryWidget key={w.key} widget={w} data={data.data[w.key]} />)}
              </div>
              {lists.length > 0 && (
                <aside className="space-y-3 lg:col-span-4" data-testid="home-list-column" aria-label="Lists">{listWidgets}</aside>
              )}
            </div>
          ) : (
            lists.length > 0 && (
              <div className="grid content-start gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="home-list-column">{listWidgets}</div>
            )
          )}
        </>
      )}

      {data.widgets.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Your account has no Home widgets available. <Link className="underline" to="/help">Get help</Link>
        </p>
      )}

      <DashboardCustomizer
        open={customizing}
        layout={data.layout}
        widgets={data.widgets}
        restricted={data.restricted}
        saving={saveLayout.isPending || resetLayout.isPending}
        onOpenChange={setCustomizing}
        onRestore={() => resetLayout.mutate()}
        onSave={(layout) => saveLayout.mutate(layout, { onSuccess: () => { setCustomizing(false); toast.success("Home layout saved."); } })}
      />
    </div>
  );
}
