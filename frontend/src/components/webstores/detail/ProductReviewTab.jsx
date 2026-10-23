import {
  Archive,
  CheckCircle2,
  Clock,
  RotateCcw,
  Save,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TabsContent } from "@/components/ui/tabs";

export default function ProductReviewTab({ model }) {
  const {
    addBundleItem,
    archiveProduct,
    detail,
    getProductSetupItems,
    productDraft,
    removeBundleItem,
    restoreProduct,
    saveProduct,
    selectedProduct,
    setProductField,
  } = model;

return (
                        <TabsContent value="review" className="space-y-3">
                          <div className="rounded-md border p-3 text-sm">
                            <div className="font-medium">Setup checklist</div>
                            <div className="mt-2 grid gap-1 text-muted-foreground md:grid-cols-2">
                              {getProductSetupItems(productDraft).map(
                                (item) => (
                                  <div
                                    key={item.label}
                                    className="flex items-center gap-2"
                                  >
                                    {item.done ? (
                                      <CheckCircle2 className="size-3 text-emerald-700" />
                                    ) : (
                                      <Clock className="size-3 text-amber-700" />
                                    )}
                                    <span>{item.label}</span>
                                  </div>
                                ),
                              )}
                            </div>
                          </div>
                          <div className="grid gap-3 md:grid-cols-2">
                            <div className="grid gap-1.5">
                              <Label>Catalog status</Label>
                              <Select
                                value={productDraft.status || "draft"}
                                onValueChange={(value) =>
                                  setProductField("status", value)
                                }
                              >
                                <SelectTrigger data-testid="webstore-product-status">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="planned">
                                    Planned
                                  </SelectItem>
                                  <SelectItem value="incomplete">
                                    Incomplete
                                  </SelectItem>
                                  <SelectItem value="ready">Ready</SelectItem>
                                  <SelectItem value="active">Active</SelectItem>
                                  <SelectItem value="archived">
                                    Archived
                                  </SelectItem>
                                  {productDraft.status === "draft" && (
                                    <SelectItem value="draft">
                                      Draft legacy
                                    </SelectItem>
                                  )}
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="grid gap-2 rounded border p-3 text-sm">
                              <div className="flex items-center gap-2">
                                <Checkbox
                                  checked={Boolean(
                                    productDraft.launch_packet_eligible,
                                  )}
                                  onCheckedChange={(checked) =>
                                    setProductField(
                                      "launch_packet_eligible",
                                      Boolean(checked),
                                    )
                                  }
                                  data-testid="webstore-product-packet-eligible"
                                />
                                <Label>Eligible for later Launch Packet</Label>
                              </div>
                              <div className="flex items-center gap-2">
                                <Checkbox
                                  checked={Boolean(
                                    productDraft.launch_packet_include,
                                  )}
                                  onCheckedChange={(checked) =>
                                    setProductField(
                                      "launch_packet_include",
                                      Boolean(checked),
                                    )
                                  }
                                  data-testid="webstore-product-packet-include"
                                />
                                <Label>
                                  Include when Launch Packet assembly is
                                  implemented
                                </Label>
                              </div>
                            </div>
                          </div>
                          <div className="grid gap-2">
                            <Label>Bundle items</Label>
                            <Select value="none" onValueChange={addBundleItem}>
                              <SelectTrigger data-testid="webstore-product-bundle-select">
                                <SelectValue placeholder="Add product to bundle" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="none">
                                  Choose product
                                </SelectItem>
                                {(detail.data?.products || [])
                                  .filter(
                                    (item) =>
                                      item.id !== productDraft.id &&
                                      item.status !== "archived",
                                  )
                                  .map((item) => (
                                    <SelectItem key={item.id} value={item.id}>
                                      {item.name}
                                    </SelectItem>
                                  ))}
                              </SelectContent>
                            </Select>
                            <div className="flex flex-wrap gap-2">
                              {(productDraft.bundle_items || []).map((item) => (
                                <Button
                                  key={item.product_id}
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() =>
                                    removeBundleItem(item.product_id)
                                  }
                                >
                                  {item.name_snapshot || item.product_id} remove
                                </Button>
                              ))}
                            </div>
                          </div>
                          <p className="text-xs text-muted-foreground">Prepare artwork and reviewed mockups in Images and Mockups before saving and submitting this product.</p>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              onClick={() => saveProduct.mutate()}
                              disabled={
                                saveProduct.isPending || !productDraft.name
                              }
                              data-testid="webstore-save-product"
                            >
                              <Save className="size-4 mr-2" />
                              Save Product
                            </Button>
                            {productDraft.status === "archived" ? (
                              <Button
                                variant="outline"
                                onClick={() =>
                                  restoreProduct.mutate(productDraft)
                                }
                              >
                                <RotateCcw className="size-4 mr-2" />
                                Restore Draft
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                onClick={() =>
                                  archiveProduct.mutate(productDraft)
                                }
                              >
                                <Archive className="size-4 mr-2" />
                                Archive
                              </Button>
                            )}
                          </div>
                          {selectedProduct?.template_provenance
                            ?.source_template_id && (
                            <div className="text-xs text-muted-foreground">
                              Copied from a product template. This product is
                              independent from later template changes.
                            </div>
                          )}
                        </TabsContent>
  );
}
