import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Printer } from "lucide-react";
import { centsToDollarsString } from "@/lib/format";

export default function PrintSummaryDialog({ workOrderId, open, onOpenChange }) {
  const printRef = useRef(null);
  const { data, isLoading } = useQuery({
    queryKey: ["work-order-summary", workOrderId],
    queryFn: async () => (await api.get(`/work-orders/${workOrderId}/summary`)).data,
    enabled: open && !!workOrderId,
  });

  useEffect(() => {
    if (!open) return;
    const style = document.createElement("style");
    style.textContent = `
      @media print {
        body * { visibility: hidden !important; }
        [data-print-region="work-order-summary"], [data-print-region="work-order-summary"] * { visibility: visible !important; }
        [data-print-region="work-order-summary"] { position: fixed !important; inset: 0 !important; padding: 24px !important; background: #fff !important; overflow: visible !important; z-index: 999999 !important; box-shadow: none !important; border: 0 !important; }
        .no-print { display: none !important; }
      }
    `;
    document.head.appendChild(style);
    return () => { style.remove(); };
  }, [open]);

  const summary = data || {};
  const items = summary.items || [];
  const includePricing = items.some((it) => it.unit_price_cents !== undefined && it.unit_price_cents !== null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl" data-testid="print-summary-dialog">
        <DialogHeader className="no-print">
          <DialogTitle>Printable Work Order Summary</DialogTitle>
          <DialogDescription>Tenant-safe production summary. Pricing appears only for users with invoice access.</DialogDescription>
        </DialogHeader>
        {isLoading || !summary.work_order_number ? (
          <div className="text-sm text-muted-foreground">Loading summary…</div>
        ) : (
          <div ref={printRef} data-print-region="work-order-summary" className="bg-white text-black p-4 rounded">
            <div className="flex items-start justify-between border-b pb-3 mb-3">
              <div>
                <div className="text-xs uppercase tracking-wide text-muted-foreground">Work Order</div>
                <div className="text-2xl font-semibold mono">
                  W-{summary.work_order_number}{summary.version > 1 ? ` v${summary.version}` : ""}
                </div>
                {!summary.current_version && (
                  <div className="text-xs text-rose-700 font-medium mt-0.5" data-testid="print-summary-superseded-flag">SUPERSEDED</div>
                )}
              </div>
              <div className="text-right text-sm">
                <div><span className="text-muted-foreground">Status: </span><span className="capitalize font-medium">{String(summary.status || "").replace(/_/g, " ")}</span></div>
                <div><span className="text-muted-foreground">Priority: </span><span className="capitalize font-medium">{summary.priority || "normal"}</span></div>
                {summary.due_date && <div><span className="text-muted-foreground">Due: </span><span className="font-medium">{summary.due_date}</span></div>}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm mb-3">
              <div>
                <div className="text-xs uppercase text-muted-foreground mb-1">Customer</div>
                <div className="font-medium">{summary.customer?.name || "—"}</div>
              </div>
              <div>
                <div className="text-xs uppercase text-muted-foreground mb-1">Order</div>
                <div className="font-medium mono">O-{summary.order_number || "—"}</div>
              </div>
            </div>

            {summary.production_notes && (
              <div className="mb-3">
                <div className="text-xs uppercase text-muted-foreground mb-1">Instructions</div>
                <div className="text-sm whitespace-pre-wrap border rounded p-2 bg-muted/20">{summary.production_notes}</div>
              </div>
            )}

            <div className="mb-2 text-xs uppercase text-muted-foreground">Items</div>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-1">Description</th>
                  <th className="text-right py-1 w-16">Qty</th>
                  {includePricing && <th className="text-right py-1 w-24">Unit</th>}
                  {includePricing && <th className="text-right py-1 w-24">Line</th>}
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr><td colSpan={includePricing ? 4 : 2} className="py-3 text-muted-foreground italic">No production items</td></tr>
                ) : items.map((it, i) => (
                  <tr key={i} className="border-b last:border-0" data-testid={`print-summary-item-${i}`}>
                    <td className="py-1 align-top">
                      <div className="font-medium">{it.description}</div>
                      {(it.width_inches || it.height_inches) && (
                        <div className="text-xs text-muted-foreground">
                          {it.width_inches ?? "?"} × {it.height_inches ?? "?"} {it.unit_of_measure || "in"}
                        </div>
                      )}
                      {it.material_key && <div className="text-xs text-muted-foreground">Material: {it.material_key}</div>}
                      {it.notes && <div className="text-xs text-muted-foreground">{it.notes}</div>}
                    </td>
                    <td className="py-1 text-right tabular-nums align-top">{it.quantity}</td>
                    {includePricing && <td className="py-1 text-right tabular-nums align-top">{centsToDollarsString(it.unit_price_cents || 0)}</td>}
                    {includePricing && <td className="py-1 text-right tabular-nums align-top">{centsToDollarsString((it.quantity || 1) * (it.unit_price_cents || 0))}</td>}
                  </tr>
                ))}
              </tbody>
            </table>

            {!includePricing && (
              <div className="mt-3 text-[10px] text-muted-foreground italic" data-testid="print-summary-no-pricing">
                Pricing hidden — requires invoice access.
              </div>
            )}

            <div className="mt-6 grid grid-cols-2 gap-6 text-xs">
              <div><div className="border-t pt-1">Prepared by</div></div>
              <div><div className="border-t pt-1">Signature / Date</div></div>
            </div>
          </div>
        )}
        <DialogFooter className="no-print">
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="print-summary-close">Close</Button>
          <Button onClick={() => window.print()} disabled={isLoading || !summary.work_order_number} data-testid="print-summary-print">
            <Printer className="size-4 mr-1" />Print
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
