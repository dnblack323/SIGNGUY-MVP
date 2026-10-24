/**
 * F3 — Shop Schedule views following the approved Price Lab Schedule layout:
 * compact Month grid with colored type counts, Single Day lanes by type with
 * overlap-safe placement, and a right rail (mini calendar, types, summary).
 */
import { Link } from "react-router-dom";
import { CalendarDays, CheckCircle2, Clock, MapPin, Pencil, RotateCcw, Users, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  SCHEDULE_TYPES,
  TYPE_BY_KEY,
  assignedPeople,
  formatTime,
  fullDateLabel,
  layoutDayItems,
  linkedRecords,
  localDateKey,
  monthGrid,
  monthLabel,
  reservedResources,
  scheduleType,
  typeCounts,
  visibleHours,
} from "./scheduleModel";
import { itemTitle } from "./AppointmentDialog";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const HOUR_HEIGHT = 56;
const MAX_MONTH_ROWS = 3;

export function TypeDot({ type, className }) {
  return <span className={cn("inline-block size-2 shrink-0 rounded-full", TYPE_BY_KEY[type]?.dot, className)} aria-hidden="true" />;
}

/* ------------------------------------------------------------------ month --- */

export function MonthView({ dateKey, byDate, onOpenDay }) {
  const today = localDateKey();
  return (
    <section className="overflow-hidden rounded-lg border bg-card" aria-label={`${monthLabel(dateKey)} schedule`} data-testid="schedule-month">
      <div className="grid grid-cols-7 border-b bg-muted/40 text-center text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {WEEKDAYS.map((day) => <div key={day} className="py-2">{day}</div>)}
      </div>
      <div className="grid grid-cols-7">
        {monthGrid(dateKey).map((cell) => {
          const items = byDate.get(cell.key) || [];
          const counts = typeCounts(items);
          return (
            <div
              key={cell.key}
              className={cn(
                "min-h-[104px] border-b border-r p-1.5 text-left last:border-r-0 [&:nth-child(7n)]:border-r-0",
                !cell.inMonth && "bg-muted/30 text-muted-foreground",
                cell.key === dateKey && "outline outline-2 -outline-offset-2 outline-blue-600",
              )}
              data-testid={`schedule-month-day-${cell.key}`}
              data-count={items.length}
            >
              <button
                type="button"
                className={cn(
                  "mb-1 grid size-7 place-items-center rounded-full text-sm font-semibold hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  cell.key === today && "bg-blue-600 text-white hover:bg-blue-700",
                )}
                aria-label={`Open ${fullDateLabel(cell.key)}`}
                onClick={() => onOpenDay(cell.key)}
              >
                {cell.day}
              </button>
              <div className="space-y-0.5">
                {counts.slice(0, MAX_MONTH_ROWS).map((type) => (
                  <button
                    key={type.key}
                    type="button"
                    className="flex w-full items-center gap-1.5 rounded bg-muted/60 px-1.5 py-0.5 text-[11px] hover:bg-muted"
                    onClick={() => onOpenDay(cell.key, type.key)}
                    data-testid={`schedule-month-count-${cell.key}-${type.key}`}
                  >
                    <TypeDot type={type.key} />
                    <span className="truncate">{type.label}</span>
                    <span className="ml-auto font-semibold tabular-nums">{type.count}</span>
                  </button>
                ))}
                {counts.length > MAX_MONTH_ROWS && (
                  <button type="button" className="px-1.5 text-[11px] font-semibold text-primary hover:underline" onClick={() => onOpenDay(cell.key)}>
                    +{counts.slice(MAX_MONTH_ROWS).reduce((sum, type) => sum + type.count, 0)} more
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------- day --- */

function DayEventCard({ entry, onOpen }) {
  const { item } = entry;
  const type = TYPE_BY_KEY[scheduleType(item)];
  const people = assignedPeople(item);
  const records = linkedRecords(item).filter((link) => ["Order", "Work Order"].includes(link.label));
  const width = 100 / entry.columns;
  return (
    <button
      type="button"
      onClick={() => onOpen(item)}
      className={cn(
        "absolute overflow-hidden rounded-md border border-l-4 px-2 py-1 text-left text-[11px] shadow-sm hover:shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        type.card, type.text,
        item.status && !["scheduled", "rescheduled", "in_progress", "open"].includes(item.status) && "opacity-70",
      )}
      style={{
        top: (entry.top * HOUR_HEIGHT) / 60,
        height: Math.max(26, (entry.height * HOUR_HEIGHT) / 60 - 2),
        left: `calc(${entry.column * width}% + 2px)`,
        width: `calc(${width}% - 4px)`,
      }}
      data-testid={`schedule-day-item-${item.source_type}-${item.source_id}`}
    >
      <div className="font-semibold tabular-nums">{formatTime(item.start_at)}–{formatTime(item.end_at)}</div>
      <div className="truncate text-xs font-semibold text-foreground">{itemTitle(item)}</div>
      {(people.length > 0 || records.length > 0 || item.location) && (
        <div className="truncate text-[10px] text-muted-foreground">
          {[people.join(", "), records.map((r) => r.label).join(" · "), item.location].filter(Boolean).join(" · ")}
        </div>
      )}
      {item.conflicts?.length > 0 && <div className="text-[10px] font-semibold text-amber-800">Conflict</div>}
    </button>
  );
}

export function DayView({ dateKey, items, lanes, onOpen, onCreateAt }) {
  const byLane = new Map(lanes.map((lane) => [lane, []]));
  for (const item of items) byLane.get(scheduleType(item))?.push(item);
  const laidOut = new Map(lanes.map((lane) => [lane, layoutDayItems(byLane.get(lane), dateKey)]));
  const { first, last } = visibleHours([...laidOut.values()].flat());
  const hours = Array.from({ length: last - first }, (_, index) => first + index);
  const offset = first * 60;
  // Lanes widen with their simultaneous items so overlapping work stays readable.
  const laneTracks = lanes.map((lane) => {
    const columns = Math.max(0, ...laidOut.get(lane).map((entry) => entry.columns));
    return columns === 0 ? "minmax(64px, 0.5fr)" : `minmax(${100 * columns}px, ${columns}fr)`;
  });
  return (
    <section className="overflow-hidden rounded-lg border bg-card" aria-label={`${fullDateLabel(dateKey)} schedule`} data-testid="schedule-day">
      <div className="overflow-x-auto">
        <div style={{ display: "grid", gridTemplateColumns: `64px ${laneTracks.join(" ")}` }}>
          <div className="border-b border-r bg-muted/40 px-2 py-2 text-xs font-semibold">Time</div>
          {lanes.map((lane) => (
            <div key={lane} className="flex items-center gap-1.5 border-b border-r bg-muted/40 px-2 py-2 text-xs font-semibold last:border-r-0" data-testid={`schedule-lane-${lane}`}>
              <TypeDot type={lane} />{TYPE_BY_KEY[lane].label}
              <span className="ml-auto text-[10px] font-normal text-muted-foreground">{byLane.get(lane).length || ""}</span>
            </div>
          ))}
          <div className="relative border-r" style={{ height: hours.length * HOUR_HEIGHT }}>
            {hours.map((hour, index) => (
              <div key={hour} className="absolute right-2 text-[10px] text-muted-foreground" style={{ top: index * HOUR_HEIGHT + 2 }}>
                {formatTime(new Date(2000, 0, 1, hour).toISOString())}
              </div>
            ))}
          </div>
          {lanes.map((lane) => (
            <div
              key={lane}
              className="relative border-r last:border-r-0"
              style={{ height: hours.length * HOUR_HEIGHT, backgroundImage: `repeating-linear-gradient(to bottom, transparent 0 ${HOUR_HEIGHT - 1}px, hsl(var(--border)) ${HOUR_HEIGHT - 1}px ${HOUR_HEIGHT}px)` }}
              onDoubleClick={() => onCreateAt?.(lane)}
            >
              {laidOut.get(lane).map((entry) => (
                <DayEventCard key={entry.item.id} entry={{ ...entry, top: entry.top - offset }} onOpen={onOpen} />
              ))}
            </div>
          ))}
        </div>
      </div>
      {items.length === 0 && (
        <div className="flex items-center justify-center gap-2 border-t px-4 py-6 text-sm text-muted-foreground" data-testid="schedule-day-empty">
          <CalendarDays className="size-4" aria-hidden="true" /> Nothing scheduled for this day.
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------- rail --- */

export function ScheduleRail({ dateKey, byDate, enabledTypes, onToggleType, onSelectDate, onOpenDay }) {
  const today = localDateKey();
  const dayItems = (byDate.get(dateKey) || []).filter((item) => enabledTypes.includes(scheduleType(item)));
  return (
    <aside className="space-y-3" aria-label="Schedule tools" data-testid="schedule-rail">
      <section className="rounded-lg border bg-card p-3">
        <h3 className="mb-2 text-sm font-semibold">{monthLabel(dateKey)}</h3>
        <div className="grid grid-cols-7 text-center text-[10px] font-semibold text-muted-foreground">
          {WEEKDAYS.map((day) => <div key={day}>{day[0]}</div>)}
        </div>
        <div className="grid grid-cols-7 text-center text-xs">
          {monthGrid(dateKey).map((cell) => (
            <button
              key={cell.key}
              type="button"
              className={cn(
                "mx-auto my-0.5 grid size-7 place-items-center rounded-full hover:bg-muted",
                !cell.inMonth && "text-muted-foreground/60",
                cell.key === today && "font-bold text-blue-700",
                cell.key === dateKey && "bg-blue-600 font-semibold text-white hover:bg-blue-700",
              )}
              aria-label={`Select ${fullDateLabel(cell.key)}`}
              onClick={() => onSelectDate(cell.key)}
            >
              {cell.day}
            </button>
          ))}
        </div>
      </section>
      <section className="rounded-lg border bg-card p-3" data-testid="schedule-type-legend">
        <h3 className="mb-2 text-sm font-semibold">Activity types</h3>
        <div className="space-y-1.5">
          {SCHEDULE_TYPES.map((type) => (
            <label key={type.key} className="flex cursor-pointer items-center gap-2 text-xs">
              <Checkbox checked={enabledTypes.includes(type.key)} onCheckedChange={() => onToggleType(type.key)} aria-label={`Show ${type.label}`} />
              <TypeDot type={type.key} />{type.label}
            </label>
          ))}
        </div>
      </section>
      <section className="rounded-lg border bg-card p-3" data-testid="schedule-day-summary">
        <h3 className="text-sm font-semibold">Day summary</h3>
        <div className="text-xs text-muted-foreground">{fullDateLabel(dateKey)}</div>
        <div className="mt-1 text-3xl font-semibold tabular-nums text-blue-700">{dayItems.length}</div>
        <div className="text-xs text-muted-foreground">scheduled {dayItems.length === 1 ? "activity" : "activities"}</div>
        <Button type="button" variant="outline" size="sm" className="mt-2 w-full" onClick={() => onOpenDay(dateKey)}>Open Day</Button>
      </section>
    </aside>
  );
}

/* ---------------------------------------------------------------- details --- */

export function EventDetailsDialog({ item, open, onOpenChange, canManage, onEdit, onComplete, onCancel, onReopen, busy = false, children }) {
  if (!item) return null;
  const type = TYPE_BY_KEY[scheduleType(item)];
  const people = assignedPeople(item);
  const resources = reservedResources(item);
  const isAppointment = item.source_type === "calendar_event";
  const actions = item.allowed_actions || [];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="schedule-event-details">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><TypeDot type={type.key} className="size-2.5" />{itemTitle(item)}</DialogTitle>
          <DialogDescription>{type.label}{item.status ? ` · ${String(item.status).replace(/_/g, " ")}` : ""}</DialogDescription>
        </DialogHeader>
        <dl className="space-y-2 text-sm">
          <div className="flex gap-2"><Clock className="mt-0.5 size-4 text-muted-foreground" />
            <span>{fullDateLabel(localDateKey(new Date(item.start_at)))}, {formatTime(item.start_at)}–{formatTime(item.end_at)}</span></div>
          {people.length > 0 && <div className="flex gap-2"><Users className="mt-0.5 size-4 text-muted-foreground" /><span data-testid="schedule-details-people">{people.join(", ")}</span></div>}
          {resources.length > 0 && <div className="text-xs text-muted-foreground" data-testid="schedule-details-resources">Reserved: {resources.join(", ")}</div>}
          {item.location && <div className="flex gap-2"><MapPin className="mt-0.5 size-4 text-muted-foreground" /><span>{item.location}</span></div>}
          {item.conflicts?.length > 0 && <div className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-900">Saved with an approved conflict override.</div>}
        </dl>
        {linkedRecords(item).length > 0 && (
          <div className="flex flex-wrap gap-2" data-testid="schedule-details-links">
            {linkedRecords(item).map((link) => (
              <Button key={link.label} asChild variant="outline" size="sm"><Link to={link.to}>Open {link.label}</Link></Button>
            ))}
          </div>
        )}
        {canManage && (
          <div className="flex flex-wrap gap-2 border-t pt-3">
            {isAppointment && <Button size="sm" onClick={() => onEdit(item)} data-testid="schedule-details-edit"><Pencil className="mr-1 size-3.5" />Edit</Button>}
            {actions.includes("complete") && <Button size="sm" variant="outline" onClick={() => onComplete(item)} data-testid={`shop-schedule-complete-${item.source_id}`}><CheckCircle2 className="mr-1 size-3.5" />Complete</Button>}
            {actions.includes("reopen") && <Button size="sm" variant="outline" disabled={busy} onClick={() => onReopen(item)} data-testid={`shop-schedule-reopen-${item.source_id}`}><RotateCcw className="mr-1 size-3.5" />Reopen</Button>}
            {actions.includes("cancel") && <Button size="sm" variant="ghost" className="text-rose-700" onClick={() => onCancel(item)}><X className="mr-1 size-3.5" />Cancel appointment</Button>}
          </div>
        )}
        {children}
      </DialogContent>
    </Dialog>
  );
}
