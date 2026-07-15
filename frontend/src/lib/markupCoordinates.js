/**
 * EC10 Phase 10C — coordinate/resize contract helpers (§7).
 *
 * The Fabric canvas is always created at a FIXED logical resolution
 * (`canvas_width`/`canvas_height`, matching the source image/PDF-page at
 * the time a version was saved). To display that same canvas at a
 * different container width, we compute one uniform scale factor and apply
 * it via Fabric's `canvas.setZoom(scale)` — every stored object coordinate
 * is used completely unchanged; only the on-screen rendering/hit-testing is
 * scaled. This keeps annotations pixel-accurate at any screen size without
 * ever rewriting a stored coordinate.
 */
export function computeDisplayScale(canvasWidth, containerWidth) {
  if (!canvasWidth || !containerWidth || canvasWidth <= 0 || containerWidth <= 0) return 1;
  return Math.min(1, containerWidth / canvasWidth);
}

export function scaledDimensions(canvasWidth, canvasHeight, containerWidth) {
  const scale = computeDisplayScale(canvasWidth, containerWidth);
  return {
    width: Math.round(canvasWidth * scale),
    height: Math.round(canvasHeight * scale),
    scale,
  };
}
