import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock3,
  CreditCard,
  FileText,
  MessageSquare,
  PackagePlus,
  Receipt,
  Upload,
  UserRound,
  Wrench,
} from "lucide-react";
import api, { extractError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const CATEGORY_OPTIONS = [
  { value: "all", label: "All categories" },
  { value: "order", label: "Order" },
  { value: "order_item", label: "Items" },
  { value: "work_order", label: "Work orders" },
  { value: "proof", label: "Proofs" },
  { value: "document", label: "Documents" },
  { value: "invoice", label: "Invoices" },
  { value: "payment", label: "Payments" },
];

const ICONS = {
  order: PackagePlus,
  order_item: PackagePlus,
  work_order: Wrench,
  proof: CheckCircle2,
  document: Upload,
  invoice: Receipt,
  payment: CreditCard,
  activity: MessageSquare,
};

function endpointFor({ scope, orderId, orderItemId, workOrderId }) {
  if (scope === "work_order") return `/work-orders/${workOrderId}/timeline`;
  if (scope === "order_item") return `/orders/${orderId}/items/${orderItemId}/timeline`;
  return `/orders/${orderId}/timeline`;
}

function EventIcon({ category }) {
  const Icon = ICONS[category] || FileText;
  return (
    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
      <Icon className="size-4" />
    </div>
  );
}

function LinkList({ links }) {
  const safeLinks = (links || []).filter((link) => link?.to && link?.label);
  if (!safeLinks.length) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-2 text-xs">
      {safeLinks.map((link) => (
        <Link key={`${link.to}-${link.label}`} className="link-underline" to={link.to}>
          {link.label}
        </Link>
      ))}
    </div>
  );
}

export default function ProductionTimeline({
  scope = "order",
  orderId,
  orderItemId,
  workOrderId,
  pageSize = 25,
  testId = "production-timeline",
}) {
  const [category, setCategory] = useState("all");
  const [offset, setOffset] = useState(0);
  const endpoint = endpointFor({ scope, orderId, orderItemId, workOrderId });
  const params = useMemo(() => {
    const p = { limit: pageSize, offset, sort: "desc" };
    if (category !== "all") p.event_category = category;
    return p;
  }, [category, offset, pageSize]);

  const enabled = Boolean(endpoint && (orderId || workOrderId));
  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ["production-timeline", endpoint, params],
    queryFn: async () => (await api.get(endpoint, { params })).data,
    enabled,
    keepPreviousData: true,
  });

  const items = data?.items || [];

  return (
    <div className="rounded-xl border bg-card" data-testid={testId}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b p-3">
        <div>
          <div className="text-sm font-medium">Production timeline</div>
          <div className="text-xs text-muted-foreground">Newest events first</div>
        </div>
        <Select
          value={category}
          onValueChange={(value) => {
            setCategory(value);
            setOffset(0);
          }}
        >
          <SelectTrigger className="h-8 w-[160px]" data-testid="production-timeline-category">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CATEGORY_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="p-6 text-sm text-muted-foreground" data-testid="production-timeline-loading">Loading timeline...</div>
      ) : isError ? (
        <div className="p-6 text-sm text-destructive" data-testid="production-timeline-error">{extractError(error)}</div>
      ) : items.length === 0 ? (
        <div className="p-6 text-sm text-muted-foreground" data-testid="production-timeline-empty">No production timeline events yet.</div>
      ) : (
        <ul className="divide-y">
          {items.map((event) => (
            <li key={event.id} className="flex gap-3 p-3" data-testid="production-timeline-item">
              <EventIcon category={event.event_category} />
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                  <div className="min-w-0 truncate text-sm font-medium">{event.title}</div>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                    {String(event.event_type || "").replaceAll("_", " ")}
                  </span>
                </div>
                <div className="mt-1 text-sm text-muted-foreground">{event.internal_summary}</div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1"><UserRound className="size-3" />{event.actor_label || event.actor_type || "System"}</span>
                  <span className="inline-flex items-center gap-1"><Clock3 className="size-3" />{formatDateTime(event.occurred_at)}</span>
                  <span>{event.visibility}</span>
                </div>
                <LinkList links={event.links} />
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center justify-between border-t p-3 text-xs text-muted-foreground">
        <span>{data?.total ? `${Math.min(offset + items.length, data.total)} of ${data.total}` : "0 events"}</span>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={offset === 0 || isFetching} onClick={() => setOffset(Math.max(0, offset - pageSize))}>
            Previous
          </Button>
          <Button size="sm" variant="outline" disabled={data?.next_offset == null || isFetching} onClick={() => setOffset(data.next_offset)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
