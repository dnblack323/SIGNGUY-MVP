import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TabsContent } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { toIntCents } from "./WebstoreDetailUtils";

export default function ProductOptionsTab({ model }) {
  const {
    addPersonalizationField,
    addVariant,
    id,
    productDraft,
    removePersonalizationField,
    removeVariant,
    setPersonalizationField,
    setProductField,
    setVariantField,
  } = model;

return (
                        <TabsContent value="options" className="space-y-4">
                          <div className="space-y-2">
                            <div className="flex items-center justify-between gap-2">
                              <Label>Variants and SKUs</Label>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={addVariant}
                              >
                                Add Variant
                              </Button>
                            </div>
                            <div className="grid gap-2">
                              {(productDraft.variants || []).map(
                                (variant, index) => (
                                  <div
                                    key={variant.id || index}
                                    className="grid gap-2 rounded border p-2 md:grid-cols-[1fr_1fr_1fr_120px_auto]"
                                  >
                                    <Input
                                      placeholder="Size"
                                      value={variant.size || ""}
                                      onChange={(e) =>
                                        setVariantField(
                                          index,
                                          "size",
                                          e.target.value,
                                        )
                                      }
                                      data-testid={`webstore-variant-size-${index}`}
                                    />
                                    <Input
                                      placeholder="Color"
                                      value={variant.color || ""}
                                      onChange={(e) =>
                                        setVariantField(
                                          index,
                                          "color",
                                          e.target.value,
                                        )
                                      }
                                      data-testid={`webstore-variant-color-${index}`}
                                    />
                                    <Input
                                      placeholder="SKU"
                                      value={variant.sku || ""}
                                      onChange={(e) =>
                                        setVariantField(
                                          index,
                                          "sku",
                                          e.target.value,
                                        )
                                      }
                                      data-testid={`webstore-variant-sku-${index}`}
                                    />
                                    <Input
                                      type="number"
                                      min="0"
                                      placeholder="Price cents"
                                      value={variant.selling_price_cents ?? ""}
                                      onChange={(e) =>
                                        setVariantField(
                                          index,
                                          "selling_price_cents",
                                          toIntCents(e.target.value),
                                        )
                                      }
                                      data-testid={`webstore-variant-price-${index}`}
                                    />
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      onClick={() => removeVariant(index)}
                                    >
                                      Remove
                                    </Button>
                                  </div>
                                ),
                              )}
                              {(productDraft.variants || []).length === 0 && (
                                <div className="rounded border p-3 text-sm text-muted-foreground">
                                  No variants yet. A single SKU can still be
                                  saved on this product.
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="grid gap-3 md:grid-cols-2">
                            <div className="grid gap-1.5">
                              <Label>Product SKU</Label>
                              <Input
                                value={productDraft.sku || ""}
                                onChange={(e) =>
                                  setProductField("sku", e.target.value)
                                }
                                data-testid="webstore-product-sku"
                              />
                            </div>
                            <div className="grid gap-1.5">
                              <Label>Inventory policy</Label>
                              <Select
                                value={
                                  productDraft.inventory_policy || "not_tracked"
                                }
                                onValueChange={(value) =>
                                  setProductField("inventory_policy", value)
                                }
                              >
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="not_tracked">
                                    Not tracked
                                  </SelectItem>
                                  <SelectItem value="track_quantity">
                                    Track quantity
                                  </SelectItem>
                                  <SelectItem value="made_to_order">
                                    Made to order
                                  </SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="grid gap-1.5">
                              <Label>Inventory quantity</Label>
                              <Input
                                type="number"
                                min="0"
                                value={productDraft.inventory_quantity ?? ""}
                                onChange={(e) =>
                                  setProductField(
                                    "inventory_quantity",
                                    e.target.value === ""
                                      ? ""
                                      : toIntCents(e.target.value),
                                  )
                                }
                              />
                            </div>
                          </div>
                          <div className="space-y-2">
                            <div className="flex items-center justify-between gap-2">
                              <Label>Personalization</Label>
                              <div className="flex items-center gap-2 text-sm">
                                <Checkbox
                                  checked={Boolean(
                                    productDraft.personalization_enabled,
                                  )}
                                  onCheckedChange={(checked) =>
                                    setProductField(
                                      "personalization_enabled",
                                      Boolean(checked),
                                    )
                                  }
                                />
                                Enabled
                              </div>
                            </div>
                            <div className="grid gap-2">
                              {(productDraft.personalization_fields || []).map(
                                (field, index) => (
                                  <div
                                    key={field.key || index}
                                    className="grid gap-2 rounded border p-2 md:grid-cols-[1fr_1fr_120px_auto]"
                                  >
                                    <Input
                                      placeholder="Key"
                                      value={field.key || ""}
                                      onChange={(e) =>
                                        setPersonalizationField(
                                          index,
                                          "key",
                                          e.target.value,
                                        )
                                      }
                                    />
                                    <Input
                                      placeholder="Prompt label"
                                      value={field.label || ""}
                                      onChange={(e) =>
                                        setPersonalizationField(
                                          index,
                                          "label",
                                          e.target.value,
                                        )
                                      }
                                      data-testid={`webstore-personalization-label-${index}`}
                                    />
                                    <Select
                                      value={field.type || "text"}
                                      onValueChange={(value) =>
                                        setPersonalizationField(
                                          index,
                                          "type",
                                          value,
                                        )
                                      }
                                    >
                                      <SelectTrigger>
                                        <SelectValue />
                                      </SelectTrigger>
                                      <SelectContent>
                                        <SelectItem value="text">
                                          Text
                                        </SelectItem>
                                        <SelectItem value="textarea">
                                          Textarea
                                        </SelectItem>
                                        <SelectItem value="select">
                                          Select
                                        </SelectItem>
                                        <SelectItem value="number">
                                          Number
                                        </SelectItem>
                                      </SelectContent>
                                    </Select>
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      onClick={() =>
                                        removePersonalizationField(index)
                                      }
                                    >
                                      Remove
                                    </Button>
                                  </div>
                                ),
                              )}
                            </div>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={addPersonalizationField}
                              data-testid="webstore-add-personalization"
                            >
                              Add Prompt
                            </Button>
                          </div>
                        </TabsContent>
  );
}
