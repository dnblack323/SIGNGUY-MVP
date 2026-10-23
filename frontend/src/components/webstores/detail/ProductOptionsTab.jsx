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
                                    className="grid gap-2 rounded border p-2 md:grid-cols-3"
                                  >
                                    <Input
                                      placeholder="Size"
                                      aria-label={`Variant ${index + 1} size`}
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
                                      aria-label={`Variant ${index + 1} color`}
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
                                      aria-label={`Variant ${index + 1} SKU`}
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
                                      aria-label={`Variant ${index + 1} price cents`}
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
                                    <Select value={variant.status || "active"} onValueChange={(value) => setVariantField(index, "status", value)}>
                                      <SelectTrigger aria-label={`Variant ${index + 1} status`}><SelectValue /></SelectTrigger>
                                      <SelectContent>
                                        <SelectItem value="active">Active</SelectItem>
                                        <SelectItem value="inactive">Inactive</SelectItem>
                                        <SelectItem value="archived">Archived</SelectItem>
                                      </SelectContent>
                                    </Select>
                                    <label className="flex items-center gap-2 text-sm">
                                      <Checkbox checked={variant.available !== false} onCheckedChange={(checked) => setVariantField(index, "available", Boolean(checked))} aria-label={`Variant ${index + 1} manually available`} />
                                      Manually available
                                    </label>
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
                            <p className="text-xs text-muted-foreground">Availability is set by staff; it does not confirm supplier stock. Inactive or unavailable variants cannot be ordered.</p>
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
                                    key={index}
                                    className="grid gap-2 rounded border p-3 md:grid-cols-2"
                                  >
                                    <Input
                                      placeholder="Key"
                                      aria-label={`Prompt ${index + 1} key`}
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
                                      aria-label={`Prompt ${index + 1} name`}
                                      maxLength={120}
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
                                      <SelectTrigger aria-label={`Prompt ${index + 1} type`}>
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
                                    <label className="flex items-center gap-2 text-sm">
                                      <Checkbox checked={Boolean(field.required)} onCheckedChange={(checked) => setPersonalizationField(index, "required", Boolean(checked))} aria-label={`Prompt ${index + 1} required`} />
                                      Required
                                    </label>
                                    {field.type === "select" ? (
                                      <div className="grid gap-1.5 md:col-span-2">
                                        <Label htmlFor={`personalization-choices-${index}`}>Choices (one per line, up to 20)</Label>
                                        <Textarea id={`personalization-choices-${index}`} rows={3} value={(field.choices || []).join("\n")} onChange={(e) => setPersonalizationField(index, "choices", e.target.value.split("\n"))} />
                                        {!(field.choices || []).some((choice) => String(choice).trim()) && <p className="text-xs text-amber-800">Add at least one choice before saving.</p>}
                                      </div>
                                    ) : (
                                      <div className="grid gap-1.5">
                                        <Label htmlFor={`personalization-placeholder-${index}`}>Placeholder</Label>
                                        <Input id={`personalization-placeholder-${index}`} maxLength={120} value={field.placeholder || ""} onChange={(e) => setPersonalizationField(index, "placeholder", e.target.value)} />
                                      </div>
                                    )}
                                    {(!field.type || ["text", "textarea"].includes(field.type)) && (
                                      <div className="grid gap-1.5">
                                        <Label htmlFor={`personalization-max-${index}`}>Maximum characters</Label>
                                        <Input id={`personalization-max-${index}`} type="number" min="1" step="1" placeholder="Default limit" value={field.max_length ?? ""} onChange={(e) => setPersonalizationField(index, "max_length", e.target.value === "" ? "" : Number(e.target.value))} />
                                        <p className="text-xs text-muted-foreground">Leave blank for the existing default limit.</p>
                                      </div>
                                    )}
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
