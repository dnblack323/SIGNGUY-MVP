import { Link } from "react-router-dom";
import {
  Archive,
  CheckCircle2,
  Clock,
  PackagePlus,
  Send,
} from "lucide-react";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { centsToDollarsString } from "@/lib/format";
import {
  productCatalogStatus,
  staffProductImageUrl,
} from "./WebstoreDetailUtils";

export default function SelectedProductsPanel({ model }) {
  const {
    activeProducts,
    archiveProduct,
    categories,
    createBlankProduct,
    duplicateProduct,
    filteredProducts,
    formatLabel,
    getProductSetupItems,
    id,
    packet,
    productFilters,
    reorderProducts,
    restoreProduct,
    setProductFilters,
    startProductSetup,
    submitProductApproval,
  } = model;

return (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Selected Products</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Alert>
                    <AlertTitle>Private catalog setup</AlertTitle>
                    <AlertDescription>
                      Each selected product stays private while Staff completes
                      catalog status, options, cents-based pricing, shares,
                      media, and packet eligibility.
                    </AlertDescription>
                  </Alert>
                  <div className="grid gap-2 md:grid-cols-3">
                    <Input
                      placeholder="Search products"
                      value={productFilters.q}
                      onChange={(e) =>
                        setProductFilters({
                          ...productFilters,
                          q: e.target.value,
                        })
                      }
                      data-testid="webstore-product-search"
                    />
                    <Select
                      value={productFilters.status}
                      onValueChange={(value) =>
                        setProductFilters({ ...productFilters, status: value })
                      }
                    >
                      <SelectTrigger data-testid="webstore-product-status-filter">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All statuses</SelectItem>
                        <SelectItem value="planned">Planned</SelectItem>
                        <SelectItem value="incomplete">Incomplete</SelectItem>
                        <SelectItem value="ready">Ready</SelectItem>
                        <SelectItem value="active">Active</SelectItem>
                        <SelectItem value="archived">Archived</SelectItem>
                      </SelectContent>
                    </Select>
                    <Select
                      value={productFilters.category_id}
                      onValueChange={(value) =>
                        setProductFilters({
                          ...productFilters,
                          category_id: value,
                        })
                      }
                    >
                      <SelectTrigger data-testid="webstore-product-category-filter">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All categories</SelectItem>
                        {(categories.data?.items || []).map((category) => (
                          <SelectItem key={category.id} value={category.id}>
                            {category.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      onClick={() => createBlankProduct.mutate()}
                      disabled={createBlankProduct.isPending}
                      data-testid="webstore-create-blank-product"
                    >
                      <PackagePlus className="size-4 mr-2" />
                      Create Custom Product
                    </Button>
                    <Button asChild variant="link" size="sm">
                      <Link to="/webstores">Manage Product Templates</Link>
                    </Button>
                    <Button asChild variant="link" size="sm">
                      <Link to="/webstores">Manage Categories</Link>
                    </Button>
                  </div>
                  <div className="grid gap-3">
                    {filteredProducts.map((product, index) => (
                      <div
                        key={product.id}
                        className="rounded-md border p-3 text-sm"
                        data-testid={`webstore-product-card-${product.id}`}
                      >
                        <div className="flex gap-3">
                          <div className="h-20 w-24 shrink-0 overflow-hidden rounded border bg-slate-100">
                            {staffProductImageUrl(product) ? (
                              <img
                                className="h-full w-full object-cover"
                                src={staffProductImageUrl(product)}
                                alt=""
                              />
                            ) : (
                              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                                No image
                              </div>
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div>
                                <div className="font-medium">
                                  {product.name}
                                </div>
                                <div className="text-xs text-muted-foreground capitalize">
                                  {formatLabel(productCatalogStatus(product))} -{" "}
                                  {product.public
                                    ? "public legacy"
                                    : "private catalog"}{" "}
                                  -{" "}
                                  {product.category_name ||
                                    product.category ||
                                    "No category"}
                                </div>
                              </div>
                              <Badge variant="outline">
                                {centsToDollarsString(
                                  product.selling_price_cents,
                                )}
                              </Badge>
                              <Badge variant={product.approval_status === "approved" ? "secondary" : "outline"}>
                                {formatLabel(product.approval_status || "not_submitted")}
                              </Badge>
                            </div>
                            <div className="mt-3 grid gap-1 text-xs text-muted-foreground md:grid-cols-2">
                              {getProductSetupItems(product).map((item) => (
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
                              ))}
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                type="button"
                                size="sm"
                                onClick={() => startProductSetup(product)}
                                data-testid={`webstore-product-row-${product.id}`}
                              >
                                Continue Setup
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={!staffProductImageUrl(product)}
                              >
                                Preview
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => duplicateProduct.mutate(product)}
                                disabled={duplicateProduct.isPending || product.status === "archived"}
                              >
                                Duplicate
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  const ids = activeProducts.map((item) => item.id);
                                  const current = ids.indexOf(product.id);
                                  if (current > 0) {
                                    [ids[current - 1], ids[current]] = [ids[current], ids[current - 1]];
                                    reorderProducts.mutate(ids);
                                  }
                                }}
                                disabled={index === 0 || reorderProducts.isPending || product.status === "archived"}
                              >
                                Move Up
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  const ids = activeProducts.map((item) => item.id);
                                  const current = ids.indexOf(product.id);
                                  if (current >= 0 && current < ids.length - 1) {
                                    [ids[current + 1], ids[current]] = [ids[current], ids[current + 1]];
                                    reorderProducts.mutate(ids);
                                  }
                                }}
                                disabled={index >= filteredProducts.length - 1 || reorderProducts.isPending || product.status === "archived"}
                              >
                                Move Down
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => submitProductApproval.mutate(product)}
                                disabled={submitProductApproval.isPending || product.status === "archived"}
                              >
                                Send Product Approval
                              </Button>
                              {product.status === "archived" ? (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => restoreProduct.mutate(product)}
                                >
                                  Restore
                                </Button>
                              ) : (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => archiveProduct.mutate(product)}
                                >
                                  Archive
                                </Button>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                    {filteredProducts.length === 0 && (
                      <div className="p-3 text-sm text-muted-foreground">
                        No products match these filters.
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
  );
}
