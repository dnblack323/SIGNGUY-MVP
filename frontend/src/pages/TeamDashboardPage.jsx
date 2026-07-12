import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Clock, Coffee, FileText, Megaphone, Users } from "lucide-react";
import { relativeTime } from "@/lib/format";
import EmptyState from "@/components/common/EmptyState";

const STATUS_LABELS = { active: "Active", suspended: "Suspended", inactive: "Inactive", terminated: "Terminated", archived: "Archived" };

export default function TeamDashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["team-dashboard"],
    queryFn: async () => (await api.get("/team/dashboard")).data,
  });
  const { data: timeClockStatus } = useQuery({
    queryKey: ["time-clock-team-status"],
    queryFn: async () => (await api.get("/time-clock/team-status")).data,
    retry: false,
    refetchInterval: 30000,
  });
  const { data: pendingReview } = useQuery({
    queryKey: ["timesheets-pending"],
    queryFn: async () => (await api.get("/timesheets/pending-review")).data,
    retry: false,
  });

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading…</div>;
  const counts = data?.employee_status_counts || {};
  const announcements = data?.announcements || [];
  const pendingCount = pendingReview?.items?.length ?? 0;

  return (
    <div className="space-y-4" data-testid="team-dashboard-page">
      <PageHeader title="Team" subtitle="Who's on the team, at a glance." actions={<Button asChild variant="outline" data-testid="team-dashboard-manage-employees-link"><Link to="/team/employees"><Users className="size-4 mr-1" />Manage employees</Link></Button>} />

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3" data-testid="team-status-counts">
        {Object.entries(STATUS_LABELS).map(([key, label]) => (
          <Card key={key}>
            <CardContent className="p-4">
              <div className="text-2xl font-semibold tabular-nums" data-testid={`team-count-${key}`}>{counts[key] ?? 0}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {timeClockStatus && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="team-time-clock-counts">
          <Card><CardContent className="p-4 flex items-center gap-3"><Clock className="size-5 text-emerald-600" /><div><div className="text-xl font-semibold tabular-nums" data-testid="dashboard-clocked-in-count">{timeClockStatus.clocked_in}</div><div className="text-xs text-muted-foreground">Clocked in</div></div></CardContent></Card>
          <Card><CardContent className="p-4 flex items-center gap-3"><Coffee className="size-5 text-amber-600" /><div><div className="text-xl font-semibold tabular-nums" data-testid="dashboard-on-break-count">{timeClockStatus.on_break}</div><div className="text-xs text-muted-foreground">On break</div></div></CardContent></Card>
          <Card><CardContent className="p-4 flex items-center gap-3"><FileText className="size-5 text-sky-600" /><div><div className="text-xl font-semibold tabular-nums" data-testid="dashboard-open-entries-count">{timeClockStatus.open_entries}</div><div className="text-xs text-muted-foreground">Open entries</div></div></CardContent></Card>
          <Card><CardContent className="p-4 flex items-center gap-3"><Clock className="size-5 text-rose-600" /><div><div className="text-xl font-semibold tabular-nums" data-testid="dashboard-missed-clockouts-count">{timeClockStatus.missed_clock_outs}</div><div className="text-xs text-muted-foreground">Missed clock-outs</div></div></CardContent></Card>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2"><Megaphone className="size-4" />Announcements</CardTitle>
            <Button asChild variant="ghost" size="sm" data-testid="team-dashboard-announcements-link"><Link to="/team/announcements">View all</Link></Button>
          </CardHeader>
          <CardContent>
            {announcements.length === 0 ? (
              <EmptyState icon={Megaphone} title="No active announcements" description="Post one from the Announcements page." />
            ) : (
              <ul className="divide-y" data-testid="team-dashboard-announcements-list">
                {announcements.map((a) => (
                  <li key={a.id} className="py-2">
                    <div className="text-sm font-medium">{a.title}</div>
                    <div className="text-xs text-muted-foreground">{relativeTime(a.published_at)}</div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2"><FileText className="size-4" />Timesheets</CardTitle>
            <Button asChild variant="ghost" size="sm" data-testid="team-dashboard-timesheets-link"><Link to="/team/timesheets">Review</Link></Button>
          </CardHeader>
          <CardContent>
            {pendingCount === 0 ? (
              <EmptyState icon={FileText} title="Nothing awaiting review" description="Timesheets with activity show up here once submitted." />
            ) : (
              <div className="text-sm" data-testid="dashboard-timesheets-awaiting-count">
                <span className="text-2xl font-semibold tabular-nums">{pendingCount}</span> timesheet{pendingCount === 1 ? "" : "s"} awaiting review
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
