import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export default function RevokeCertificationDialog({ open, onOpenChange, onConfirm, pending }) {
  const [reason, setReason] = useState("");
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="revoke-certification-dialog">
        <DialogHeader>
          <DialogTitle>Revoke Certification</DialogTitle>
          <DialogDescription>The record is kept as permanent history — this cannot be undone.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-1.5">
          <Label>Reason*</Label>
          <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus data-testid="revoke-certification-reason-input" />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="destructive" disabled={pending || !reason.trim()} onClick={() => onConfirm(reason.trim())} data-testid="revoke-certification-submit-button">Revoke</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
