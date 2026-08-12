import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { CardsSkeleton } from "@/components/common/LoadingSkeleton";
import StatusPill from "@/components/common/StatusPill";
import { centsToDollarsString, relativeTime } from "@/lib/format";
import { ShoppingBag, FileText, Wrench, Receipt, ChevronRight } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { AuditTimeline } from "@/components/audit/AuditTimeline";

function StatCard({ label, value, helper, icon: Icon, to, testId }) {
  return (
    <Link to={to} className="rounded-xl border bg-card p-4 shadow-[0_1px_0_rgba(15,23,42,0.04)] hover:bg-muted/30 transition-colors block" data-testid={testId}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs font-medium text-muted-foreground">{label}</div>
          <div className="mt-2 text-3xl font-semibold tabular-nums font-display" data-testid="dashboard-stat-card-value">{value}</div>
          {helper && <div className="mt-1 text-xs text-muted-foreground">{helper}</div>}
        </div>
        {Icon && <div className="grid size-9 place-items-center rounded-lg bg-muted text-muted-foreground"><Icon className="size-4" /></div>}
      </div>
    </Link>
  );
}

function ListCard({ title, testId, empty, children, viewAllTo }) {
  return (
    <div className="rounded-xl border bg-card" data-testid={testId}>
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="font-medium">{title}</div>
        {viewAllTo && <Link className="text-xs text-muted-foreground hover:underline" to={viewAllTo}>View all</Link>}
      </div>
      <div>{children || <div className="px-4 py-6 text-sm text-muted-foreground">{empty}</div>}</div>
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/dashboard/summary")).data,
  });

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <PageHeader title="Overview" subtitle="What needs attention across shop operations" testId="dashboard-header" />
      {isLoading ? (
        <CardsSkeleton />
      ) : error ? (
        <EmptyState title="Couldn't load dashboard" description="Try refreshing the page." />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard testId="stat-active-orders" label="Active orders" value={data.counts.active_orders} icon={ShoppingBag} to="/orders" helper="Confirmed or in production" />
            <StatCard testId="stat-quotes-follow-up" label="Quotes needing follow-up" value={data.counts.quotes_follow_up} icon={FileText} to="/quotes" helper="Sent, not yet decided" />
            <StatCard testId="stat-work-orders-attention" label="Work orders in progress" value={data.counts.work_orders_attention} icon={Wrench} to="/work-orders" helper="Or on hold" />
            <StatCard testId="stat-unpaid-invoices" label="Unpaid invoices" value={data.counts.unpaid_invoices} icon={Receipt} to="/invoices" helper="Sent, partially paid, overdue" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-6">
              <ListCard title="Quotes needing follow-up" testId="list-quotes-follow-up" empty="No quotes waiting." viewAllTo="/quotes">
                {data.quotes_follow_up.length > 0 && (
                  <ul className="divide-y">
                    {data.quotes_follow_up.slice(0, 6).map((q) => (
                      <li key={q.id}>
                        <Link className="flex items-center justify-between px-4 py-3 hover:bg-muted/40" to={`/quotes/${q.id}`}>
                          <div className="min-w-0">
                            <div className="text-sm truncate"><span className="mono text-xs text-muted-foreground mr-2">Q-{q.number}</span>{q.job_name}</div>
                            <div className="text-xs text-muted-foreground">{relativeTime(q.created_at)}</div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm tabular-nums">{centsToDollarsString(q.total_cents)}</span>
                            <StatusPill kind="quote" value={q.status} />
                            <ChevronRight className="size-4 text-muted-foreground" />
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </ListCard>
            </div>

            <div className="lg:col-span-6">
              <ListCard title="Work orders in production" testId="list-work-orders-attention" empty="Nothing in the shop right now." viewAllTo="/work-orders">
                {data.work_orders_attention.length > 0 && (
                  <ul className="divide-y">
                    {data.work_orders_attention.slice(0, 6).map((w) => (
                      <li key={w.id}>
                        <Link className="flex items-center justify-between px-4 py-3 hover:bg-muted/40" to={`/work-orders/${w.id}`}>
                          <div className="min-w-0">
                            <div className="text-sm truncate"><span className="mono text-xs text-muted-foreground mr-2">W-{w.number}</span>Order O-…</div>
                            <div className="text-xs text-muted-foreground">{relativeTime(w.created_at)}</div>
                          </div>
                          <StatusPill kind="production" value={w.production_status} />
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </ListCard>
            </div>

            <div className="lg:col-span-7">
              <ListCard title="Unpaid invoices" testId="list-unpaid-invoices" empty="Nothing outstanding 🎉 " viewAllTo="/invoices">
                {data.unpaid_invoices.length > 0 && (
                  <ul className="divide-y">
                    {data.unpaid_invoices.slice(0, 8).map((inv) => (
                      <li key={inv.id}>
                        <Link className="flex items-center justify-between px-4 py-3 hover:bg-muted/40" to={`/invoices/${inv.id}`}>
                          <div className="min-w-0">
                            <div className="text-sm truncate"><span className="mono text-xs text-muted-foreground mr-2">I-{inv.number}</span>{inv.title}</div>
                            <div className="text-xs text-muted-foreground">Due {inv.due_date || "—"}</div>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-sm tabular-nums">{centsToDollarsString(inv.total_cents)}</span>
                            <StatusPill kind="invoice" value={inv.status} />
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </ListCard>
            </div>

            <div className="lg:col-span-5 space-y-6">
              <ListCard title="Recent emails" testId="list-recent-emails" empty="No emails sent yet." viewAllTo="/email-history">
                {data.recent_emails.length > 0 && (
                  <ul className="divide-y">
                    {data.recent_emails.slice(0, 6).map((e) => (
                      <li key={e.id} className="px-4 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-sm truncate">{e.subject}</div>
                          <StatusPill kind="email" value={e.status} />
                        </div>
                        <div className="text-xs text-muted-foreground">to {e.to_email} · {relativeTime(e.created_at)}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </ListCard>

              <ListCard title="Recent activity" testId="list-recent-activity" empty="No activity yet.">
                <div className="p-3">
                  <AuditTimeline events={data.recent_activity} />
                </div>
              </ListCard>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
