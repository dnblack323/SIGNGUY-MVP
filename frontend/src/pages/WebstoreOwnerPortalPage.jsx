import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  CheckCircle2,
  FileText,
  FileUp,
  MessageSquare,
  Save,
  Send,
} from "lucide-react";
import portalApi, { portalExtractError } from "@/portal/portalApi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import FormRenderer from "@/components/forms/FormRenderer";
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
  const [changeRequest, setChangeRequest] = useState({
    category: "general",
    comment: "",
  });
  function load() {
    Promise.all([
      portalApi.get(`/portal/webstores/${webstoreId}`),
      portalApi.get(`/portal/webstores/${webstoreId}/questionnaire`),
      portalApi.get(`/portal/webstores/${webstoreId}/setup-progress`),
      portalApi.get(`/portal/webstores/${webstoreId}/setup-files`),
    ])
      .then(([detail, q, setup, fileList]) => {
        setData(detail.data);
        setQuestionnaire(q.data);
        setProgress(setup.data);
        setFiles(fileList.data.items || []);
        setAnswers(
          q.data.submission?.answers ||
            q.data.submission?.submitted_snapshot?.answers ||
            {},
        );
      })
      .catch((e) => setErr(portalExtractError(e)));
  }
  useEffect(load, [webstoreId]);
  async function saveDraft() {
    try {
      await portalApi.post(
        `/portal/webstores/${webstoreId}/questionnaire/draft`,
        { answers, known_products: [] },
      );
      toast.success("Draft saved");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }
  async function submitQuestionnaire() {
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/questionnaire`, {
        answers,
        known_products: [],
      });
      toast.success("Questionnaire submitted");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }
  async function uploadSetupFile() {
    if (!setupFile) return;
    try {
      const formData = new FormData();
      formData.append("category", fileCategory);
      formData.append("file", setupFile);
      await portalApi.post(
        `/portal/webstores/${webstoreId}/setup-files`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      toast.success("File uploaded");
      setSetupFile(null);
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }
  async function approve() {
    try {
      await portalApi.post(
        `/portal/webstores/${webstoreId}/launch-packets/${data.launch_packet.id}/approve`,
      );
      toast.success("Launch approved");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }
  async function requestChanges() {
    if (!changeRequest.comment.trim()) return;
    try {
      await portalApi.post(
        `/portal/webstores/${webstoreId}/launch-packets/${data.launch_packet.id}/request-changes`,
        changeRequest,
      );
      toast.success("Change request sent");
      setChangeRequest({ category: "general", comment: "" });
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }
  async function acceptTerms() {
    try {
      await portalApi.post(`/portal/webstores/${webstoreId}/terms/accept`, {
        terms_version: data.current_terms_version,
      });
      toast.success("Terms accepted");
      load();
    } catch (e) {
      toast.error(portalExtractError(e));
    }
  }
  if (err)
    return (
      <div className="text-sm text-rose-700" data-testid="webstore-owner-error">
        {err}
      </div>
    );
  if (!data)
    return <div className="text-sm text-muted-foreground">Loading...</div>;
  return (
    <div className="space-y-4" data-testid="webstore-owner-portal-page">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{data.webstore.name}</h1>
          <p className="text-sm text-muted-foreground">
            Review setup, products, and launch approval.
          </p>
        </div>
        <Badge variant="outline" className="capitalize">
          {String(data.webstore.status).replace(/_/g, " ")}
        </Badge>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Setup Progress</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Badge variant="outline" data-testid="portal-webstore-setup-state">
            {progress?.setup_state ||
              data.webstore.setup_state ||
              "not_started"}
          </Badge>
          {(progress?.steps || []).map((step) => (
            <div key={step.key} className="flex justify-between gap-3">
              <span>{step.label}</span>
              <span className="text-muted-foreground">{step.status}</span>
            </div>
          ))}
          {progress?.type_requirements && (
            <div
              className="rounded border p-3"
              data-testid="portal-webstore-type-requirements"
            >
              <div className="font-medium">
                {progress.type_requirements.label} requirements
              </div>
              <div className="mt-2 grid gap-2">
                {(progress.type_requirements.items || []).map((item) => (
                  <div key={item.key} className="flex justify-between gap-3">
                    <span>{item.owner_wording || item.label}</span>
                    <span className="text-muted-foreground">{item.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Commerce</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
          <div>
            <div className="text-xs text-muted-foreground">Orders</div>
            <div className="font-semibold">
              {data.commerce_summary?.order_count || 0}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Sales</div>
            <div className="font-semibold">
              {centsToDollarsString(
                data.commerce_summary?.gross_sales_cents || 0,
              )}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Refunds</div>
            <div className="font-semibold">
              {centsToDollarsString(
                data.commerce_summary?.refund_total_cents || 0,
              )}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Payouts</div>
            <div className="font-semibold">
              {centsToDollarsString(
                data.commerce_summary?.payout_total_cents || 0,
              )}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Disputes</div>
            <div className="font-semibold">
              {centsToDollarsString(
                data.commerce_summary?.dispute_hold_cents || 0,
              )}
            </div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Questionnaire</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <FormRenderer
            sections={(questionnaire?.templates || []).flatMap(
              (template) => template.sections || [],
            )}
            answers={answers}
            onAnswersChange={setAnswers}
            lockedAnswerIds={(questionnaire?.templates || []).flatMap(
              (template) => template.locked_answer_ids || [],
            )}
          />
          <div className="flex gap-2">
            <Button variant="outline" onClick={saveDraft}>
              <Save className="size-4 mr-2" />
              Save draft
            </Button>
            <Button onClick={submitQuestionnaire}>
              <Send className="size-4 mr-2" />
              Submit
            </Button>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Setup Files</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-2">
            <input
              className="border rounded px-3 py-2 text-sm"
              value={fileCategory}
              onChange={(e) => setFileCategory(e.target.value)}
              data-testid="portal-webstore-file-category"
            />
            <input
              className="border rounded px-3 py-2 text-sm"
              type="file"
              onChange={(e) => setSetupFile(e.target.files?.[0] || null)}
              data-testid="portal-webstore-file"
            />
            <Button disabled={!setupFile} onClick={uploadSetupFile}>
              <FileUp className="size-4 mr-2" />
              Upload
            </Button>
          </div>
          <div className="rounded border divide-y">
            {files.map((file) => (
              <div
                key={file.id}
                className="p-3 flex items-center justify-between gap-3 text-sm"
              >
                <span>{file.file_name}</span>
                <span className="text-muted-foreground">
                  {file.category} -{" "}
                  {file.private_download_only
                    ? "download only"
                    : "preview safe"}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Branding</CardTitle>
        </CardHeader>
        <CardContent>
          <WebstoreBrandingEditor
            webstoreId={webstoreId}
            portal
            products={data.products || []}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Products</CardTitle>
        </CardHeader>
        <CardContent className="rounded border divide-y p-0">
          {(data.products || []).map((p) => (
            <div
              key={p.id}
              className="p-3 grid gap-3 md:grid-cols-[96px_1fr_auto] text-sm"
            >
              <div className="aspect-square overflow-hidden rounded border bg-slate-50">
                {p.images?.[0]?.url ? (
                  <img
                    src={p.images[0].url}
                    alt={p.images[0].alt_text || p.name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                    No image
                  </div>
                )}
              </div>
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-muted-foreground">
                  {p.description || p.product_type}
                </div>
                {(p.mockups || []).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {p.mockups.map((mockup) => (
                      <Badge key={mockup.id} variant="outline">
                        {mockup.alt_text || mockup.purpose || "Mockup"}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              <span className="font-medium">
                {centsToDollarsString(p.selling_price_cents)}
              </span>
            </div>
          ))}
          {(data.products || []).length === 0 && (
            <div className="p-3 text-sm text-muted-foreground">
              No product previews are available yet.
            </div>
          )}
        </CardContent>
      </Card>
      {data.launch_packet && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Launch Packet</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-medium">
                  Version {data.launch_packet.version || 1}
                </div>
                <div className="text-xs text-muted-foreground capitalize">
                  {String(data.launch_packet.status).replace(/_/g, " ")}
                </div>
              </div>
              <Badge variant="outline">
                {data.launch_packet.delivery_status || "portal"}
              </Badge>
            </div>
            <div>
              {data.launch_packet.promotion_copy ||
                "Launch packet is ready for approval."}
            </div>
            <div
              className="rounded border p-3 space-y-2"
              data-testid="portal-launch-packet-products"
            >
              {(data.launch_packet.snapshot?.products || []).map((product) => (
                <div
                  key={product.packet_ref || product.id}
                  className="flex items-center justify-between gap-3"
                >
                  <div>
                    <div className="font-medium">{product.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {product.description || product.product_type}
                    </div>
                  </div>
                  <span className="font-medium">
                    {centsToDollarsString(product.selling_price_cents)}
                  </span>
                </div>
              ))}
            </div>
            <div
              className="rounded border p-3 text-xs"
              data-testid="portal-readiness-summary"
            >
              {(data.readiness_summary || []).map((gate) => (
                <div className="flex justify-between gap-3" key={gate.key}>
                  <span>{gate.owner_wording}</span>
                  <Badge
                    variant={gate.state === "ready" ? "secondary" : "outline"}
                  >
                    {gate.state}
                  </Badge>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={data.launch_packet.status === "owner_approved"}
                onClick={approve}
                data-testid="portal-approve-packet"
              >
                <CheckCircle2 className="size-4 mr-2" />
                Approve packet v{data.launch_packet.version || 1}
              </Button>
            </div>
            <div
              className="rounded border p-3 space-y-2"
              data-testid="portal-change-request"
            >
              <div className="font-medium">Request changes</div>
              <select
                className="border rounded px-2 py-1 text-sm"
                value={changeRequest.category}
                onChange={(e) =>
                  setChangeRequest({
                    ...changeRequest,
                    category: e.target.value,
                  })
                }
              >
                {[
                  "branding",
                  "product",
                  "price",
                  "description",
                  "artwork",
                  "mockup",
                  "variant",
                  "personalization",
                  "fulfillment",
                  "availability",
                  "policy",
                  "general",
                ].map((category) => (
                  <option key={category} value={category}>
                    {category.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <Textarea
                rows={3}
                value={changeRequest.comment}
                onChange={(e) =>
                  setChangeRequest({
                    ...changeRequest,
                    comment: e.target.value,
                  })
                }
                placeholder="Tell the shop what needs to change."
                data-testid="portal-change-request-comment"
              />
              <Button
                variant="outline"
                disabled={!changeRequest.comment.trim()}
                onClick={requestChanges}
                data-testid="portal-request-changes"
              >
                <MessageSquare className="size-4 mr-2" />
                Send change request
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Terms</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div
            className="rounded border p-3"
            data-testid="portal-terms-version"
          >
            <div className="font-medium">
              Version {data.current_terms_version || "webstore_terms_2026_07"}
            </div>
            <div className="text-xs text-muted-foreground">
              {data.terms_acceptance
                ? `Accepted ${new Date(data.terms_acceptance.accepted_at).toLocaleString()}`
                : "Terms acceptance is separate from packet approval."}
            </div>
          </div>
          <Button
            disabled={!!data.terms_acceptance}
            onClick={acceptTerms}
            data-testid="portal-accept-terms"
          >
            <FileText className="size-4 mr-2" />
            Accept current Terms
          </Button>
        </CardContent>
      </Card>
      {(data.change_requests || []).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Change Request History</CardTitle>
          </CardHeader>
          <CardContent
            className="rounded border divide-y p-0"
            data-testid="portal-change-request-history"
          >
            {data.change_requests.map((request) => (
              <div key={request.id} className="p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium capitalize">
                    {request.category}
                  </span>
                  <Badge variant="outline">{request.status}</Badge>
                </div>
                <div className="text-xs text-muted-foreground">
                  {request.owner_comment}
                </div>
                {(request.owner_visible_history || [])
                  .slice(-2)
                  .map((item, index) => (
                    <div
                      key={`${request.id}-${index}`}
                      className="mt-1 text-xs"
                    >
                      {item.message}
                    </div>
                  ))}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
