import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import MarkupCanvas from "@/components/intake/markup/MarkupCanvas";
import MarkupToolbar from "@/components/intake/markup/MarkupToolbar";
import MarkupVersionHistory from "@/components/intake/markup/MarkupVersionHistory";

const MAX_DIMENSION = 1400;

async function loadImageBlobUrl(fileId) {
  const { data } = await api.get(`/files/${fileId}/download`, { responseType: "blob" });
  return URL.createObjectURL(data);
}

async function naturalImageSize(blobUrl) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => resolve({ width: MAX_DIMENSION, height: Math.round(MAX_DIMENSION * 0.75) });
    img.src = blobUrl;
  });
}

function capDimensions(w, h) {
  if (w <= MAX_DIMENSION) return { width: w, height: h };
  const scale = MAX_DIMENSION / w;
  return { width: MAX_DIMENSION, height: Math.round(h * scale) };
}

async function renderPdfPage(fileId, pageNumber) {
  const pdfjsLib = await import("pdfjs-dist");
  pdfjsLib.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
  const { data } = await api.get(`/files/${fileId}/download`, { responseType: "arraybuffer" });
  const pdf = await pdfjsLib.getDocument({ data }).promise;
  const page = await pdf.getPage(pageNumber);
  const base = page.getViewport({ scale: 1 });
  const scale = Math.min(2, MAX_DIMENSION / base.width);
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
  return { dataUrl: canvas.toDataURL("image/png"), width: Math.round(viewport.width), height: Math.round(viewport.height) };
}

/**
 * EC10 Phase 10C §11 — the reusable internal markup workspace. Opens a
 * markup (creating one on first use if none exists yet for this source),
 * resolves the background (image blob or a client-rendered PDF page — see
 * §9: the original PDF is never modified, only one page is rendered into
 * this workspace), and saves new versions via the backend contract.
 */
