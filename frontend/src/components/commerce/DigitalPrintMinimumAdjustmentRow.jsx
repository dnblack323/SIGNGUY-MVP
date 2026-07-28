import { centsToDollarsString, isValidIntegerCents } from "@/lib/format";

export function digitalPrintMinimumAdjustmentCents(totals) {
  const direct = totals?.digital_print_order_minimum_adjustment_cents;
  const nested = totals?.digital_print_minimum?.order_minimum_adjustment_cents;
  const cents = direct ?? nested;
  return isValidIntegerCents(cents) && cents > 0 ? cents : null;
}

export default function DigitalPrintMinimumAdjustmentRow({
  totals,
  className = "",
  labelClassName = "text-xs text-muted-foreground text-right",
  valueClassName = "text-right tabular-nums",
  testId = "digital-print-order-minimum-adjustment",
}) {
  const cents = digitalPrintMinimumAdjustmentCents(totals);
  if (cents == null) return null;
  return (
    <>
      <div className={`${labelClassName} ${className}`.trim()}>Digital Print order minimum adjustment</div>
      <div className={`${valueClassName} ${className}`.trim()} data-testid={testId}>
        {centsToDollarsString(cents)}
      </div>
    </>
  );
}
