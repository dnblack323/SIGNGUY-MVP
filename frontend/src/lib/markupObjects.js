import { Line, Triangle, Rect, Ellipse, Circle, Textbox, Group } from "fabric";

/**
 * EC10 Phase 10C §6 — tool object builders. Fabric.js has no built-in
 * "arrow", "pin", or "numbered callout" primitive, so each is composed from
 * allowlisted primitives (line/triangle/circle/textbox grouped) — every
 * resulting object still serializes to one of the backend's
 * `_ALLOWED_OBJECT_TYPES` (`group`, `line`, `triangle`, `rect`, `circle`,
 * `ellipse`, `textbox`). No image/pattern/data-URI is ever attached.
 */
const STROKE = "#ef4444";
const FILL = "rgba(239,68,68,0.25)";

export function buildArrow(x1, y1, x2, y2) {
  const line = new Line([x1, y1, x2, y2], { stroke: STROKE, strokeWidth: 3, selectable: false, evented: false });
  const angle = (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI + 90;
  const head = new Triangle({
    left: x2, top: y2, width: 14, height: 16, fill: STROKE, angle, originX: "center", originY: "center",
    selectable: false, evented: false,
  });
  return new Group([line, head], { left: Math.min(x1, x2), top: Math.min(y1, y2) });
}

export function buildPin(x, y) {
  const circle = new Circle({ radius: 12, fill: STROKE, left: 0, top: 0, originX: "center", originY: "center" });
  return new Group([circle], { left: x, top: y, originX: "center", originY: "center" });
}

export function buildNumberedCallout(x, y, number) {
  const circle = new Circle({ radius: 14, fill: STROKE, left: 0, top: 0, originX: "center", originY: "center" });
  const label = new Textbox(String(number), {
    left: -14, top: -9, width: 28, fontSize: 16, fill: "#fff", textAlign: "center", fontWeight: "bold",
  });
  return new Group([circle, label], { left: x, top: y, originX: "center", originY: "center" });
}

export function buildRect(x, y, w, h, highlight = false) {
  return new Rect({
    left: x, top: y, width: Math.abs(w), height: Math.abs(h),
    stroke: STROKE, strokeWidth: highlight ? 0 : 2,
    fill: highlight ? FILL : "transparent",
  });
}

export function buildEllipse(x, y, w, h) {
  return new Ellipse({
    left: x, top: y, rx: Math.abs(w) / 2, ry: Math.abs(h) / 2, stroke: STROKE, strokeWidth: 2, fill: "transparent",
  });
}

export function buildTextbox(x, y) {
  return new Textbox("Note", { left: x, top: y, fontSize: 18, fill: STROKE, width: 160 });
}
