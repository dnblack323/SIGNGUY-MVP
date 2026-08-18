import { Link } from "react-router-dom";
import {
  Archive,
  Copy,
  Save,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function ProductResourcesPanel({ model }) {
  const {
    archiveCategory,
    categories,
    categoryEditDraft,
    editingCategoryId,
    id,
    restoreCategory,
    saveCategory,
    setCategoryEditDraft,
    setEditingCategoryId,
    templates,
  } = model;

return (
            <div
              className="grid grid-cols-1 xl:grid-cols-2 gap-4"
              data-testid="webstore-product-resources"
            >
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Product Templates</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div className="text-muted-foreground">
                    Templates are reusable shop resources. Copy one into this
                    Webstore from Products, then edit the private product
                    draft here.
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button asChild variant="outline" size="sm">
                      <Link to="/webstores">Manage Product Templates</Link>
                    </Button>
                    <Button type="button" variant="outline" size="sm" disabled>
                      Create New Template Later
                    </Button>
                  </div>
                  <div className="rounded border divide-y">
                    {(templates.data || []).slice(0, 5).map((template) => (
                      <div
                        key={template.id}
                        className="flex items-center justify-between gap-3 p-3"
                      >
                        <div>
                          <div className="font-medium">
                            {template.template_name}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {template.scope === "platform"
                              ? "Platform starter"
                              : "Tenant template"}{" "}
                            -{" "}
                            {template.status ||
                              (template.active ? "active" : "archived")}
                          </div>
                        </div>
                        {template.scope === "platform" && (
                          <Badge variant="outline">Starter</Badge>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card data-testid="webstore-category-resources">
                <CardHeader>
                  <CardTitle className="text-base">
                    Product Categories
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div className="text-muted-foreground">
                    Categories can be selected for this Webstore's products. New
                    category creation belongs in the shared category resource
                    area.
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button asChild variant="outline" size="sm">
                      <Link to="/webstores">Manage Categories</Link>
                    </Button>
                    <Button type="button" variant="outline" size="sm" disabled>
                      Create New Category Later
                    </Button>
                  </div>
                  <div className="rounded border divide-y">
                    {(categories.data?.items || []).map((category) => (
                      <div key={category.id} className="p-3 space-y-2">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="font-medium">{category.name}</div>
                            <div className="text-xs text-muted-foreground">
                              {category.status} - {category.product_count || 0}{" "}
                              active products
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingCategoryId(category.id);
                                setCategoryEditDraft(category);
                              }}
                            >
                              Edit
                            </Button>
                            {category.status === "archived" ? (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => restoreCategory.mutate(category)}
                              >
                                Restore
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => archiveCategory.mutate(category)}
                              >
                                Archive
                              </Button>
                            )}
                          </div>
                        </div>
                        {editingCategoryId === category.id && (
                          <div className="grid gap-2 md:grid-cols-[1fr_1fr_auto] rounded bg-slate-50 p-2">
                            <Input
                              value={categoryEditDraft.name || ""}
                              onChange={(e) =>
                                setCategoryEditDraft({
                                  ...categoryEditDraft,
                                  name: e.target.value,
                                })
                              }
                            />
                            <Input
                              value={categoryEditDraft.description || ""}
                              onChange={(e) =>
                                setCategoryEditDraft({
                                  ...categoryEditDraft,
                                  description: e.target.value,
                                })
                              }
                            />
                            <Button
                              size="sm"
                              disabled={
                                !categoryEditDraft.name ||
                                saveCategory.isPending
                              }
                              onClick={() => saveCategory.mutate()}
                              data-testid="webstore-save-category"
                            >
                              Save
                            </Button>
                          </div>
                        )}
                      </div>
                    ))}
                    {(categories.data?.legacy_categories || []).map((name) => (
                      <div
                        key={name}
                        className="p-3 text-xs text-muted-foreground"
                      >
                        Legacy free-text category preserved: {name}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
  );
}
