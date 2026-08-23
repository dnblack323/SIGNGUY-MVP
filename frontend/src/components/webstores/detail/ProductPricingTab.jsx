import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TabsContent } from "@/components/ui/tabs";
import { centsToDollarsString } from "@/lib/format";
import { toIntCents } from "./WebstoreDetailUtils";

export default function ProductPricingTab({ model }) {
  const { productDraft, setProductField } = model;

return (
                        <TabsContent value="pricing" className="space-y-3">
                          <div className="grid gap-3 md:grid-cols-2">
                            <div className="grid gap-1.5">
                              <Label>Selling price (cents)</Label>
                              <Input
                                type="number"
                                min="0"
                                value={productDraft.selling_price_cents ?? 0}
                                onChange={(e) =>
                                  setProductField(
                                    "selling_price_cents",
                                    toIntCents(e.target.value),
                                  )
                                }
                                data-testid="webstore-product-selling-price"
                              />
                            </div>
                            <div className="grid gap-1.5">
                              <Label>Production cost (cents)</Label>
                              <Input
                                type="number"
                                min="0"
                                value={productDraft.production_cost_cents ?? 0}
                                onChange={(e) =>
                                  setProductField(
                                    "production_cost_cents",
                                    toIntCents(e.target.value),
                                  )
                                }
                                data-testid="webstore-product-production-cost"
                              />
                            </div>
                            <div className="grid gap-1.5">
                              <Label>Owner share (cents)</Label>
                              <Input
                                type="number"
                                min="0"
                                value={
                                  productDraft.store_owner_share_cents ?? 0
                                }
                                onChange={(e) =>
                                  setProductField(
                                    "store_owner_share_cents",
                                    toIntCents(e.target.value),
                                  )
                                }
                                data-testid="webstore-product-owner-share"
                              />
                            </div>
                            <div className="grid gap-1.5">
                              <Label>Fundraiser share (cents)</Label>
                              <Input
                                type="number"
                                min="0"
                                value={productDraft.fundraiser_share_cents ?? 0}
                                onChange={(e) =>
                                  setProductField(
                                    "fundraiser_share_cents",
                                    toIntCents(e.target.value),
                                  )
                                }
                              />
                            </div>
                            <div className="grid gap-1.5">
                              <Label>Platform fee (basis points)</Label>
                              <Input
                                type="number"
                                min="0"
                                max="10000"
                                value={
                                  productDraft.platform_fee_basis_points ?? 0
                                }
                                onChange={(e) =>
                                  setProductField(
                                    "platform_fee_basis_points",
                                    toIntCents(e.target.value),
                                  )
                                }
                              />
                            </div>
                            <div className="rounded-md border bg-slate-50 p-3 text-sm">
                              <div className="font-medium">Internal margin</div>
                              <div className="text-muted-foreground">
                                {centsToDollarsString(
                                  Math.max(
                                    0,
                                    Number(
                                      productDraft.selling_price_cents || 0,
                                    ) -
                                      Number(
                                        productDraft.production_cost_cents || 0,
                                      ) -
                                      Number(
                                        productDraft.store_owner_share_cents ||
                                          0,
                                      ) -
                                      Number(
                                        productDraft.fundraiser_share_cents ||
                                          0,
                                      ),
                                  ),
                                )}
                              </div>
                            </div>
                          </div>
                        </TabsContent>
  );
}
