import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TabsContent } from "@/components/ui/tabs";
import {
  productImageAltText,
  staffProductImageUrl,
} from "./WebstoreDetailUtils";

export default function ProductImagesTab({ model }) {
  const { id, productDraft, removeImageSlot, setImageField, setImageFile, setupFileItems } = model;

return (
                        <TabsContent value="images" className="space-y-3">
                          <div className="grid gap-3 md:grid-cols-2">
                            {["primary", "secondary"].map((slot) => (
                              <div
                                key={slot}
                                className="rounded border p-3 space-y-2"
                                data-testid={`webstore-product-image-${slot}`}
                              >
                                <div className="font-medium capitalize">
                                  {slot} image
                                </div>
                                <Select
                                  value={
                                    productDraft.customer_images?.[slot]
                                      ?.file_id || "none"
                                  }
                                  onValueChange={(value) =>
                                    setImageFile(slot, value)
                                  }
                                >
                                  <SelectTrigger
                                    data-testid={`webstore-product-image-${slot}-file`}
                                  >
                                    <SelectValue placeholder="Choose uploaded setup file" />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="none">
                                      No image
                                    </SelectItem>
                                    {setupFileItems.map((file) => (
                                      <SelectItem key={file.id} value={file.id}>
                                        {file.file_name || file.id}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                                <Input
                                  placeholder="Alternate text"
                                  value={productImageAltText(
                                    productDraft,
                                    slot,
                                  )}
                                  onChange={(e) =>
                                    setImageField(
                                      slot,
                                      "alt_text",
                                      e.target.value,
                                    )
                                  }
                                />
                                <p className="text-xs text-muted-foreground">
                                  {slot === "primary"
                                    ? "Recommended: 1600x1200 px or larger."
                                    : "Recommended: 1200x1200 px or larger."}
                                </p>
                                {staffProductImageUrl(productDraft, slot) && (
                                  <img
                                    className="aspect-video w-full rounded border object-cover"
                                    src={staffProductImageUrl(
                                      productDraft,
                                      slot,
                                    )}
                                    alt={productImageAltText(
                                      productDraft,
                                      slot,
                                    )}
                                  />
                                )}
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => removeImageSlot(slot)}
                                >
                                  Remove
                                </Button>
                              </div>
                            ))}
                          </div>
                        </TabsContent>
  );
}
