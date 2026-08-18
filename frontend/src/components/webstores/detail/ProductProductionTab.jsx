import { Label } from "@/components/ui/label";
import { TabsContent } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

export default function ProductProductionTab({ model }) {
  const { productDraft, setProductField } = model;

return (
                        <TabsContent value="production" className="space-y-3">
                          <div className="grid gap-3 md:grid-cols-2">
                            <div className="grid gap-1.5">
                              <Label>Internal production notes</Label>
                              <Textarea
                                value={productDraft.production_notes || ""}
                                onChange={(e) =>
                                  setProductField(
                                    "production_notes",
                                    e.target.value,
                                  )
                                }
                              />
                            </div>
                            <div className="grid gap-1.5">
                              <Label>Private supplier/source information</Label>
                              <Textarea
                                value={productDraft.supplier_source_info || ""}
                                onChange={(e) =>
                                  setProductField(
                                    "supplier_source_info",
                                    e.target.value,
                                  )
                                }
                              />
                            </div>
                            <div className="grid gap-1.5 md:col-span-2">
                              <Label>Private fulfillment notes</Label>
                              <Textarea
                                value={productDraft.fulfillment_notes || ""}
                                onChange={(e) =>
                                  setProductField(
                                    "fulfillment_notes",
                                    e.target.value,
                                  )
                                }
                              />
                            </div>
                          </div>
                        </TabsContent>
  );
}
