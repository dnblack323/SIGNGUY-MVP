import { Badge } from "@/components/ui/badge";

/** EC4 — Paired Invoice status badges (document + financial). */
export default function InvoicePairedStatus({ documentStatus, financialStatus }) {
  const doc = documentStatus || "draft";
  const fin = financialStatus || "unpaid";
  const docVariant = {
    draft: "outline",
    issued: "secondary",
    void: "destructive",
  }[doc] || "outline";
  const finVariant = {
    unpaid: "outline",
    partial: "default",
    paid: "default",
    refunded: "secondary",
    voided: "destructive",
  }[fin] || "outline";
  return (
    <span className="inline-flex items-center gap-1" data-testid="invoice-paired-status">
      <Badge variant={docVariant} className="capitalize" data-testid={`invoice-doc-status-${doc}`}>
        {doc}
      </Badge>
      <span className="text-muted-foreground text-xs">·</span>
      <Badge variant={finVariant} className="capitalize" data-testid={`invoice-fin-status-${fin}`}>
        {fin === "partial" ? "Partially paid" : fin}
      </Badge>
    </span>
  );
}
