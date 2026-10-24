import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DecisionRoomMedia } from "@/components/decisionRoom/DecisionRoomMedia";
import { extractError } from "@/lib/api";
import { createWebstoreArtwork, createWebstoreMockup, uploadWebstoreSetupFile } from "@/lib/webstores";
import ProductMockupComposer from "./ProductMockupComposer";

export default function ProductMockupPreparation({ model }) {
  const { id, productDraft, setupFileItems = [], artworkOptions, mockupOptions,
    addAssociation, removeAssociation, submitMockupApproval } = model;
  const qc = useQueryClient();
  const [artFile, setArtFile] = useState("");
  const [mockupFile, setMockupFile] = useState("");
  const [sourceArtwork, setSourceArtwork] = useState("");
  const [alt, setAlt] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [uploaded, setUploaded] = useState([]);
  const [error, setError] = useState("");
  const files = [...new Map([...setupFileItems, ...uploaded].map((file) => [file.id, file])).values()];
  const images = files.filter((file) => !file.ai_presentation && file.safe_preview_available && file.inline_preview_allowed && !file.private_download_only && ["png", "jpg", "jpeg", "webp", "svg"].includes(file.extension));
  const staffToken = localStorage.getItem("signguy.token");
  const fail = (err) => { const message = extractError(err); setError(message); toast.error(message); };
  const upload = useMutation({
    mutationFn: async ({ file, kind }) => {
      const form = new FormData();
      form.append("category", kind === "artwork" ? "artwork" : "mockup");
      form.append("file", file);
      return { file: (await uploadWebstoreSetupFile(id, form)).file, kind };
    },
    onSuccess: ({ file, kind }) => {
      setUploaded((rows) => [...rows, file]);
      if (kind === "artwork") setArtFile(file.id);
      else { setMockupFile(file.id); setReviewed(false); }
      setError("");
      qc.invalidateQueries({ queryKey: ["webstore-setup-files", id] });
    },
    onError: fail,
  });
  const attachArtwork = useMutation({
    mutationFn: () => createWebstoreArtwork(id, { product_id: productDraft.id, file_id: artFile,
      file_name: files.find((file) => file.id === artFile)?.file_name, purpose: "Customer artwork" }),
    onSuccess: async (artwork) => {
      addAssociation("artwork_associations", "artwork_id", artwork.id);
      setSourceArtwork(artwork.id); setError("");
      await artworkOptions.refetch();
      toast.success("Artwork attached to the draft. Save Product to keep this association.");
    }, onError: fail,
  });
  const attachMockup = useMutation({
    mutationFn: () => createWebstoreMockup(id, { product_id: productDraft.id, mockup_file_id: mockupFile,
      artwork_id: sourceArtwork || undefined, generation_source: "manual", alt_text: alt.trim(),
      purpose: "Owner product review", shop_approved: reviewed }),
    onSuccess: async (mockup) => {
      addAssociation("mockup_associations", "mockup_id", mockup.id);
      setReviewed(false); setError("");
      await mockupOptions.refetch();
      toast.success("Reviewed mockup attached to the draft. Save Product before submitting.");
    }, onError: fail,
  });
  const picker = (label, testId, value, onChange, options) => (
    <Label className="grid gap-1.5">{label}
      <select className="h-10 w-full rounded border bg-background px-2 text-sm" data-testid={testId} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Choose a file</option>
        {options.map((file) => <option key={file.id} value={file.id}>{file.file_name || file.alt_text || file.purpose || file.id}</option>)}
      </select>
    </Label>
  );
  return (
    <section className="space-y-4 rounded border p-3" data-testid="webstore-mockup-preparation">
      <div><h3 className="font-medium">Artwork and reviewed mockups</h3>
        <p className="text-xs text-muted-foreground">Artwork stays private. Review the prepared image, attach it, then Save Product. Submit the product before sending its mockup for owner approval. Replacements stay private until resubmission.</p></div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <ProductMockupComposer model={model} files={files} onAccepted={async ({ mockup, artwork }) => {
        addAssociation("artwork_associations", "artwork_id", artwork.id);
        addAssociation("mockup_associations", "mockup_id", mockup.id);
        await artworkOptions.refetch();
        await mockupOptions.refetch();
      }} />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label className="grid gap-1.5">Upload customer artwork
            <Input type="file" data-testid="webstore-artwork-upload" disabled={upload.isPending} onChange={(e) => { if (e.target.files?.[0]) upload.mutate({ file: e.target.files[0], kind: "artwork" }); }} />
          </Label>
          {picker("Or select an existing artwork file", "webstore-artwork-file", artFile, setArtFile, files.filter((file) => !file.ai_presentation))}
          <Button variant="outline" disabled={!artFile || attachArtwork.isPending || upload.isPending} onClick={() => attachArtwork.mutate()}>Attach artwork to draft</Button>
          {picker("Or associate registered artwork", "webstore-product-artwork-associations", "", (value) => { if (value) addAssociation("artwork_associations", "artwork_id", value); }, artworkOptions.data || [])}
          {(productDraft.artwork_associations || []).map((item) => <div key={item.artwork_id} className="flex items-center justify-between gap-2 text-xs">
            <span>{(artworkOptions.data || []).find((row) => row.id === item.artwork_id)?.file_name || "Associated artwork"}</span>
            <Button size="sm" variant="ghost" onClick={() => removeAssociation("artwork_associations", "artwork_id", item.artwork_id)}>Remove artwork</Button>
          </div>)}
        </div>
        <div className="space-y-2">
          <Label className="grid gap-1.5">Upload prepared mockup
            <Input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" data-testid="webstore-mockup-upload" disabled={upload.isPending} onChange={(e) => { if (e.target.files?.[0]) upload.mutate({ file: e.target.files[0], kind: "mockup" }); }} />
          </Label>
          {picker("Or select an existing mockup image", "webstore-mockup-file", mockupFile, (value) => { setMockupFile(value); setReviewed(false); }, images)}
          {mockupFile && <DecisionRoomMedia src={`/api/webstores/${id}/setup-files/${mockupFile}/preview`} authToken={staffToken} alt={alt || "Prepared mockup for staff review"} testId="webstore-prepared-mockup-image" imageClassName="h-auto max-h-[400px] w-full rounded border object-contain" />}
          {picker("Source artwork (optional)", "webstore-mockup-artwork", sourceArtwork, setSourceArtwork, artworkOptions.data || [])}
          <Label className="grid gap-1.5">Mockup description<Input value={alt} onChange={(e) => { setAlt(e.target.value); setReviewed(false); }} data-testid="webstore-mockup-description" placeholder="Navy Hat with customer logo, front view" /></Label>
          <Label className="flex items-center gap-2"><Checkbox checked={reviewed} onCheckedChange={(value) => setReviewed(Boolean(value))} data-testid="webstore-mockup-reviewed" />I reviewed this image and its product details</Label>
          <Button variant="outline" disabled={!mockupFile || !alt.trim() || !reviewed || attachMockup.isPending || upload.isPending} onClick={() => attachMockup.mutate()}>Attach reviewed mockup</Button>
        </div>
      </div>
      {picker("Associate an existing mockup", "webstore-product-mockup-associations", "", (value) => { if (value) addAssociation("mockup_associations", "mockup_id", value); }, mockupOptions.data || [])}
      {(productDraft.mockup_associations || []).map((item) => {
        const mockup = (mockupOptions.data || []).find((row) => row.id === item.mockup_id);
        return <div key={item.mockup_id} className="grid gap-2 rounded border p-2 md:grid-cols-[160px_1fr]" data-testid={`staff-mockup-${item.mockup_id}`}>
          {mockup?.mockup_file_id && <DecisionRoomMedia src={`/api/webstores/${id}/setup-files/${mockup.mockup_file_id}/preview`} authToken={staffToken} alt={mockup.alt_text || "Product mockup"} testId={`staff-mockup-image-${item.mockup_id}`} />}
          <div className="space-y-2 text-sm"><p>{mockup?.alt_text || mockup?.purpose || "Associated mockup"}</p>
            <p className="text-xs text-muted-foreground">{mockup?.shop_approved ? "Reviewed by staff" : "Staff review required"} · {String(mockup?.approval_status || "not_submitted").replace(/_/g, " ")}</p>
            <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" disabled={!mockup?.shop_approved || submitMockupApproval.isPending || mockup?.approval_status === "pending_owner_approval" || productDraft.approval_revision !== productDraft.revision || productDraft.approval_invalidated_at || !(productDraft.approval_snapshot?.mockups || []).some((row) => row.id === item.mockup_id)} onClick={() => submitMockupApproval.mutate(item.mockup_id)}>Send Mockup Approval</Button>
              <Button size="sm" variant="ghost" onClick={() => removeAssociation("mockup_associations", "mockup_id", item.mockup_id)}>Remove mockup</Button></div>
          </div>
        </div>;
      })}
      <p className="text-xs text-muted-foreground">Save Product in Review Status before submitting. Product and mockup approval do not publish the storefront.</p>
    </section>
  );
}