export default function MarkupWorkspace({
  open, onOpenChange, sourceFileId, sourcePageNumber, intakeId, intakeItemId, existingMarkupId,
}) {
  const qc = useQueryClient();
  const canvasApiRef = useRef(null);
  const containerRef = useRef(null);
  const [markupId, setMarkupId] = useState(existingMarkupId || null);
  const [tool, setTool] = useState("select");
  const [background, setBackground] = useState(null); // { src, width, height }
  const [initialObjects, setInitialObjects] = useState([]);
  const [ready, setReady] = useState(false);
  const [changeSummary, setChangeSummary] = useState("");
  const [containerWidth, setContainerWidth] = useState(900);

  const { data: markup } = useQuery({
    queryKey: ["markup", markupId], enabled: !!markupId,
    queryFn: async () => (await api.get(`/markup/${markupId}`)).data,
  });

  const createMut = useMutation({
    mutationFn: async () => (await api.post("/markup", {
      source_file_id: sourceFileId, source_page_number: sourcePageNumber,
      intake_id: intakeId, intake_item_id: intakeItemId,
    })).data,
    onError: (err) => toast.error(extractError(err)),
  });

  const saveMut = useMutation({
    mutationFn: async () => {
      const structured = canvasApiRef.current.getStructuredJson();
      const previewDataUrl = canvasApiRef.current.toPreviewDataUrl();
      const previewBlob = await (await fetch(previewDataUrl)).blob();
      const form = new FormData();
      form.append("file", previewBlob, "markup-preview.png");
      let previewFileId = null;
      try {
        const up = await api.post("/files/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
        previewFileId = up.data.file.id;
      } catch {
        // Preview generation failure must not corrupt the structured version — proceed without one.
        toast.warning("Preview image could not be uploaded — version saved without a preview.");
      }
      return (await api.post(`/markup/${markupId}/versions`, {
        structured_markup_json: structured,
        canvas_width: background.width, canvas_height: background.height,
        source_display_width: background.width, source_display_height: background.height,
        rendered_preview_file_id: previewFileId, change_summary: changeSummary || undefined,
      })).data;
    },
    onSuccess: async (data) => {
      toast.success(`Saved version ${data.version.version_number}`);
      if (intakeItemId || intakeId) {
        try {
          await api.post(`/markup/${markupId}/attach`, { intake_id: intakeId, intake_item_id: intakeItemId || undefined });
        } catch { /* attachment is best-effort here; can be retried from the detail page */ }
      }
      qc.invalidateQueries({ queryKey: ["markup", markupId] });
      qc.invalidateQueries({ queryKey: ["markup-versions", markupId] });
      qc.invalidateQueries({ queryKey: ["intake"] });
      setChangeSummary("");
    },
    onError: (err) => toast.error(extractError(err)),
  });

  useEffect(() => {
    if (!open) { setReady(false); setMarkupId(existingMarkupId || null); return; }
    (async () => {
      let id = existingMarkupId;
      if (!id) {
        const created = await createMut.mutateAsync();
        id = created.id;
      }
      setMarkupId(id);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!markup) return;
    (async () => {
      if (markup.current_version_id) {
        const version = (await api.get(`/markup/${markupId}/versions/${markup.current_version_id}`)).data;
        setInitialObjects(version.structured_markup_json?.objects || []);
        if (markup.source_file_type === "pdf") {
          const rendered = await renderPdfPage(markup.source_file_id, markup.source_page_number);
          setBackground({ src: rendered.dataUrl, width: version.canvas_width, height: version.canvas_height });
        } else {
          const blobUrl = await loadImageBlobUrl(markup.source_file_id);
          setBackground({ src: blobUrl, width: version.canvas_width, height: version.canvas_height });
        }
      } else if (markup.source_file_type === "pdf") {
        const rendered = await renderPdfPage(markup.source_file_id, markup.source_page_number);
        setBackground({ src: rendered.dataUrl, width: rendered.width, height: rendered.height });
      } else {
        const blobUrl = await loadImageBlobUrl(markup.source_file_id);
        const natural = await naturalImageSize(blobUrl);
        const capped = capDimensions(natural.width, natural.height);
        setBackground({ src: blobUrl, ...capped });
      }
      setReady(true);
    })().catch((err) => toast.error(extractError(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markup?.id, markup?.current_version_id]);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width));
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  const api_ = canvasApiRef.current;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[1100px]" data-testid="markup-workspace-dialog">
        <DialogHeader><DialogTitle>Visual markup{markup ? ` — v${markup.current_version_number || 0}` : ""}</DialogTitle></DialogHeader>
        {!ready || !background ? (
          <div className="p-8 text-sm text-muted-foreground text-center" data-testid="markup-workspace-loading">Loading source asset…</div>
        ) : (
          <div className="grid gap-3">
            <MarkupToolbar
              activeTool={tool}
              onToolChange={(t) => { setTool(t); canvasApiRef.current?.setTool(t); }}
              onDelete={() => canvasApiRef.current?.deleteSelected()}
              onUndo={() => canvasApiRef.current?.undo()}
              onRedo={() => canvasApiRef.current?.redo()}
              onZoomIn={() => canvasApiRef.current?.zoomIn()}
              onZoomOut={() => canvasApiRef.current?.zoomOut()}
              onFit={() => canvasApiRef.current?.fitToScreen()}
              onClear={() => canvasApiRef.current?.clearUnsaved()}
              onSave={() => saveMut.mutate()}
              saving={saveMut.isPending}
            />
            <div ref={containerRef} className="rounded-lg border bg-muted/30 overflow-auto flex justify-center p-2">
              <MarkupCanvas
                ref={canvasApiRef}
                canvasWidth={background.width} canvasHeight={background.height}
                backgroundSrc={background.src} initialObjects={initialObjects}
                containerWidth={Math.max(200, containerWidth - 16)}
              />
            </div>
            <Input
              placeholder="Change summary (optional)" value={changeSummary}
              onChange={(e) => setChangeSummary(e.target.value)} data-testid="markup-change-summary-input"
            />
            <MarkupVersionHistory markupId={markupId} currentVersionId={markup?.current_version_id} onView={() => {}} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
