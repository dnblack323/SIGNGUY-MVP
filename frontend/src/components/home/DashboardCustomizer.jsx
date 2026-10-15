import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const KIND_LABEL = { kpi: "Number", summary: "Summary", list: "List" };

/**
 * Turn a widget on and switch off any other presentation of the same metric
 * (the backend enforces the same rule when saving).
 */
export function toggleWidget(draft, widgets, key) {
  const hidden = new Set(draft.hidden);
  if (!hidden.has(key)) {
    hidden.add(key);
    return { draft: { ...draft, hidden: [...hidden] }, replaced: null };
  }
  hidden.delete(key);
  const family = widgets.find((w) => w.key === key)?.family;
  const replaced = widgets.filter((w) => w.key !== key && w.family === family && !hidden.has(w.key));
  replaced.forEach((w) => hidden.add(w.key));
  return { draft: { ...draft, hidden: [...hidden] }, replaced: replaced[0] || null };
}

export const ZONES = [
  { kind: "kpi", label: "Number cards", hint: "Top row" },
  { kind: "summary", label: "Summaries", hint: "Main area" },
  { kind: "list", label: "Lists", hint: "Right column" },
];

/**
 * Move a widget up or down within its own zone (same kind). Home renders each
 * kind in a fixed zone, so cross-zone moves would have no visible effect.
 */
export function moveWidget(draft, widgets, key, direction) {
  const kindOf = new Map(widgets.map((w) => [w.key, w.kind]));
  const order = [...draft.order];
  const zone = order.filter((k) => kindOf.get(k) === kindOf.get(key));
  const pos = zone.indexOf(key);
  const neighbor = zone[pos + direction];
  if (pos < 0 || !neighbor) return draft;
  const a = order.indexOf(key);
  const b = order.indexOf(neighbor);
  [order[a], order[b]] = [order[b], order[a]];
  return { ...draft, order };
}

export default function DashboardCustomizer({ open, layout, widgets, restricted, saving, onSave, onRestore, onOpenChange }) {
  const [draft, setDraft] = useState(layout);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    if (open) {
      setDraft(layout);
      setNotice(null);
    }
  }, [open, layout]);

  const available = new Map(widgets.map((w) => [w.key, w]));
  const orderedKeys = (draft?.order || []).filter((key) => available.has(key));
  const hidden = new Set(draft?.hidden || []);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] max-w-lg overflow-hidden p-0" data-testid="home-customizer">
        <DialogHeader className="border-b px-5 py-4">
          <DialogTitle>Customize Home</DialogTitle>
          <DialogDescription>Choose widgets and set their order within each area. Each metric shows in one place only.</DialogDescription>
        </DialogHeader>
        <div className="max-h-[55dvh] overflow-y-auto px-5 py-3">
          {notice && (
            <div className="mb-2 rounded-md bg-sky-50 px-3 py-2 text-xs text-sky-900" role="status" data-testid="home-customizer-notice">{notice}</div>
          )}
          {ZONES.map((zone) => {
            const zoneKeys = orderedKeys.filter((key) => available.get(key).kind === zone.kind);
            if (zoneKeys.length === 0) return null;
            return (
              <section key={zone.kind} className="mb-3" data-testid={`home-customizer-zone-${zone.kind}`}>
                <div className="mb-1 flex items-baseline justify-between text-xs">
                  <span className="font-semibold">{zone.label}</span>
                  <span className="text-muted-foreground">{zone.hint}</span>
                </div>
                <ol className="divide-y rounded-md border">
                  {zoneKeys.map((key, index) => {
                    const widget = available.get(key);
                    return (
                      <li key={key} className="flex items-center gap-3 px-3 py-2" data-testid={`home-customizer-row-${key}`}>
                        <Checkbox
                          id={`home-widget-toggle-${key}`}
                          checked={!hidden.has(key)}
                          aria-label={`Show ${widget.title} (${KIND_LABEL[widget.kind]})`}
                          onCheckedChange={() => {
                            const result = toggleWidget(draft, widgets, key);
                            setDraft(result.draft);
                            setNotice(result.replaced ? `${widget.title} (${KIND_LABEL[widget.kind]}) replaces ${result.replaced.title} (${KIND_LABEL[result.replaced.kind]}).` : null);
                          }}
                        />
                        <label htmlFor={`home-widget-toggle-${key}`} className="min-w-0 flex-1 text-sm">
                          <span className="font-medium">{widget.title}</span>
                          <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">{KIND_LABEL[widget.kind]}</span>
                        </label>
                        <Button type="button" variant="ghost" size="icon" className="size-7" aria-label={`Move ${widget.title} (${KIND_LABEL[widget.kind]}) up`} disabled={index === 0}
                          onClick={() => setDraft(moveWidget(draft, widgets, key, -1))}>
                          <ArrowUp className="size-3.5" />
                        </Button>
                        <Button type="button" variant="ghost" size="icon" className="size-7" aria-label={`Move ${widget.title} (${KIND_LABEL[widget.kind]}) down`} disabled={index === zoneKeys.length - 1}
                          onClick={() => setDraft(moveWidget(draft, widgets, key, 1))}>
                          <ArrowDown className="size-3.5" />
                        </Button>
                      </li>
                    );
                  })}
                </ol>
              </section>
            );
          })}
          {restricted.length > 0 && (
            <div className="mt-3" data-testid="home-customizer-restricted">
              <div className="mb-1 text-xs font-medium text-muted-foreground">Not available with your access</div>
              <ul className="divide-y rounded-md border bg-muted/30">
                {restricted.map((widget) => (
                  <li key={widget.key} className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                    <Lock className="size-3.5" aria-hidden="true" />
                    <span className="flex-1">{widget.title}</span>
                    <span>Needs {widget.required_permission}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <DialogFooter className="flex-row items-center justify-between gap-2 border-t px-5 py-3 sm:justify-between">
          <Button type="button" variant="outline" size="sm" onClick={onRestore} disabled={saving}>Restore default layout</Button>
          <div className="flex gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="button" size="sm" onClick={() => onSave(draft)} disabled={saving}>Save Home</Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
