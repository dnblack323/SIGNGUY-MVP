import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";

export default function IssueCertificationDialog({ open, onOpenChange, employeeId, employeeName, equipmentId, equipmentName, renewalOf }) {
  const qc = useQueryClient();
  const [expirationDate, setExpirationDate] = useState("");
  const [restrictions, setRestrictions] = useState("");
  useEffect(() => { if (open) { setExpirationDate(""); setRestrictions(""); } }, [open]);

  const save = useMutation({
    mutationFn: async () => {
      if (renewalOf) return (await api.post(`/certifications/${renewalOf}/renew`, { expiration_date: expirationDate || null })).data;
      return (await api.post("/certifications", {
        employee_id: employeeId, equipment_id: equipmentId,
        expiration_date: expirationDate || null, restrictions: restrictions || null,
      })).data;
    },
    onSuccess: () => {
      toast.success(renewalOf ? "Certification renewed" : "Certification issued");
      qc.invalidateQueries({ queryKey: ["certification-matrix"] });
      qc.invalidateQueries({ queryKey: ["certifications-list"] });
      onOpenChange(false);
    },
    onError: (e) => toast.error(extractError(e)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="issue-certification-dialog">
        <DialogHeader>
          <DialogTitle>{renewalOf ? "Renew Certification" : "Issue Certification"}</DialogTitle>
          <DialogDescription>{employeeName} · {equipmentName}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5"><Label>Expiration date (leave blank for never)</Label><Input type="date" value={expirationDate} onChange={(e) => setExpirationDate(e.target.value)} data-testid="certification-expiration-input" /></div>
          {!renewalOf && (
            <div className="grid gap-1.5"><Label>Restrictions (optional)</Label><Textarea rows={2} value={restrictions} onChange={(e) => setRestrictions(e.target.value)} data-testid="certification-restrictions-input" /></div>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => save.mutate()} disabled={save.isPending} data-testid="certification-issue-submit-button">{save.isPending ? "Saving…" : renewalOf ? "Renew" : "Issue"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
