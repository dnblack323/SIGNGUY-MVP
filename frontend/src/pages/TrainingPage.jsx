import { useMemo, useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import EmptyState from "@/components/common/EmptyState";
import StatusPill from "@/components/common/StatusPill";
import { useAuth } from "@/auth/AuthContext";
import { toast } from "sonner";
import { formatDate } from "@/lib/format";
import { Archive, GraduationCap, Plus, UserPlus } from "lucide-react";
import TrainingDefinitionDialog from "@/components/training/TrainingDefinitionDialog";
import AssignTrainingDialog from "@/components/training/AssignTrainingDialog";
import AssignmentDetailDialog from "@/components/training/AssignmentDetailDialog";

const ASSIGNMENT_STATUSES = ["not_started", "in_progress", "pending_signoff", "completed", "failed", "expired", "cancelled"];

function DefinitionsTab({ canManage }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["training-definitions"], queryFn: async () => (await api.get("/training/definitions")).data.items });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const archive = useMutation({
    mutationFn: async (id) => (await api.post(`/training/definitions/${id}/archive`)).data,
    onSuccess: () => { toast.success("Archived"); qc.invalidateQueries({ queryKey: ["training-definitions"] }); },
    onError: (e) => toast.error(extractError(e)),
  });

  const items = data || [];
  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        {canManage && (
          <Button onClick={() => { setEditing(null); setDialogOpen(true); }} data-testid="training-create-definition-button">
            <Plus className="size-4 mr-1" />New Training
          </Button>
        )}
      </div>
      {isLoading ? <div className="text-sm text-muted-foreground">Loading…</div> : items.length === 0 ? (
        <EmptyState icon={GraduationCap} title="No Training defined yet" description="Create reading, quiz, or practical-demonstration Training content." />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="training-definitions-table">
            <TableHeader><TableRow><TableHead>Title</TableHead><TableHead>Type</TableHead><TableHead>Signoff</TableHead><TableHead>Active</TableHead><TableHead /></TableRow></TableHeader>
            <TableBody>
              {items.map((d) => (
                <TableRow key={d.id} data-testid={`training-definition-row-${d.id}`}>
                  <TableCell className="font-medium">
                    <button className="hover:underline" onClick={() => { setEditing(d); setDialogOpen(true); }} data-testid={`training-definition-edit-${d.id}`}>{d.title}</button>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground capitalize">{d.training_type.replace(/_/g, " ")}{d.training_type === "quiz" ? ` (${d.quiz_questions?.length || 0}q)` : ""}</TableCell>
                  <TableCell className="text-sm">{d.practical_signoff_required ? "Required" : "—"}</TableCell>
                  <TableCell><StatusPill kind="employee" value={d.active ? "active" : "inactive"} /></TableCell>
                  <TableCell>
                    {canManage && d.active && (
                      <Button size="sm" variant="ghost" onClick={() => archive.mutate(d.id)} data-testid={`training-definition-archive-${d.id}`}><Archive className="size-4" /></Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <TrainingDefinitionDialog open={dialogOpen} onOpenChange={setDialogOpen} editing={editing} />
    </div>
  );
}

function AssignmentsTab({ canManage }) {
  const [status, setStatus] = useState("");
  const [assignOpen, setAssignOpen] = useState(false);
  const [detail, setDetail] = useState(null); // {id, employeeName}

  const { data: assignments, isLoading } = useQuery({
    queryKey: ["training-assignments", status],
    queryFn: async () => (await api.get("/training/assignments", { params: { status: status || undefined } })).data.items,
  });
  const { data: employees } = useQuery({ queryKey: ["employees-for-training"], queryFn: async () => (await api.get("/employees")).data.items || [] });
  const { data: definitions } = useQuery({ queryKey: ["training-definitions"], queryFn: async () => (await api.get("/training/definitions")).data.items });

  const employeesById = useMemo(() => {
    const m = {};
    (employees || []).forEach((e) => { m[e.id] = e; });
    return m;
  }, [employees]);

  const items = assignments || [];
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <Select value={status || "__all__"} onValueChange={(v) => setStatus(v === "__all__" ? "" : v)}>
          <SelectTrigger className="w-[200px]" data-testid="training-assignments-status-filter"><SelectValue placeholder="All statuses" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All statuses</SelectItem>
            {ASSIGNMENT_STATUSES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s.replace(/_/g, " ")}</SelectItem>)}
          </SelectContent>
        </Select>
        {canManage && (
          <Button onClick={() => setAssignOpen(true)} data-testid="training-open-assign-button"><UserPlus className="size-4 mr-1" />Assign Training</Button>
        )}
      </div>
      {isLoading ? <div className="text-sm text-muted-foreground">Loading…</div> : items.length === 0 ? (
        <EmptyState icon={GraduationCap} title="No Training assignments" description="Assign Training to an Employee to get started." />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table data-testid="training-assignments-table">
            <TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Training</TableHead><TableHead>Status</TableHead><TableHead>Due</TableHead><TableHead>Score</TableHead></TableRow></TableHeader>
            <TableBody>
              {items.map((a) => (
                <TableRow
                  key={a.id} className="hover:bg-muted/40 cursor-pointer" data-testid={`training-assignment-row-${a.id}`}
                  onClick={() => setDetail({ id: a.id, employeeName: employeesById[a.employee_id]?.name || a.employee_id })}
                >
                  <TableCell className="font-medium">{employeesById[a.employee_id]?.name || a.employee_id}</TableCell>
                  <TableCell>{a.training_title || "—"}</TableCell>
                  <TableCell><StatusPill kind="training_assignment" value={a.status} /></TableCell>
                  <TableCell className={a.overdue ? "text-rose-700 font-medium" : "text-muted-foreground"}>{a.due_date ? formatDate(a.due_date) : "—"}{a.overdue ? " · overdue" : ""}</TableCell>
                  <TableCell className="tabular-nums">{typeof a.latest_score === "number" ? `${a.latest_score}%` : "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <AssignTrainingDialog open={assignOpen} onOpenChange={setAssignOpen} employees={employees} definitions={definitions} />
      {detail && <AssignmentDetailDialog assignmentId={detail.id} employeeName={detail.employeeName} open={!!detail} onOpenChange={(o) => !o && setDetail(null)} />}
    </div>
  );
}

export default function TrainingPage() {
  const { hasPerm } = useAuth();
  const canManage = hasPerm("training:manage");
  return (
    <div className="space-y-4" data-testid="training-page">
      <PageHeader title="Training" subtitle="Bounded training content, assignments, quizzes and practical signoffs." />
      {!canManage ? (
        <EmptyState title="No access" description="You don't have permission to view Training." />
      ) : (
        <Tabs defaultValue="definitions" data-testid="training-tabs">
          <TabsList>
            <TabsTrigger value="definitions" data-testid="training-tab-definitions">Definitions</TabsTrigger>
            <TabsTrigger value="assignments" data-testid="training-tab-assignments">Assignments</TabsTrigger>
          </TabsList>
          <TabsContent value="definitions"><DefinitionsTab canManage={canManage} /></TabsContent>
          <TabsContent value="assignments"><AssignmentsTab canManage={canManage} /></TabsContent>
        </Tabs>
      )}
    </div>
  );
}
