import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle2, FileUp, Save, Send } from "lucide-react";
import portalApi, { portalExtractError } from "@/portal/portalApi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import WebstoreBrandingEditor from "@/components/webstores/WebstoreBranding";
import { centsToDollarsString } from "@/lib/format";
import { toast } from "sonner";

export default function WebstoreOwnerPortalPage() {
  const { webstoreId } = useParams();
  const [data, setData] = useState(null);
  const [questionnaire, setQuestionnaire] = useState(null);
  const [progress, setProgress] = useState(null);
  const [files, setFiles] = useState([]);
  const [err, setErr] = useState(null);
  const [answers, setAnswers] = useState({});
  const [fileCategory, setFileCategory] = useState("logo");
  const [setupFile, setSetupFile] = useState(null);
  function load() {
    Promise.all([
      portalApi.get(`/portal/webstores/${webstoreId}`),
      portalApi.get(`/portal/webstores/${webstoreId}/questionnaire`),
      portalApi.get(`/portal/webstores/${webstoreId}/setup-progress`),
      portalApi.get(`/portal/webstores/${webstoreId}/setup-files`),
    ]).then(([detail, q, setup, fileList]) => {
      setData(detail.data);
      setQuestionnaire(q.data);
      setProgress(setup.data);
      setFiles(fileList.data.items || []);
      setAnswers(q.data.submission?.answers || q.data.submission?.submitted_snapshot?.answers || {});
    }).catch((e) => setErr(portalExtractError(e)));
  }
  useEffect(load, [webstoreId]);
  async function saveDraft() {
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/questionnaire/draft`, { answers, known_products: [] });
      toast.success("Draft saved");
      load();
    } catch (e) { toast.error(portalExtractError(e)); }
  }
  async function submitQuestionnaire() {
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/questionnaire`, { answers, known_products: [] });
      toast.success("Questionnaire submitted");
      load();
    } catch (e) { toast.error(portalExtractError(e)); }
  }
  async function uploadSetupFile() {
    if (!setupFile) return;
    try {
      const formData = new FormData();
      formData.append("category", fileCategory);
      formData.append("file", setupFile);
      await portalApi.post(`/portal/webstores/${webstoreId}/setup-files`, formData, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("File uploaded");
      setSetupFile(null);
      load();
    } catch (e) { toast.error(portalExtractError(e)); }
  }
  async function approve() {
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/launch-packets/${data.launch_packet.id}/approve`);
      toast.success("Launch approved");
      load();
    } catch (e) { toast.error(portalExtractError(e)); }
  }
  if (err) return <div className="text-sm text-rose-700" data-testid="webstore-owner-error">{err}</div>;
  if (!data) return <div className="text-sm text-muted-foreground">Loading...</div>;
  return (
    <div className="space-y-4" data-testid="webstore-owner-portal-page">
      <div className="flex items-center justify-between gap-3">
        <div><h1 className="text-2xl font-semibold">{data.webstore.name}</h1><p className="text-sm text-muted-foreground">Review setup, products, and launch approval.</p></div>
        <Badge variant="outline" className="capitalize">{String(data.webstore.status).replace(/_/g, " ")}</Badge>
      </div>
      <Card>
        <CardHeader><CardTitle className="text-base">Setup Progress</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Badge variant="outline" data-testid="portal-webstore-setup-state">{progress?.setup_state || data.webstore.setup_state || "not_started"}</Badge>
          {(progress?.steps || []).map((step) => (
            <div key={step.key} className="flex justify-between gap-3">
              <span>{step.label}</span>
              <span className="text-muted-foreground">{step.status}</span>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">Questionnaire</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {(questionnaire?.templates || []).flatMap((template) => template.sections || []).map((section) => (
            <div key={section.id} className="rounded border p-3 space-y-2">
              <div className="font-medium">{section.title}</div>
              {(section.questions || []).map((question) => (
                <label key={question.key} className="grid gap-1.5 text-sm">
                  <span>{question.label}</span>
                  <Textarea
                    rows={question.type === "textarea" ? 3 : 1}
                    value={answers[question.key] || ""}
                    onChange={(e) => setAnswers({ ...answers, [question.key]: e.target.value })}
                    data-testid={`portal-webstore-answer-${question.key}`}
                  />
                </label>
              ))}
            </div>
          ))}
          <div className="flex gap-2">
            <Button variant="outline" onClick={saveDraft}><Save className="size-4 mr-2" />Save draft</Button>
            <Button onClick={submitQuestionnaire}><Send className="size-4 mr-2" />Submit</Button>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">Setup Files</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-2">
            <input className="border rounded px-3 py-2 text-sm" value={fileCategory} onChange={(e) => setFileCategory(e.target.value)} data-testid="portal-webstore-file-category" />
            <input className="border rounded px-3 py-2 text-sm" type="file" onChange={(e) => setSetupFile(e.target.files?.[0] || null)} data-testid="portal-webstore-file" />
            <Button disabled={!setupFile} onClick={uploadSetupFile}><FileUp className="size-4 mr-2" />Upload</Button>
          </div>
          <div className="rounded border divide-y">
            {files.map((file) => (
              <div key={file.id} className="p-3 flex items-center justify-between gap-3 text-sm">
                <span>{file.file_name}</span>
                <span className="text-muted-foreground">{file.category} - {file.private_download_only ? "download only" : "preview safe"}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">Branding</CardTitle></CardHeader>
        <CardContent>
          <WebstoreBrandingEditor webstoreId={webstoreId} portal products={data.products || []} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">Products</CardTitle></CardHeader>
        <CardContent className="rounded border divide-y p-0">
          {(data.products || []).map((p) => (
            <div key={p.id} className="p-3 grid gap-3 md:grid-cols-[96px_1fr_auto] text-sm">
              <div className="aspect-square overflow-hidden rounded border bg-slate-50">
                {p.images?.[0]?.url ? (
                  <img src={p.images[0].url} alt={p.images[0].alt_text || p.name} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-muted-foreground">No image</div>
                )}
              </div>
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-muted-foreground">{p.description || p.product_type}</div>
                {(p.mockups || []).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {p.mockups.map((mockup) => <Badge key={mockup.id} variant="outline">{mockup.alt_text || mockup.purpose || "Mockup"}</Badge>)}
                  </div>
                )}
              </div>
              <span className="font-medium">{centsToDollarsString(p.selling_price_cents)}</span>
            </div>
          ))}
          {(data.products || []).length === 0 && <div className="p-3 text-sm text-muted-foreground">No product previews are available yet.</div>}
        </CardContent>
      </Card>
      {data.launch_packet && (
        <Card>
          <CardHeader><CardTitle className="text-base">Launch Packet</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>{data.launch_packet.promotion_copy || "Launch packet is ready for approval."}</div>
            <Button disabled={data.launch_packet.status === "owner_approved"} onClick={approve}><CheckCircle2 className="size-4 mr-2" />Approve launch</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
