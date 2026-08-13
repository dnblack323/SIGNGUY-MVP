import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { CardsSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { DashboardListCard, DashboardStatCard } from "@/pages/DashboardPage";
import { centsToDollarsString, relativeTime } from "@/lib/format";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  FileText,
  MessageSquare,
  ShoppingBag,
  Wrench,
} from "lucide-react";

function OperationalRow({ to, primary, secondary, statusKind, statusValue, value }) {
  return (
    <Link className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-muted/40" to={to}>
      <div className="min-w-0">
        <div className="truncate text-sm">{primary}</div>
        {secondary && <div className="text-xs text-muted-foreground">{secondary}</div>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {value && <span className="text-sm tabular-nums">{value}</span>}
        {statusKind && <StatusPill kind={statusKind} value={statusValue} />}
        <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
      </div>
    </Link>
  );
}

function OperationsSnapshot({ data }) {
  const productionCount = data.work_orders_attention.length;
  const orderCount = data.active_orders.length;
  const quoteCount = data.quotes_follow_up.length;
  return (
    <DashboardListCard title="Operational Snapshot" testId="shop-operations-snapshot">
      <div className="space-y-3 p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2"><ShoppingBag className="size-4 text-blue-700" aria-hidden="true" />Active orders</span>
          <span className="font-semibold tabular-nums">{orderCount}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2"><FileText className="size-4 text-blue-700" aria-hidden="true" />Quotes needing follow-up</span>
          <span className="font-semibold tabular-nums">{quoteCount}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2"><Wrench className="size-4 text-orange-700" aria-hidden="true" />Production attention</span>
          <span className="font-semibold tabular-nums">{productionCount}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden="true">
          <div className="h-full bg-blue-600" style={{ width: `${Math.min(100, (orderCount + quoteCount + productionCount) * 10)}%` }} />
        </div>
      </div>
    </DashboardListCard>
  );
}

export default function ShopOperationsOverviewPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["shop-operations-overview"],
    queryFn: async () => (await api.get("/dashboard/summary")).data,
  });

  return (
    <div className="space-y-5" data-testid="shop-operations-overview-page">
      <PageHeader title="Overview" subtitle="What needs attention across customer, sales, approval, order, and production workflows." testId="shop-operations-overview-header" />
      {isLoading ? (
        <CardsSkeleton />
      ) : error ? (
        <EmptyState title="Couldn't load Shop Operations" description="Try refreshing the page." />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <DashboardStatCard testId="shop-stat-active-orders" label="Active orders" value={data.counts.active_orders} icon={ShoppingBag} to="/orders" helper="Confirmed or in production" />
            <DashboardStatCard testId="shop-stat-quotes-follow-up" label="Quotes need follow-up" value={data.counts.quotes_follow_up} icon={FileText} to="/quotes" helper="Sent, not yet decided" />
            <DashboardStatCard testId="shop-stat-production-attention" label="Production attention" value={data.counts.work_orders_attention} icon={Wrench} to="/work-orders" helper="In progress or on hold" />
            <DashboardStatCard testId="shop-stat-approval-readiness" label="Approval readiness" value={data.quotes_follow_up.length + data.work_orders_attention.length} icon={CheckCircle2} to="/approval-center" helper="Existing records needing action" />
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
            <div className="space-y-5 lg:col-span-8">
              <DashboardListCard title="Sales Follow-up Queue" testId="shop-list-sales-follow-up" empty="No quotes waiting." viewAllTo="/quotes">
                {data.quotes_follow_up.length > 0 && (
                  <ul className="divide-y">
                    {data.quotes_follow_up.slice(0, 6).map((q) => (
                      <li key={q.id}>
                        <OperationalRow
                          to={`/quotes/${q.id}`}
                          primary={<><span className="mono mr-2 text-xs text-muted-foreground">Q-{q.number}</span>{q.job_name}</>}
                          secondary={relativeTime(q.created_at)}
                          statusKind="quote"
                          statusValue={q.status}
                          value={centsToDollarsString(q.total_cents)}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </DashboardListCard>

              <DashboardListCard title="Production Attention" testId="shop-list-production-attention" empty="Nothing in the shop needs attention right now." viewAllTo="/work-orders">
                {data.work_orders_attention.length > 0 && (
                  <ul className="divide-y">
                    {data.work_orders_attention.slice(0, 6).map((w) => (
                      <li key={w.id}>
                        <OperationalRow
                          to={`/work-orders/${w.id}`}
                          primary={<><span className="mono mr-2 text-xs text-muted-foreground">W-{w.number}</span>Work Order attention</>}
                          secondary={relativeTime(w.created_at)}
                          statusKind="production"
                          statusValue={w.production_status}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </DashboardListCard>
            </div>

            <div className="space-y-5 lg:col-span-4">
              <OperationsSnapshot data={data} />
              <DashboardListCard title="Approval & Customer Signals" testId="shop-list-approval-signals" empty="No approval signals from current records." viewAllTo="/approval-center">
                {(data.quotes_follow_up.length > 0 || data.active_orders.length > 0) && (
                  <ul className="divide-y">
                    {data.quotes_follow_up.slice(0, 3).map((q) => (
                      <li key={`approval-${q.id}`}>
                        <OperationalRow
                          to={`/quotes/${q.id}`}
                          primary={<><MessageSquare className="mr-2 inline size-4 text-blue-700" aria-hidden="true" />Quote follow-up</>}
                          secondary={q.job_name}
                          statusKind="quote"
                          statusValue={q.status}
                        />
                      </li>
                    ))}
                    {data.active_orders.slice(0, 3).map((order) => (
                      <li key={`order-${order.id}`}>
                        <OperationalRow
                          to={`/orders/${order.id}`}
                          primary={<><AlertTriangle className="mr-2 inline size-4 text-orange-700" aria-hidden="true" />Order readiness check</>}
                          secondary={order.job_name || `Order ${order.number}`}
                          statusKind="order"
                          statusValue={order.status}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </DashboardListCard>

              <DashboardListCard title="Operational Activity" testId="shop-list-operational-activity" empty="No operational activity yet.">
                {data.recent_activity.length > 0 && (
                  <ul className="divide-y">
                    {data.recent_activity.slice(0, 5).map((event) => (
                      <li key={event.id} className="px-4 py-3">
                        <div className="flex items-start gap-2 text-sm">
                          <ClipboardList className="mt-0.5 size-4 shrink-0 text-blue-700" aria-hidden="true" />
                          <div className="min-w-0">
                            <div className="truncate">{event.summary || event.action || "Activity"}</div>
                            <div className="text-xs text-muted-foreground">{relativeTime(event.created_at)}</div>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </DashboardListCard>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
