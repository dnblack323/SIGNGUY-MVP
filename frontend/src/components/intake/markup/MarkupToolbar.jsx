import { Button } from "@/components/ui/button";
import {
  MousePointer2, Pencil, Minus, ArrowUpRight, Square, Circle as CircleIcon,
  Type, ListOrdered, MapPin, Highlighter, Trash2, Undo2, Redo2,
  ZoomIn, ZoomOut, Maximize, RotateCcw, Save,
} from "lucide-react";

const TOOLS = [
  { id: "select", icon: MousePointer2, label: "Select / move" },
  { id: "draw", icon: Pencil, label: "Freehand" },
  { id: "line", icon: Minus, label: "Line" },
  { id: "arrow", icon: ArrowUpRight, label: "Arrow" },
  { id: "rect", icon: Square, label: "Rectangle" },
  { id: "ellipse", icon: CircleIcon, label: "Ellipse" },
  { id: "text", icon: Type, label: "Text label" },
  { id: "callout", icon: ListOrdered, label: "Numbered callout" },
  { id: "pin", icon: MapPin, label: "Pin" },
  { id: "highlight", icon: Highlighter, label: "Highlight box" },
];

/**
 * EC10 Phase 10C §6 — practical internal markup toolset. No filters,
 * cropping, masking, or design tools — annotation only.
 */
export default function MarkupToolbar({ activeTool, onToolChange, onDelete, onUndo, onRedo, onZoomIn, onZoomOut, onFit, onClear, onSave, saving }) {
  return (
    <div className="flex flex-wrap items-center gap-1 rounded-lg border bg-card p-1.5" data-testid="markup-toolbar">
      {TOOLS.map(({ id, icon: Icon, label }) => (
        <Button
          key={id} type="button" size="icon" variant={activeTool === id ? "default" : "ghost"}
          title={label} onClick={() => onToolChange(id)} data-testid={`markup-tool-${id}`}
        >
          <Icon className="size-4" />
        </Button>
      ))}
      <div className="w-px h-6 bg-border mx-1" />
      <Button type="button" size="icon" variant="ghost" title="Delete selected" onClick={onDelete} data-testid="markup-tool-delete"><Trash2 className="size-4" /></Button>
      <Button type="button" size="icon" variant="ghost" title="Undo" onClick={onUndo} data-testid="markup-tool-undo"><Undo2 className="size-4" /></Button>
      <Button type="button" size="icon" variant="ghost" title="Redo" onClick={onRedo} data-testid="markup-tool-redo"><Redo2 className="size-4" /></Button>
      <div className="w-px h-6 bg-border mx-1" />
      <Button type="button" size="icon" variant="ghost" title="Zoom in" onClick={onZoomIn} data-testid="markup-tool-zoom-in"><ZoomIn className="size-4" /></Button>
      <Button type="button" size="icon" variant="ghost" title="Zoom out" onClick={onZoomOut} data-testid="markup-tool-zoom-out"><ZoomOut className="size-4" /></Button>
      <Button type="button" size="icon" variant="ghost" title="Fit to screen" onClick={onFit} data-testid="markup-tool-fit"><Maximize className="size-4" /></Button>
      <Button type="button" size="icon" variant="ghost" title="Clear unsaved changes" onClick={onClear} data-testid="markup-tool-clear"><RotateCcw className="size-4" /></Button>
      <div className="flex-1" />
      <Button type="button" size="sm" disabled={saving} onClick={onSave} data-testid="markup-save-version-button">
        <Save className="size-4 mr-1" />{saving ? "Saving…" : "Save new version"}
      </Button>
    </div>
  );
}
