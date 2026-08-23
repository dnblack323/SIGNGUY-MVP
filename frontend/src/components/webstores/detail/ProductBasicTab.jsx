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

export default function ProductBasicTab({ model }) {
  const { categories, id, productDraft, setProductDraft, setProductField } = model;

return (
                        <TabsContent value="basic" className="space-y-3">
                          <div className="grid gap-3 md:grid-cols-2">
                            <div className="grid gap-1.5">
                              <Label>Name</Label>
                              <Input
                                value={productDraft.name || ""}
                                onChange={(e) =>
                                  setProductField("name", e.target.value)
                                }
                                data-testid="webstore-product-name"
                              />
                            </div>
                            <div className="grid gap-1.5">
                              <Label>Product type</Label>
                              <Input
                                value={productDraft.product_type || ""}
                                onChange={(e) =>
                                  setProductField(
                                    "product_type",
                                    e.target.value,
                                  )
                                }
                              />
                            </div>
                            <div className="grid gap-1.5">
                              <Label>Category</Label>
                              <Select
                                value={productDraft.category_id || "none"}
                                onValueChange={(value) =>
                                  setProductDraft({
                                    ...productDraft,
                                    category_id: value === "none" ? "" : value,
                                    category_name:
                                      (categories.data?.items || []).find(
                                        (c) => c.id === value,
                                      )?.name || "",
                                  })
                                }
                              >
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="none">
                                    No category
                                  </SelectItem>
                                  {(categories.data?.items || [])
                                    .filter(
                                      (category) =>
                                        category.status === "active",
                                    )
                                    .map((category) => (
                                      <SelectItem
                                        key={category.id}
                                        value={category.id}
                                      >
                                        {category.name}
                                      </SelectItem>
                                    ))}
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="grid gap-1.5">
                              <Label>Production method</Label>
                              <Input
                                value={productDraft.production_method || ""}
                                onChange={(e) =>
                                  setProductField(
                                    "production_method",
                                    e.target.value,
                                  )
                                }
                              />
                            </div>
                          </div>
                          <div className="grid gap-1.5">
                            <Label>Short description</Label>
                            <Textarea
                              value={productDraft.short_description || ""}
                              onChange={(e) =>
                                setProductField(
                                  "short_description",
                                  e.target.value,
                                )
                              }
                            />
                          </div>
                          <div className="grid gap-1.5">
                            <Label>Full description</Label>
                            <Textarea
                              value={productDraft.full_description || ""}
                              onChange={(e) =>
                                setProductField(
                                  "full_description",
                                  e.target.value,
                                )
                              }
                            />
                          </div>
                        </TabsContent>
  );
}
