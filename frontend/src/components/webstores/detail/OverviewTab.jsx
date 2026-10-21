import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TabsContent } from "@/components/ui/tabs";
import WorkspaceTimeline from "@/components/workspace/WorkspaceTimeline";
import api, { extractError } from "@/lib/api";
import { updateWebstore } from "@/lib/webstores";
import { primaryActionFor } from "./WebstoreNextAction";

const UNASSIGNED = "__none__";

function AssigneeSelect({ model }) {
  const { id, refresh, store, users } = model;
  const save = useMutation({
    mutationFn: (value) => updateWebstore(id, { assignee_user_id: value === UNASSIGNED ? null : value }),
    onSuccess: async () => {
      toast.success("Assignee updated");
      await refresh();
    },
    onError: (err) => toast.error(extractError(err)),
  });
  return (
    <Select value={store.assignee_user_id || UNASSIGNED} onValueChange={(value) => save.mutate(value)} disabled={save.isPending}>
      <SelectTrigger className="h-8 w-56" data-testid="webstore-assignee-select">
        <SelectValue placeholder="Unassigned" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
        {users.map((u) => (
          <SelectItem key={u.id} value={u.id}>
            {u.name || u.email}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export default function OverviewTab({ model }) {
  const { formatDateTime, formatLabel, nextAction, ownerAssignment, stage, store } = model;
  const users = useQuery({ queryKey: ["users"], queryFn: async () => (await api.get("/users")).data });
  const userItems = Array.isArray(users.data) ? users.data : users.data?.items || [];
  const primary = primaryActionFor(model);
  const waitingOnOwner = nextAction?.actor === "owner";

  return (
    <TabsContent value="overview" className="space-y-4">
      <WorkspaceTimeline
        title="Webstore progress"
        testId="webstore-timeline"
        stages={(stage?.path || []).map((step) => ({ key: step.key, label: step.staff_label }))}
        currentKey={stage?.key}
        nextAction={
          nextAction && {
            heading: waitingOnOwner ? "Waiting on owner" : "Next action",
            text: nextAction.staff_text,
          }
        }
        blockers={(nextAction?.blockers || [])
          .filter((blocker) => blocker.key !== nextAction.key)
          .map((blocker) => ({ key: blocker.key, text: blocker.reason || formatLabel(blocker.key) }))}
        action={
          primary && (
            <Button size="sm" variant={primary.variant || "default"} disabled={primary.disabled} onClick={primary.onClick}>
              {primary.label}
            </Button>
          )
        }
        facts={[
          { label: "Webstore type", value: formatLabel(store.webstore_type || store.store_type || "general") },
          { label: "Webstore owner", value: ownerAssignment?.name || ownerAssignment?.email || "Not assigned" },
          { label: "Stage since", value: formatDateTime(stage?.changed_at || store.created_at) },
          { label: "Ordering closes", value: store.deadline_at ? formatDateTime(store.deadline_at) : "Not set" },
        ]}
      />
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-white p-4 text-sm" data-testid="webstore-assignee">
        <div>
          <div className="text-xs font-medium uppercase text-muted-foreground">Assigned to</div>
          <div className="text-muted-foreground">Shop tasks for this Webstore go to this person.</div>
        </div>
        <AssigneeSelect model={{ ...model, users: userItems }} />
        <div className="ml-auto text-xs text-muted-foreground">Last updated {formatDateTime(store.updated_at || store.created_at)}</div>
      </div>
    </TabsContent>
  );
}
