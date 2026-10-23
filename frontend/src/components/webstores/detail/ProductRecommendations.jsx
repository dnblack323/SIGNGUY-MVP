import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/auth/AuthContext";
import { getWebstoreProductRecommendations } from "@/lib/webstores";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ProductRecommendations({ model }) {
  const { id, templates, templateId, setTemplateId } = model;
  const { hasPerm } = useAuth();
  const recommendations = useQuery({
    queryKey: ["webstore-product-recommendations", id],
    queryFn: () => getWebstoreProductRecommendations(id),
    // Reuse the existing template loader/installer; this read does not seed a
    // second library and cannot race the first installation of tenant starters.
    enabled: Boolean(id && templates.isSuccess),
  });
  const data = recommendations.data;
  return (
    <Card data-testid="webstore-product-recommendations">
      <CardHeader>
        <CardTitle className="text-base">Recommended starting products</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">Matches use the questionnaire and the store types recorded on your templates. Choose a template, then create and review its draft below.</p>
        {recommendations.isPending && <p role="status">Loading product matches…</p>}
        {recommendations.isError && (
          <div role="alert">
            <p>Product matches could not load. Your existing templates and products are still available below.</p>
            <Button type="button" variant="outline" size="sm" onClick={() => recommendations.refetch()}>
              Retry recommendations
            </Button>
          </div>
        )}
        {data && <>
          {!data.submission_id && <p className="text-muted-foreground">A completed questionnaire is needed to match the owner's product requests. Any matches below use template store-type settings only.</p>}
          {data.extra_suggestions_declined && <p>Showing requested products only; the owner declined extra suggestions.</p>}
          {(data.context || []).length > 0 && (
            <dl className="rounded border bg-slate-50 p-3 space-y-2" aria-label="Product selection context">
              {data.context.map((item) => (
                <div key={item.key}>
                  <dt className="font-medium">{item.label}</dt>
                  <dd className="break-words text-muted-foreground">{item.value}</dd>
                </div>
              ))}
            </dl>
          )}
          {(data.items || []).length === 0 && <p>No active templates match these requests or the store's template settings. Choose an existing template below or start a custom product.</p>}
          {(data.items || []).map((item) => (
            <div key={item.template_id} className="rounded border p-3 space-y-2">
              <div className="font-medium">{item.name}</div>
              <ul className="list-disc pl-5 text-muted-foreground">
                {item.reasons.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!hasPerm("webstore:write") || item.already_selected}
                onClick={() => setTemplateId(item.template_id)}
                data-testid={`webstore-recommend-template-${item.template_id}`}
              >
                {item.already_selected ? "Already in selected products" : templateId === item.template_id ? "Template selected" : "Select template"}
              </Button>
            </div>
          ))}
          {(data.unmatched_requests || []).length > 0 && <p className="rounded border border-amber-200 bg-amber-50 p-3">No matching active template for: {data.unmatched_requests.join(", ")}. Review these requests with the shop before choosing an alternative.</p>}
          <p className="text-muted-foreground">{data.review_note}</p>
        </>}
      </CardContent>
    </Card>
  );
}
