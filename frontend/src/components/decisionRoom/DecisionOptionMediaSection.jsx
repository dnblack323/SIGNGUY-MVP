import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import FileAttachmentPicker from "@/components/intake/FileAttachmentPicker";
import { Link2, Unlink } from "lucide-react";

function RefIdField({ label, value, onAttach, onDetach, testIdPrefix }) {
  const [val, setVal] = useState("");
  return (
    <div className="grid gap-1.5">
      <Label className="text-xs">{label}</Label>
      {value ? (
        <div className="flex items-center gap-2">
          <span className="text-xs rounded bg-muted px-2 py-1 truncate flex-1" data-testid={`${testIdPrefix}-value`}>{value}</span>
          <Button type="button" size="icon" variant="ghost" onClick={onDetach} data-testid={`${testIdPrefix}-detach-button`}><Unlink className="size-4" /></Button>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <Input value={val} onChange={(e) => setVal(e.target.value)} placeholder={`${label} id`} className="text-xs" data-testid={`${testIdPrefix}-input`} />
          <Button type="button" size="icon" variant="outline" disabled={!val.trim()} onClick={() => { onAttach(val.trim()); setVal(""); }} data-testid={`${testIdPrefix}-attach-button`}>
            <Link2 className="size-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

/**
 * EC10 Phase 10D — media/proof/markup reference section of a Decision
 * Option editor. Every reference is an ID pointer into an existing,
 * immutable record (File / Proof / VisualMarkup) — nothing is ever copied
 * or re-uploaded here. Proof/VisualMarkup are pasted-in ids (no dedicated
 * browser yet — a known, documented gap for a future phase).
 */
export default function DecisionOptionMediaSection({ option, onFilesChange, onAttachField, onDetachField, testIdPrefix }) {
  return (
    <div className="grid gap-3 rounded-lg border border-dashed p-3" data-testid={`${testIdPrefix}-media`}>
      <div className="grid gap-1.5">
        <Label className="text-xs">Customer-visible files</Label>
        <FileAttachmentPicker fileIds={option.file_ids || []} onChange={onFilesChange} testIdPrefix={`${testIdPrefix}-files`} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <RefIdField
          label="Proof" value={option.proof_id} testIdPrefix={`${testIdPrefix}-proof`}
          onAttach={(id) => onAttachField("proof_id", id)} onDetach={() => onDetachField(["proof_id"])}
        />
        <RefIdField
          label="Visual Markup" value={option.visual_markup_id} testIdPrefix={`${testIdPrefix}-markup`}
          onAttach={(id) => onAttachField("visual_markup_id", id)} onDetach={() => onDetachField(["visual_markup_id"])}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <RefIdField
          label="Rendered preview file" value={option.rendered_preview_file_id} testIdPrefix={`${testIdPrefix}-rendered-preview`}
          onAttach={(id) => onAttachField("rendered_preview_file_id", id)} onDetach={() => onDetachField(["rendered_preview_file_id"])}
        />
        <RefIdField
          label="Thumbnail file" value={option.thumbnail_file_id} testIdPrefix={`${testIdPrefix}-thumbnail`}
          onAttach={(id) => onAttachField("thumbnail_file_id", id)} onDetach={() => onDetachField(["thumbnail_file_id"])}
        />
      </div>
    </div>
  );
}
