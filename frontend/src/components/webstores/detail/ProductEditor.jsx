import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ProductAiPanel from "./ProductAiPanel";
import ProductBasicTab from "./ProductBasicTab";
import ProductImagesTab from "./ProductImagesTab";
import ProductOptionsTab from "./ProductOptionsTab";
import ProductPricingTab from "./ProductPricingTab";
import ProductProductionTab from "./ProductProductionTab";
import ProductReviewTab from "./ProductReviewTab";

export default function ProductEditor({ model }) {
  const { productDraft, productError, refresh } = model;

  return (
    <Card data-testid="webstore-product-editor">
      <CardHeader>
        <CardTitle className="text-base">Focused Product Setup</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!productDraft.id ? (
          <div className="text-sm text-muted-foreground">
            Select a product or create a draft to edit product foundation fields.
          </div>
        ) : (
          <>
            {productError && (
              <Alert variant="destructive">
                <AlertTitle>Product was not saved</AlertTitle>
                <AlertDescription>
                  {productError}
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="mt-2"
                    onClick={refresh}
                  >
                    Reload latest product data
                  </Button>
                </AlertDescription>
              </Alert>
            )}
            <ProductAiPanel model={model} />
            <Tabs
              defaultValue="basic"
              className="space-y-3"
              data-testid="webstore-product-editor-sections"
            >
              <TabsList className="flex h-auto flex-wrap justify-start">
                <TabsTrigger value="basic">Basic Information</TabsTrigger>
                <TabsTrigger value="images">Images and Mockups</TabsTrigger>
                <TabsTrigger value="options">
                  Options and Personalization
                </TabsTrigger>
                <TabsTrigger value="pricing">Pricing and Shares</TabsTrigger>
                <TabsTrigger value="production">Production Setup</TabsTrigger>
                <TabsTrigger value="review">Review Status</TabsTrigger>
              </TabsList>
              <ProductBasicTab model={model} />
              <ProductImagesTab model={model} />
              <ProductOptionsTab model={model} />
              <ProductPricingTab model={model} />
              <ProductProductionTab model={model} />
              <ProductReviewTab model={model} />
            </Tabs>
          </>
        )}
      </CardContent>
    </Card>
  );
}
