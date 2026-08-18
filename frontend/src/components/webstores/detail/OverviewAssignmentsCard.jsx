import { UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function OverviewAssignmentsCard({ model }) {
  const {
    addAssignment,
    assignment,
    assignments,
    id,
    resendInvitation,
    revokeAssignment,
    setAssignment,
  } = model;

return (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    Owners and Managers
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div className="grid grid-cols-1 md:grid-cols-[120px_1fr_1fr_auto] gap-2">
                    <Select
                      value={assignment.role}
                      onValueChange={(role) =>
                        setAssignment({ ...assignment, role })
                      }
                    >
                      <SelectTrigger data-testid="webstore-assignment-role">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="owner">Owner</SelectItem>
                        <SelectItem value="manager">Manager</SelectItem>
                      </SelectContent>
                    </Select>
                    <Input
                      value={assignment.name}
                      onChange={(e) =>
                        setAssignment({ ...assignment, name: e.target.value })
                      }
                      placeholder="Name"
                      data-testid="webstore-assignment-name"
                    />
                    <Input
                      type="email"
                      value={assignment.email}
                      onChange={(e) =>
                        setAssignment({ ...assignment, email: e.target.value })
                      }
                      placeholder="Email"
                      data-testid="webstore-assignment-email"
                    />
                    <Button
                      disabled={!assignment.email || addAssignment.isPending}
                      onClick={() => addAssignment.mutate()}
                      data-testid="webstore-assignment-add"
                    >
                      <UserPlus className="size-4" />
                    </Button>
                  </div>
                  <div className="rounded border divide-y">
                    {(assignments.data || []).map((a) => (
                      <div
                        key={a.id}
                        className="p-2 flex items-center justify-between gap-2"
                      >
                        <div>
                          <div>{a.email}</div>
                          <div className="text-xs text-muted-foreground">
                            {a.role} - {a.status}
                            {a.is_primary_owner ? " - primary" : ""}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={
                              a.status === "active" ||
                              resendInvitation.isPending
                            }
                            onClick={() => resendInvitation.mutate(a.id)}
                            data-testid={`webstore-assignment-resend-${a.id}`}
                          >
                            Resend
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={
                              a.is_primary_owner ||
                              revokeAssignment.isPending ||
                              a.status === "revoked"
                            }
                            onClick={() => revokeAssignment.mutate(a.id)}
                            data-testid={`webstore-assignment-revoke-${a.id}`}
                          >
                            Revoke
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
  );
}
