import { useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  Clock,
  Factory,
  FileText,
  History,
  Mail,
  Receipt,
  ShoppingBag,
  UserRound,
  Users,
} from "lucide-react";
import StatusPill from "@/components/common/StatusPill";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { centsToDollarsString, formatDate, relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Visual identity per data family (Price Lab compact Home direction). */
export const FAMILY_STYLE = {
  active_orders: { icon: ShoppingBag, tone: "bg-sky-50 text-sky-700" },
  unpaid_invoices: { icon: Receipt, tone: "bg-emerald-50 text-emerald-700" },
  quotes_awaiting: { icon: FileText, tone: "bg-indigo-50 text-indigo-700" },
  production: { icon: Factory, tone: "bg-violet-50 text-violet-700" },
  timesheets_pending: { icon: Clock, tone: "bg-amber-50 text-amber-700" },
  active_team: { icon: Users, tone: "bg-slate-100 text-slate-700" },
  todays_schedule: { icon: CalendarDays, tone: "bg-sky-50 text-sky-700" },
  recent_customers: { icon: UserRound, tone: "bg-teal-50 text-teal-700" },
  recent_activity: { icon: History, tone: "bg-slate-100 text-slate-700" },
  recent_emails: { icon: Mail, tone: "bg-rose-50 text-rose-700" },
};

const EMPTY_TEXT = {
  active_orders: "No active orders.",
  unpaid_invoices: "No unpaid invoices.",
  quotes_awaiting: "No quotes awaiting a decision.",
  production: "No active work orders.",
  todays_schedule: "Nothing else scheduled today.",
  recent_customers: "No customers yet.",
  recent_activity: "No recent activity yet.",
  recent_emails: "No emails sent yet.",
};

function FamilyIcon({ family, small = false }) {
  const style = FAMILY_STYLE[family] || FAMILY_STYLE.recent_activity;
  const Icon = style.icon;
  return (
    <span className={cn("grid shrink-0 place-items-center rounded-md", small ? "size-7" : "size-8", style.tone)}>
      <Icon className={small ? "size-3.5" : "size-4"} aria-hidden="true" />
    </span>
  );
}

function Unavailable({ data }) {
  return (
    <div className="flex items-center gap-2 px-3 py-3 text-xs text-amber-800" data-state="unavailable">
      <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
      <span>{data?.message || "This information is unavailable right now."}</span>
    </div>
  );
}

/** COMPACT KPI — one clickable number card; no collapse or expansion. */
export function KpiWidget({ widget, data }) {
  const unavailable = data?.state === "unavailable";
  return (
    <Link
      to={widget.to}
      className="flex min-h-[68px] items-center gap-3 rounded-lg border bg-card px-3 py-2.5 transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      data-testid={`home-widget-${widget.key}`}
      data-kind="kpi"
    >
      <FamilyIcon family={widget.family} />
      <div className="min-w-0">
        <div className="line-clamp-2 text-[11px] font-medium leading-tight text-muted-foreground">{widget.title}</div>
        {unavailable ? (
          <div className="text-xs text-amber-800">Unavailable</div>
        ) : (
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-semibold leading-tight tabular-nums font-display" data-testid="home-kpi-value">{data?.value ?? 0}</span>
            {data?.amount_cents != null && (
              <span className="truncate text-xs text-muted-foreground tabular-nums">{centsToDollarsString(data.amount_cents)} due</span>
            )}
          </div>
        )}
      </div>
    </Link>
  );
}

function WidgetHeader({ widget, count, actions }) {
  return (
    <div className="flex min-h-[44px] items-center justify-between gap-2 border-b px-3 py-2">
      <div className="flex min-w-0 items-center gap-2">
        <FamilyIcon family={widget.family} small />
        <h2 className="truncate text-sm font-semibold">{widget.title}</h2>
        {count != null && <span className="rounded-full bg-muted px-1.5 text-[11px] tabular-nums text-muted-foreground">{count}</span>}
      </div>
      <div className="flex shrink-0 items-center gap-1">{actions}</div>
    </div>
  );
}

/** STANDARD SUMMARY — medium card with clickable breakdown rows. */
export function SummaryWidget({ widget, data }) {
  const rows = data?.rows || [];
  return (
    <section className="rounded-lg border bg-card" data-testid={`home-widget-${widget.key}`} data-kind="summary">
      <WidgetHeader
        widget={widget}
        actions={widget.to && <Link className="text-[11px] font-semibold text-primary hover:underline" to={widget.to}>View all</Link>}
      />
      {data?.state === "unavailable" ? (
        <Unavailable data={data} />
      ) : (
        <ul className="divide-y">
          {rows.map((row) => (
            <li key={row.label}>
              <Link to={row.to || widget.to} className="flex items-center justify-between gap-3 px-3 py-2 text-sm hover:bg-muted/40">
                <span className="truncate">{row.label}</span>
                <span className="flex shrink-0 items-baseline gap-2 tabular-nums">
                  {row.amount_cents != null && <span className="text-xs text-muted-foreground">{centsToDollarsString(row.amount_cents)}</span>}
                  <strong className="font-semibold">{row.value}</strong>
                </span>
              </Link>
            </li>
          ))}
          <li className="flex items-center justify-between px-3 py-2 text-xs text-muted-foreground">
            <span>Total</span>
            <span className="tabular-nums">
              {data?.amount_cents != null && <span className="mr-2">{centsToDollarsString(data.amount_cents)}</span>}
              {data?.total ?? 0}
            </span>
          </li>
        </ul>
      )}
    </section>
  );
}

function ListRow({ item }) {
  const secondary = item.due_date
    ? `Due ${formatDate(item.due_date) || "not set"}`
    : item.start_at
      ? new Date(item.start_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
      : item.subtitle || (item.when ? relativeTime(item.when) : null);
  return (
    <Link to={item.to} className="flex items-center justify-between gap-3 px-3 py-2 hover:bg-muted/40">
      <div className="min-w-0">
        <div className="truncate text-sm">
          {item.ref && <span className="mono mr-2 text-xs text-muted-foreground">{item.ref}</span>}
          {item.title}
        </div>
        {secondary && <div className="truncate text-xs text-muted-foreground">{secondary}</div>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {item.amount_cents != null && <span className="text-sm tabular-nums">{centsToDollarsString(item.amount_cents)}</span>}
        {item.status_kind && <StatusPill kind={item.status_kind} value={item.status} />}
        <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
      </div>
    </Link>
  );
}

const COLLAPSED_ROWS = 5;

/** LIST — scrollable, collapsible (saved) and expandable records with direct links. */
export function ListWidget({ widget, data, collapsed, onToggleCollapsed }) {
  const [expanded, setExpanded] = useState(false);
  const items = data?.items || [];
  const shown = expanded ? items : items.slice(0, COLLAPSED_ROWS);
  const bodyId = `home-widget-body-${widget.key}`;
  return (
    <section className="rounded-lg border bg-card" data-testid={`home-widget-${widget.key}`} data-kind="list" data-collapsed={collapsed ? "true" : "false"}>
      <WidgetHeader
        widget={widget}
        count={data?.state === "ready" ? data?.total : null}
        actions={(
          <>
            {widget.to && <Link className="text-[11px] font-semibold text-primary hover:underline" to={widget.to}>View all</Link>}
            <button
              type="button"
              className="grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-muted"
              aria-expanded={!collapsed}
              aria-controls={bodyId}
              aria-label={collapsed ? `Expand ${widget.title}` : `Collapse ${widget.title}`}
              onClick={onToggleCollapsed}
            >
              <ChevronDown className={cn("size-4 transition-transform", collapsed && "-rotate-90")} aria-hidden="true" />
            </button>
          </>
        )}
      />
      {!collapsed && (
        <div id={bodyId}>
          {data?.state === "unavailable" ? (
            <Unavailable data={data} />
          ) : items.length === 0 ? (
            <div className="px-3 py-4 text-xs text-muted-foreground" data-state="empty">{EMPTY_TEXT[widget.family] || "Nothing to show."}</div>
          ) : widget.family === "recent_activity" ? (
            <div className="max-h-80 overflow-y-auto p-3">
              <AuditTimeline events={shown} />
            </div>
          ) : (
            <ul className="max-h-80 divide-y overflow-y-auto">
              {shown.map((item) => (
                <li key={item.id || item.to}><ListRow item={item} /></li>
              ))}
            </ul>
          )}
          {items.length > COLLAPSED_ROWS && (
            <button
              type="button"
              className="w-full border-t px-3 py-1.5 text-left text-[11px] font-semibold text-primary hover:bg-muted/40"
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded ? "Show fewer" : `Show all ${items.length}`}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
