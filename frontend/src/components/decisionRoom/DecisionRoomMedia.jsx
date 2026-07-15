import { useEffect, useState } from "react";
import axios from "axios";
import { ImageOff, FileText } from "lucide-react";

/**
 * EC10 Phase 10E-1 (media gap fix) — one shared customer-safe media
 * renderer, used for images, proof previews, and rendered markup previews
 * across both the Customer Portal and Public Token views. Always fetches
 * as a blob (with an `Authorization` header for portal mode, none for
 * public-token mode where the token already lives in the URL's `t` query
 * param) rather than using a plain `<img src>` — this lets a non-image
 * response (e.g. a PDF) safely fall back to a "View file" link instead of
 * a broken-image icon, without needing to know the mime type up front.
 */
export function DecisionRoomMedia({ src, authToken, alt, testId }) {
  const [state, setState] = useState({ status: src ? "loading" : "unavailable", blobUrl: null });

  useEffect(() => {
    if (!src) return;
    let cancelled = false;
    let createdUrl = null;
    axios
      .get(src, { headers: authToken ? { Authorization: `Bearer ${authToken}` } : {}, responseType: "blob" })
      .then((resp) => {
        if (cancelled) return;
        createdUrl = URL.createObjectURL(resp.data);
        const isImage = (resp.data.type || "").startsWith("image/");
        setState({ status: isImage ? "image" : "file", blobUrl: createdUrl });
      })
      .catch(() => { if (!cancelled) setState({ status: "unavailable", blobUrl: null }); });
    return () => { cancelled = true; if (createdUrl) URL.revokeObjectURL(createdUrl); };
  }, [src, authToken]);

  if (state.status === "loading") return <div className="h-28 w-full rounded border bg-slate-100 animate-pulse" data-testid={`${testId}-loading`} />;
  if (state.status === "unavailable") {
    return (
      <div className="h-28 w-full rounded border bg-slate-50 flex flex-col items-center justify-center text-slate-400 gap-1" data-testid={`${testId}-unavailable`}>
        <ImageOff className="size-5" /><span className="text-xs">Media unavailable</span>
      </div>
    );
  }
  if (state.status === "file") {
    return (
      <a href={state.blobUrl} target="_blank" rel="noreferrer" className="h-28 w-full rounded border bg-slate-50 flex flex-col items-center justify-center gap-1 text-sky-700 hover:underline" data-testid={testId}>
        <FileText className="size-5" /><span className="text-xs">View file</span>
      </a>
    );
  }
  return <img src={state.blobUrl} alt={alt} className="h-28 w-full rounded border object-cover" data-testid={testId} onError={() => setState({ status: "unavailable", blobUrl: null })} />;
}
