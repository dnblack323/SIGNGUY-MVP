import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import PageHeader from "@/components/layout/PageHeader";
import { CardsSkeleton } from "@/components/common/LoadingSkeleton";
import StatusPill from "@/components/common/StatusPill";
import { EmptyState } from "@/components/common/EmptyState";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { centsToDollarsString, formatDate, relativeTime } from "@/lib/format";
import {
  BriefcaseBusiness,
  ChevronRight,
  FileText,
  Receipt,
  ShoppingBag,
  Users,
} from "lucide-react";

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

function SummaryRow({ to, primary, secondary, statusKind, statusValue, value }) {
  const row = (
    <>
      <div className="min-w-0">
        <div className="truncate text-sm">{primary}</div>
        {secondary && <div className="text-xs text-muted-foreground">{secondary}</div>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {value && <span className="text-sm tabular-nums">{value}</span>}
        {statusKind && <StatusPill kind={statusKind} value={statusValue} />}
        <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
      </div>
    </>
  );

  if (!to) return <div className="flex items-center justify-between gap-3 px-4 py-3">{row}</div>;
  return (
    <Link className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-muted/40" to={to}>
      {row}
    </Link>
  );
}

function CrossBusinessSection({ title, icon: Icon, testId, children }) {
  return (
    <section className="rounded-lg border bg-card" data-testid={testId}>
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
        <h2 className="font-medium">{title}</h2>
      </div>
      <div>{children}</div>
    </section>
  );
}

function RestrictedState({ children }) {
  return <div className="px-4 py-6 text-sm text-muted-foreground" data-testid="home-permission-empty">{children}</div>;
}

export default function DashboardPage() {
  const { hasPerm } = useAuth();
  const canViewFinance = hasPerm("invoice:read") || hasPerm("finance:read");
  const canViewTeam = hasPerm("employee:read") || hasPerm("task:read") || hasPerm("timesheet:self");
  const canReviewTimesheets = hasPerm("timesheet:read") || hasPerm("timesheet:manage");

  const { data, isLoading, error } = useQuery({
    queryKey: ["home-dashboard"],
    queryFn: async () => (await api.get("/dashboard/summary")).data,
  });
  const teamDashboard = useQuery({
    queryKey: ["home-team-dashboard"],
    queryFn: async () => (await api.get("/team/dashboard")).data,
    enabled: canViewTeam,
    retry: false,
  });
  const pendingTimesheets = useQuery({
    queryKey: ["home-timesheets-pending"],
    queryFn: async () => (await api.get("/timesheets/pending-review")).data,
    enabled: canReviewTimesheets,
    retry: false,
  });

  return (
    <div className="space-y-5" data-testid="home-dashboard-page">
      <PageHeader title="Home" subtitle="Cross-business attention for the whole company today." testId="dashboard-header" />
      {isLoading ? (
        <CardsSkeleton />
      ) : error ? (
        <EmptyState title="Couldn't load dashboard" description="Try refreshing the page." />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <DashboardStatCard testId="home-stat-shop-operations" label="Shop operations" value={data.counts.active_orders} icon={ShoppingBag} to="/shop-operations" helper="Active orders needing oversight" />
            <DashboardStatCard testId="home-stat-quotes-follow-up" label="Sales follow-up" value={data.counts.quotes_follow_up} icon={FileText} to="/quotes" helper="Sent quotes awaiting decisions" />
            <DashboardStatCard testId="home-stat-finance" label="Finance attention" value={canViewFinance ? data.counts.unpaid_invoices : "-"} icon={Receipt} to="/finance" helper={canViewFinance ? "Open invoice balances" : "Restricted by permission"} />
            <DashboardStatCard testId="home-stat-team" label="Team signals" value={canReviewTimesheets ? (pendingTimesheets.data?.items?.length ?? 0) : "-"} icon={Users} to="/team" helper={canViewTeam ? "Team and timesheet signals" : "Restricted by permission"} />
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
            <div className="space-y-5 lg:col-span-7">
              <CrossBusinessSection title="Shop Operations Attention" icon={BriefcaseBusiness} testId="home-section-shop-operations">
                {(data.quotes_follow_up.length > 0 || data.work_orders_attention.length > 0) ? (
                  <ul className="divide-y">
                    {data.quotes_follow_up.slice(0, 3).map((q) => (
                      <li key={q.id}>
                        <SummaryRow
                          to={`/quotes/${q.id}`}
                          primary={<><span className="mono mr-2 text-xs text-muted-foreground">Q-{q.number}</span>{q.job_name}</>}
                          secondary={relativeTime(q.created_at)}
                          statusKind="quote"
                          statusValue={q.status}
                          value={centsToDollarsString(q.total_cents)}
                        />
                      </li>
                    ))}
                    {data.work_orders_attention.slice(0, 3).map((w) => (
                      <li key={w.id}>
                        <SummaryRow
                          to={`/work-orders/${w.id}`}
                          primary={<><span className="mono mr-2 text-xs text-muted-foreground">W-{w.number}</span>Production attention</>}
                          secondary={relativeTime(w.created_at)}
                          statusKind="production"
                          statusValue={w.production_status}
                        />
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="px-4 py-6 text-sm text-muted-foreground">No shop operations attention items from current records.</div>
                )}
              </CrossBusinessSection>

              <CrossBusinessSection title="Business & Finance" icon={Receipt} testId="home-section-business-finance">
                {!canViewFinance ? (
                  <RestrictedState>Finance information is hidden because this account does not have finance or invoice access.</RestrictedState>
                ) : data.unpaid_invoices.length > 0 ? (
                  <ul className="divide-y">
                    {data.unpaid_invoices.slice(0, 5).map((inv) => (
                      <li key={inv.id}>
                        <SummaryRow
                          to={`/invoices/${inv.id}`}
                          primary={<><span className="mono mr-2 text-xs text-muted-foreground">I-{inv.number}</span>{inv.title}</>}
                          secondary={`Due ${formatDate(inv.due_date) || "not set"}`}
                          statusKind="invoice"
                          statusValue={inv.status}
                          value={centsToDollarsString(inv.total_cents)}
                        />
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="px-4 py-6 text-sm text-muted-foreground">No unpaid invoice attention items from current records.</div>
                )}
              </CrossBusinessSection>
            </div>

            <div className="space-y-5 lg:col-span-5">
              <CrossBusinessSection title="Team & Productivity" icon={Users} testId="home-section-team-productivity">
                {!canViewTeam ? (
                  <RestrictedState>Team information is hidden because this account does not have team access.</RestrictedState>
                ) : teamDashboard.isLoading || pendingTimesheets.isLoading ? (
                  <div className="px-4 py-6 text-sm text-muted-foreground">Loading team signals...</div>
                ) : teamDashboard.error && !pendingTimesheets.data ? (
                  <div className="px-4 py-6 text-sm text-muted-foreground">Team summary is unavailable right now.</div>
                ) : (
                  <ul className="divide-y">
                    <li>
                      <SummaryRow
                        to="/team/timesheets"
                        primary="Timesheets awaiting review"
                        secondary="Existing timesheet review queue"
                        value={canReviewTimesheets ? String(pendingTimesheets.data?.items?.length ?? 0) : "Restricted"}
                      />
                    </li>
                    <li>
                      <SummaryRow
                        to="/team"
                        primary="Active team members"
                        secondary="Current team status summary"
                        value={String(teamDashboard.data?.employee_status_counts?.active ?? 0)}
                      />
                    </li>
                  </ul>
                )}
              </CrossBusinessSection>

              <DashboardListCard title="Upcoming & Recent Activity" testId="home-list-recent-activity" empty="No recent activity yet.">
                {data.recent_activity.length > 0 ? (
                  <div className="p-3">
                    <AuditTimeline events={data.recent_activity.slice(0, 6)} />
                  </div>
                ) : (
                  <div className="px-4 py-6 text-sm text-muted-foreground">No recent cross-business activity yet.</div>
                )}
              </DashboardListCard>

              <DashboardListCard title="Recent Emails" testId="home-list-recent-emails" empty="No emails sent yet." viewAllTo="/email-history">
                {data.recent_emails.length > 0 && (
                  <ul className="divide-y">
                    {data.recent_emails.slice(0, 5).map((e) => (
                      <li key={e.id} className="px-4 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="truncate text-sm">{e.subject}</div>
                          <StatusPill kind="email" value={e.status} />
                        </div>
                        <div className="text-xs text-muted-foreground">to {e.to_email} - {relativeTime(e.created_at)}</div>
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
