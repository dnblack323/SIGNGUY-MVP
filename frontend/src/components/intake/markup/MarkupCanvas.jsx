import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { Canvas, FabricImage, Line, PencilBrush, util } from "fabric";
import { buildArrow, buildEllipse, buildNumberedCallout, buildPin, buildRect, buildTextbox } from "@/lib/markupObjects";
import { computeDisplayScale } from "@/lib/markupCoordinates";

/**
 * EC10 Phase 10C — the annotation surface itself. Fixed logical resolution
 * (`canvasWidth`/`canvasHeight`) is set once per source and never changes
 * across versions of the same workspace — see `lib/markupCoordinates.js`
 * for how display-time scaling is applied without touching stored
 * coordinates. `structured_markup_json` is built from `canvas.getObjects()`
 * ONLY — the background image is never part of that array, so it can never
 * leak into the persisted payload.
 */
const MarkupCanvas = forwardRef(function MarkupCanvas(
  { canvasWidth, canvasHeight, backgroundSrc, initialObjects, containerWidth, testId = "markup-canvas" },
  ref,
) {
  const canvasElRef = useRef(null);
  const fabricRef = useRef(null);
  const historyRef = useRef([]);
  const historyIndexRef = useRef(-1);
  const replayingRef = useRef(false);
  const originalObjectsRef = useRef(initialObjects || []);
  const calloutCountRef = useRef(0);
  const detachDragRef = useRef(null);

  function pushHistory() {
    if (replayingRef.current) return;
    const snapshot = fabricRef.current.getObjects().map((o) => o.toObject());
    historyRef.current = [...historyRef.current.slice(0, historyIndexRef.current + 1), snapshot];
    historyIndexRef.current = historyRef.current.length - 1;
  }

  async function replay(objects) {
    replayingRef.current = true;
    const canvas = fabricRef.current;
    canvas.getObjects().forEach((o) => canvas.remove(o));
    if (objects?.length) {
      const enlivened = await util.enlivenObjects(objects);
      enlivened.forEach((o) => canvas.add(o));
    }
    canvas.requestRenderAll();
    replayingRef.current = false;
  }

  useEffect(() => {
    const canvas = new Canvas(canvasElRef.current, { width: canvasWidth, height: canvasHeight, preserveObjectStacking: true });
    fabricRef.current = canvas;
    canvas.on("object:added", pushHistory);
    canvas.on("object:modified", pushHistory);
    canvas.on("object:removed", pushHistory);

    if (backgroundSrc) {
      FabricImage.fromURL(backgroundSrc, { crossOrigin: "anonymous" }).then((img) => {
        img.scaleToWidth(canvasWidth);
        canvas.backgroundImage = img;
        canvas.requestRenderAll();
      }).catch(() => {});
    }

    (async () => {
      if (originalObjectsRef.current?.length) await replay(originalObjectsRef.current);
      pushHistory();
    })();

    return () => canvas.dispose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const canvas = fabricRef.current;
    if (!canvas) return;
    const scale = computeDisplayScale(canvasWidth, containerWidth);
    canvas.setZoom(scale);
    canvas.setDimensions({ width: Math.round(canvasWidth * scale), height: Math.round(canvasHeight * scale) });
  }, [containerWidth, canvasWidth, canvasHeight]);

  function attachDragTool(tool) {
    const canvas = fabricRef.current;
    detachDragRef.current?.();
    let start = null;
    let temp = null;
    const onDown = (e) => { start = canvas.getScenePoint(e.e); };
    const onMove = (e) => {
      if (!start) return;
      const p = canvas.getScenePoint(e.e);
      if (temp) canvas.remove(temp);
      if (tool === "arrow") temp = buildArrow(start.x, start.y, p.x, p.y);
      else if (tool === "line") temp = new Line([start.x, start.y, p.x, p.y], { stroke: "#ef4444", strokeWidth: 3 });
      else if (tool === "rect") temp = buildRect(Math.min(start.x, p.x), Math.min(start.y, p.y), p.x - start.x, p.y - start.y);
      else if (tool === "ellipse") temp = buildEllipse(Math.min(start.x, p.x), Math.min(start.y, p.y), p.x - start.x, p.y - start.y);
      else if (tool === "highlight") temp = buildRect(Math.min(start.x, p.x), Math.min(start.y, p.y), p.x - start.x, p.y - start.y, true);
      if (temp) { temp.selectable = false; canvas.add(temp); canvas.requestRenderAll(); }
    };
    const onUp = () => { start = null; if (temp) temp.selectable = true; temp = null; };
    canvas.on("mouse:down", onDown);
    canvas.on("mouse:move", onMove);
    canvas.on("mouse:up", onUp);
    detachDragRef.current = () => {
      canvas.off("mouse:down", onDown);
      canvas.off("mouse:move", onMove);
      canvas.off("mouse:up", onUp);
      detachDragRef.current = null;
    };
  }

  useImperativeHandle(ref, () => ({
    setTool(tool) {
      const canvas = fabricRef.current;
      detachDragRef.current?.();
      canvas.__markupClickHandler && canvas.off("mouse:down", canvas.__markupClickHandler);
      canvas.isDrawingMode = tool === "draw";
      if (tool === "draw") {
        canvas.freeDrawingBrush = new PencilBrush(canvas);
        canvas.freeDrawingBrush.color = "#ef4444";
        canvas.freeDrawingBrush.width = 3;
      }
      canvas.selection = tool === "select";
      canvas.forEachObject((o) => (o.selectable = tool === "select"));

      if (["line", "arrow", "rect", "ellipse", "highlight"].includes(tool)) {
        attachDragTool(tool);
      } else if (["text", "pin", "callout"].includes(tool)) {
        const handler = (e) => {
          const p = canvas.getScenePoint(e.e);
          if (tool === "text") canvas.add(buildTextbox(p.x, p.y));
          else if (tool === "pin") canvas.add(buildPin(p.x, p.y));
          else if (tool === "callout") { calloutCountRef.current += 1; canvas.add(buildNumberedCallout(p.x, p.y, calloutCountRef.current)); }
        };
        canvas.__markupClickHandler = handler;
        canvas.on("mouse:down", handler);
      }
    },
    deleteSelected() {
      const canvas = fabricRef.current;
      canvas.getActiveObjects().forEach((o) => canvas.remove(o));
      canvas.discardActiveObject();
      canvas.requestRenderAll();
    },
    undo() {
      if (historyIndexRef.current <= 0) return;
      historyIndexRef.current -= 1;
      replay(historyRef.current[historyIndexRef.current]);
    },
    redo() {
      if (historyIndexRef.current >= historyRef.current.length - 1) return;
      historyIndexRef.current += 1;
      replay(historyRef.current[historyIndexRef.current]);
    },
    clearUnsaved() {
      replay(originalObjectsRef.current);
      historyRef.current = [originalObjectsRef.current];
      historyIndexRef.current = 0;
    },
    zoomIn() { const c = fabricRef.current; c.setZoom(Math.min(3, c.getZoom() * 1.2)); },
    zoomOut() { const c = fabricRef.current; c.setZoom(Math.max(0.2, c.getZoom() / 1.2)); },
    fitToScreen() {
      const c = fabricRef.current;
      const scale = computeDisplayScale(canvasWidth, containerWidth);
      c.setZoom(scale);
      c.setDimensions({ width: Math.round(canvasWidth * scale), height: Math.round(canvasHeight * scale) });
    },
    getStructuredJson() {
      return { objects: fabricRef.current.getObjects().map((o) => o.toObject()) };
    },
    toPreviewDataUrl() {
      return fabricRef.current.toDataURL({ format: "png", multiplier: 1 });
    },
  }));

  return <canvas ref={canvasElRef} data-testid={testId} />;
});

export default MarkupCanvas;
