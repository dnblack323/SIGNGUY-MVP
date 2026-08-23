import { PackagePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { centsToDollarsString } from "@/lib/format";

export default function OverviewProductsSummaryCard({ model }) {
  const { addProduct, detail, id, setTemplateId, templateId, templates } = model;

return (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Products</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex gap-2">
                    <Select value={templateId} onValueChange={setTemplateId}>
                      <SelectTrigger data-testid="webstore-template-select">
                        <SelectValue placeholder="Choose template" />
                      </SelectTrigger>
                      <SelectContent>
                        {(templates.data || []).map((t) => (
                          <SelectItem value={t.id} key={t.id}>
                            {t.template_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      disabled={!templateId || addProduct.isPending}
                      onClick={() => addProduct.mutate()}
                    >
                      <PackagePlus className="size-4" />
                    </Button>
                  </div>
                  <div className="rounded border divide-y">
                    {(detail.data?.products || []).map((p) => (
                      <div
                        key={p.id}
                        className="p-3 text-sm flex items-center justify-between gap-3"
                      >
                        <div>
                          <div className="font-medium">{p.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {p.status} · {p.public ? "public" : "private"}
                          </div>
                        </div>
                        <span className="font-medium">
                          {centsToDollarsString(p.selling_price_cents)}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
  );
}
