import { useState } from "react";
import { MessageSquare } from "lucide-react";
import { DecisionRoomMedia } from "@/components/decisionRoom/DecisionRoomMedia";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

/**
 * EC10 Phase 10E-3 — wraps `DecisionRoomMedia` with click-to-anchor
 * comment/pin support. Coordinates are normalized (0.0-1.0) relative to
 * the rendered image box — independent of the staff Fabric.js editor's
 * `canvas_pixels_v1` contract. Only supported on `image`-type media (PDF/
 * file fallbacks render as a "View file" link with no clickable surface
 * in this phase — anchoring against a specific PDF page still works via
 * the API's `page_number` validation, just not through this click UI).
 */
export function DecisionRoomAnchorableMedia({ src, authToken, alt, testId, fileId, canAnnotate, overlays, onAddOverlay }) {
  const [mode, setMode] = useState(null); // null | "comment" | "pin"
  const [pending, setPending] = useState(null);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const myMarkers = (overlays || []).filter((o) => o.source_file_id === fileId && o.status !== "withdrawn");

  function handleClick(e) {
    if (!mode) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
    const y = Math.min(Math.max((e.clientY - rect.top) / rect.height, 0), 1);
    setPending({ x, y });
  }

  async function save() {
    if (!pending || !message.trim()) return;
    setSubmitting(true);
    try {
      await onAddOverlay({ overlay_type: mode, normalized_x: pending.x, normalized_y: pending.y, customer_message: message, source_file_id: fileId });
      setPending(null); setMessage(""); setMode(null);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-1">
      <div className="relative" onClick={handleClick} style={{ cursor: mode ? "crosshair" : "default" }} data-testid={`${testId}-anchorable`}>
        <DecisionRoomMedia src={src} authToken={authToken} alt={alt} testId={testId} />
        {myMarkers.map((o) => (
          <span
            key={o.id}
            className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center size-5 rounded-full bg-amber-500 text-white text-[10px] font-bold border-2 border-white shadow"
            style={{ left: `${o.normalized_x * 100}%`, top: `${o.normalized_y * 100}%` }}
            title={o.customer_message}
            data-testid={`${testId}-overlay-marker-${o.id}`}
          >
            {o.overlay_type === "pin" ? (o.marker_number ?? "•") : <MessageSquare className="size-3" />}
          </span>
        ))}
        {pending && (
          <span className="absolute -translate-x-1/2 -translate-y-1/2 size-3 rounded-full bg-amber-300 ring-2 ring-white" style={{ left: `${pending.x * 100}%`, top: `${pending.y * 100}%` }} />
        )}
      </div>
      {canAnnotate && (
        <div className="flex items-center gap-1 flex-wrap">
          <Button type="button" size="sm" variant={mode === "pin" ? "default" : "outline"} className="h-6 px-2 text-xs" onClick={() => { setMode(mode === "pin" ? null : "pin"); setPending(null); }} data-testid={`${testId}-pin-mode-button`}>Add pin</Button>
          <Button type="button" size="sm" variant={mode === "comment" ? "default" : "outline"} className="h-6 px-2 text-xs" onClick={() => { setMode(mode === "comment" ? null : "comment"); setPending(null); }} data-testid={`${testId}-comment-mode-button`}>Add comment</Button>
          {mode && <span className="text-xs text-slate-500">Click the image to place it</span>}
        </div>
      )}
      {pending && (
        <div className="flex gap-1" data-testid={`${testId}-overlay-composer`}>
          <Textarea rows={2} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Add your note…" className="text-xs" data-testid={`${testId}-overlay-textarea`} />
          <div className="flex flex-col gap-1">
            <Button type="button" size="sm" className="h-6 px-2 text-xs" disabled={submitting || !message.trim()} onClick={save} data-testid={`${testId}-overlay-save-button`}>Save</Button>
            <Button type="button" size="sm" variant="outline" className="h-6 px-2 text-xs" onClick={() => { setPending(null); setMessage(""); }} data-testid={`${testId}-overlay-cancel-button`}>Cancel</Button>
          </div>
        </div>
      )}
    </div>
  );
}
