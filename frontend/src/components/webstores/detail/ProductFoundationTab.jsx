import { TabsContent } from "@/components/ui/tabs";
import ProductEditor from "./ProductEditor";
import ProductResourcesPanel from "./ProductResourcesPanel";
import SelectedProductsPanel from "./SelectedProductsPanel";

export default function ProductFoundationTab({ model }) {
  return (
    <TabsContent
      value="products"
      className="space-y-4"
      data-testid="webstore-product-foundation"
    >
      <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_1.4fr] gap-4">
        <SelectedProductsPanel model={model} />
        <ProductEditor model={model} />
      </div>
      <ProductResourcesPanel model={model} />
    </TabsContent>
  );
}
