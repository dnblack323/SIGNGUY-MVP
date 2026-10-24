import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DecisionRoomMedia } from "@/components/decisionRoom/DecisionRoomMedia";
import { extractError } from "@/lib/api";
import { acceptWebstoreMockupComposition, previewWebstoreMockupComposition, uploadWebstoreSetupFile } from "@/lib/webstores";

const supported = new Set(["t-shirt", "tshirt", "tee", "hoodie"]);
export default function ProductMockupComposer({ model, files, onAccepted }) {
  const { id, productDraft } = model;
  const qc = useQueryClient();
  const [blank, setBlank] = useState("");
  const [artwork, setArtwork] = useState("");
  const [variant, setVariant] = useState("");
  const [placement, setPlacement] = useState({ x: 35, y: 28, width: 30, height: 35 });
  const [matched, setMatched] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [description, setDescription] = useState("");
  const [preview, setPreview] = useState(null);
  const [uploaded, setUploaded] = useState([]);
  const [error, setError] = useState("");
  const payload = { expected_revision: productDraft.revision, blank_file_id: blank, artwork_file_id: artwork,
    variant_id: variant, blank_matches_product: matched, placement: Object.fromEntries(Object.entries(placement).map(([k, v]) => [k, Number(v) / 100])) };
  const key = JSON.stringify(payload);
  const current = useRef(key); current.current = key;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => () => { if (preview?.url) URL.revokeObjectURL(preview.url); }, [preview]);
  const validPreview = preview?.key === key;
  const images = [...new Map([...files, ...uploaded].map((file) => [file.id, file])).values()].filter((file) =>
    file.safe_preview_available && file.inline_preview_allowed && !file.private_download_only && ["png", "jpg", "jpeg", "webp"].includes(file.extension));
  const variants = (productDraft.variants || []).filter((v) => v.color && v.status !== "inactive" && v.status !== "archived" && v.available !== false);
  const fail = async (err) => {
    // Axios blob responses include JSON errors as blobs as well.
    let message = extractError(err);
    if (err?.response?.data instanceof Blob) {
      try { message = extractError({ response: { data: JSON.parse(await err.response.data.text()) } }); } catch { /* Keep the ordinary transport error. */ }
    }
    if (mounted.current) setError(message);
  };
  const upload = useMutation({
    mutationFn: async (file) => {
      const form = new FormData(); form.append("file", file); form.append("category", "artwork");
      form.append("notes", "Blank product image for private staff composition");
      return (await uploadWebstoreSetupFile(id, form)).file;
    },
    onSuccess: (file) => { setUploaded((rows) => [...rows, file]); setBlank(file.id); setMatched(false); setReviewed(false); qc.invalidateQueries({ queryKey: ["webstore-setup-files", id] }); },
    onError: fail,
  });
  const prepare = useMutation({
    mutationFn: ({ fields }) => previewWebstoreMockupComposition(id, productDraft.id, fields),
    onSuccess: (result, request) => {
      if (!mounted.current || request.key !== current.current) return;
      setPreview({ key: request.key, sha256: result.sha256, url: URL.createObjectURL(result.image) });
      setReviewed(false); setError("");
    }, onError: fail,
  });
  const accept = useMutation({
    mutationFn: () => acceptWebstoreMockupComposition(id, productDraft.id, { ...payload, preview_sha256: preview.sha256, reviewed, alt_text: description.trim() }),
    onSuccess: async (result) => {
      setPreview(null); setReviewed(false); setError("");
      await onAccepted(result);
      qc.invalidateQueries({ queryKey: ["webstore-setup-files", id] });
      toast.success("Reviewed composition attached privately. Save Product, then submit when ready.");
    }, onError: fail,
  });
  if (!supported.has(String(productDraft.product_type || "").toLowerCase().replace(/[_ ]/g, "-"))) {
    return <p className="text-xs text-muted-foreground">Automatic artwork placement currently supports flat-front T-shirts and hoodies. Use the prepared mockup upload for other products or curved views.</p>;
  }
  const token = localStorage.getItem("signguy.token");
  const select = (label, value, change, options) => <Label className="grid gap-1.5">{label}
    <select aria-label={label} className="h-10 rounded border bg-background px-2 text-sm" value={value} onChange={(e) => { change(e.target.value); setReviewed(false); }}>
      <option value="">Choose an option</option>{options.map((row) => <option key={row.id} value={row.id}>{row.label || row.file_name}</option>)}
    </select></Label>;
  const busy = prepare.isPending || accept.isPending || upload.isPending;
  return <details className="rounded border p-3" data-testid="mockup-composer">
    <summary className="cursor-pointer font-medium">Compose original artwork on a product image</summary>
    <div className="mt-3 space-y-3">
      <p className="text-xs text-muted-foreground">Flat-front T-shirt / hoodie composition. Uses your original pixels, not AI redrawing. No AI credits. Use a matching blank product and color; this is a visual placement guide, not a supplier or manufacturing guarantee.</p>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <div className="grid gap-3 md:grid-cols-2">
        {select("Blank product image", blank, (v) => { setBlank(v); setMatched(false); }, images)}
        <Label className="grid gap-1.5">Upload a matching blank<Input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={(e) => { if (e.target.files?.[0]) upload.mutate(e.target.files[0]); }} /></Label>
        {select("Original artwork file", artwork, setArtwork, images)}
        {select("Product color and size", variant, (v) => { setVariant(v); setMatched(false); }, variants.map((v) => ({ ...v, label: [v.color, v.size, v.sku].filter(Boolean).join(" / ") })))}
      </div>
      <p className="text-xs text-muted-foreground">Use the customer artwork upload or select an existing file. Transparent PNG is recommended; JPEG/WebP keep their existing background. SVG/PDF/vector artwork must first be exported to PNG, or use a prepared mockup upload. Originals stay unchanged.</p>
      <Label className="flex items-center gap-2"><Checkbox checked={matched} disabled={accept.isPending} onCheckedChange={(v) => { setMatched(Boolean(v)); setReviewed(false); }} />I verified this is the correct blank product, color and flat front view</Label>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {Object.keys(placement).map((field) => <Label key={field} className="grid gap-1.5">{({ x: "Left (%)", y: "Top (%)", width: "Area width (%)", height: "Area height (%)" })[field]}
          <Input type="number" min={field === "x" || field === "y" ? 0 : 1} max="100" step="1" value={placement[field]} disabled={busy} onChange={(e) => { setPlacement((p) => ({ ...p, [field]: e.target.value })); setReviewed(false); }} /></Label>)}
      </div>
      <p className="text-xs text-muted-foreground">Save product configuration before composing. Artwork is centered and fit inside this area without stretching or cropping. Defaults are a starting area; staff must verify placement. Physical dimensions, perspective, fabric folds, color proofing and curved surfaces are unsupported.</p>
      <Button variant="outline" disabled={!blank || !artwork || !variant || !matched || busy} onClick={() => prepare.mutate({ fields: payload, key })}>Preview composition</Button>
      <div className="grid gap-3 md:grid-cols-2">
        {artwork && <div><p className="text-sm">Original artwork</p><DecisionRoomMedia src={`/api/webstores/${id}/setup-files/${artwork}/preview`} authToken={token} alt="Original customer artwork" imageClassName="h-auto max-h-[300px] w-full rounded border object-contain" /></div>}
        {validPreview && <div><p className="text-sm">Prepared mockup · private preview</p><img src={preview.url} alt="Original artwork composed on blank product" className="h-auto max-h-[400px] w-full rounded border object-contain" data-testid="composition-preview" /></div>}
      </div>
      {validPreview && <div className="space-y-2">
        <Label className="grid gap-1.5">Composed mockup description<Input value={description} maxLength={200} onChange={(e) => { setDescription(e.target.value); setReviewed(false); }} placeholder="Navy T-shirt, original school logo on front" /></Label>
        <Label className="flex items-center gap-2"><Checkbox checked={reviewed} onCheckedChange={(v) => setReviewed(Boolean(v))} />I reviewed the original artwork, product color and placement</Label>
        <Button disabled={!reviewed || !description.trim() || busy} onClick={() => accept.mutate()}>Accept mockup into draft</Button>
      </div>}
      <p className="text-xs text-muted-foreground">Acceptance saves a new private file and reviewed mockup. Save Product to keep its selection; only explicit submission makes it available to the owner. Real AI presentation generation is not connected.</p>
    </div>
  </details>;
}
