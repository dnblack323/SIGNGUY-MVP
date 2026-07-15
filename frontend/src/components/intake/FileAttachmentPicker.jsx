import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Paperclip, X, FileWarning, Loader2, PenSquare } from "lucide-react";
import { toast } from "sonner";
import MarkupWorkspace from "@/components/intake/markup/MarkupWorkspace";

const MARKUPABLE_TYPES = new Set(["image/png", "image/jpeg", "image/jpg", "image/webp", "application/pdf"]);

function FileChip({ fileId, onRemove, testIdPrefix, markupContext, existingMarkupId }) {
  const [pdfPage, setPdfPage] = useState(1);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["file-meta", fileId],
    queryFn: async () => (await api.get(`/files/${fileId}`)).data?.file,
    retry: false,
  });
  if (isLoading) {
    return <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs"><Loader2 className="size-3 animate-spin" /> Loading…</span>;
  }
  if (isError || !data) {
    // Safe missing-file state — never crashes, never exposes a raw storage path.
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 text-rose-700 ring-1 ring-rose-200 px-2.5 py-1 text-xs" data-testid={`${testIdPrefix}-missing-${fileId}`}>
        <FileWarning className="size-3" /> Missing file
        {onRemove && <button type="button" onClick={() => onRemove(fileId)}><X className="size-3 ml-1" /></button>}
      </span>
    );
  }
  const canMarkup = markupContext && MARKUPABLE_TYPES.has(data.mime_type);
  const isPdf = data.mime_type === "application/pdf";
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs" data-testid={`${testIdPrefix}-chip-${fileId}`}>
      <Paperclip className="size-3" /> {data.original_filename || "File"}
      {canMarkup && isPdf && (
        <Input type="number" min={1} value={pdfPage} onChange={(e) => setPdfPage(Math.max(1, parseInt(e.target.value || "1", 10)))} className="h-5 w-12 px-1 text-[10px]" data-testid={`${testIdPrefix}-pdf-page-${fileId}`} />
      )}
      {canMarkup && (
        <button type="button" title={existingMarkupId ? "Open markup" : "Add markup"} onClick={() => setWorkspaceOpen(true)} data-testid={`${testIdPrefix}-markup-${fileId}`}>
          <PenSquare className="size-3 ml-1 text-primary" />
        </button>
      )}
      {onRemove && <button type="button" onClick={() => onRemove(fileId)} data-testid={`${testIdPrefix}-remove-${fileId}`}><X className="size-3 ml-1" /></button>}
      {canMarkup && (
        <MarkupWorkspace
          open={workspaceOpen} onOpenChange={setWorkspaceOpen}
          sourceFileId={fileId} sourcePageNumber={isPdf ? pdfPage : undefined}
          intakeId={markupContext.intakeId} intakeItemId={markupContext.intakeItemId}
          existingMarkupId={existingMarkupId}
        />
      )}
    </span>
  );
}

/**
 * EC10 Phase 10B — reusable intake-level/item-level file attachment control.
 * Uploads through the existing `/files/upload` endpoint (object storage,
 * no inline base64) and stores only the returned file id — original files
 * remain immutable and are never touched by this component.
 */
export default function FileAttachmentPicker({ fileIds = [], onChange, testIdPrefix = "intake-files", markupContext = null, existingMarkupId = null }) {
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  async function handleFiles(e) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setBusy(true);
    const newIds = [];
    for (const f of files) {
      const form = new FormData();
      form.append("file", f);
      try {
        const { data } = await api.post("/files/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
        newIds.push(data.file.id);
      } catch (err) { toast.error(`${f.name}: ${extractError(err)}`); }
    }
    setBusy(false);
    if (fileRef.current) fileRef.current.value = "";
    if (newIds.length) onChange?.([...fileIds, ...newIds]);
  }

  function remove(id) {
    onChange?.(fileIds.filter((f) => f !== id));
  }

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid={testIdPrefix}>
      {fileIds.map((id) => (
        <FileChip key={id} fileId={id} onRemove={onChange ? remove : undefined} testIdPrefix={testIdPrefix} markupContext={markupContext} existingMarkupId={existingMarkupId} />
      ))}
      {onChange && (
        <>
          <input ref={fileRef} type="file" multiple className="hidden" onChange={handleFiles} data-testid={`${testIdPrefix}-input`} />
          <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => fileRef.current?.click()} data-testid={`${testIdPrefix}-attach-button`}>
            {busy ? <Loader2 className="size-3.5 mr-1 animate-spin" /> : <Paperclip className="size-3.5 mr-1" />}
            Attach file
          </Button>
        </>
      )}
    </div>
  );
}
