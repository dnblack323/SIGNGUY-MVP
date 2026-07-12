import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Megaphone, Users } from "lucide-react";
import { relativeTime } from "@/lib/format";
import EmptyState from "@/components/common/EmptyState";

const STATUS_LABELS = { active: "Active", suspended: "Suspended", inactive: "Inactive", terminated: "Terminated", archived: "Archived" };

export default function TeamDashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["team-dashboard"],
    queryFn: async () => (await api.get("/team/dashboard")).data,
  });

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading…</div>;
  const counts = data?.employee_status_counts || {};
  const announcements = data?.announcements || [];

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
    </div>
  );
}
