import ContextualHelp from "@/components/help/ContextualHelp";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { extractError } from "@/lib/api";
import { getWebstoreFulfillmentSettings, saveWebstoreFulfillmentSettings } from "@/lib/webstores";
import { toast } from "sonner";

export const FULFILLMENT_METHOD_LABELS = {
  individual_shipping: "Individual shipping to each buyer",
  bulk_shipping: "Bulk shipping to the organizer",
  shop_pickup: "Pickup at our shop",
  organizer_pickup: "Bulk pickup by the organizer",
  event_distribution: "Distribution at the event",
  local_delivery: "Local delivery",
};

/** Shop-level Webstore fulfillment settings: owners only see the methods checked here. */
export default function WebstoreFulfillmentSettingsDialog({ open, onOpenChange }) {
  const settings = useQuery({ queryKey: ["webstore-fulfillment-settings"], queryFn: getWebstoreFulfillmentSettings, enabled: open });
  const [form, setForm] = useState(null);
  useEffect(() => {
    if (settings.data) setForm(settings.data);
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () => saveWebstoreFulfillmentSettings({
      supported_methods: form.supported_methods,
      default_pickup_location: form.default_pickup_location,
      pickup_instructions: form.pickup_instructions,
      pickup_windows_enabled: form.pickup_windows_enabled,
      default_window_start: form.default_window_start,
      default_window_end: form.default_window_end,
    }),
    onSuccess: (data) => { setForm(data); toast.success("Fulfillment settings saved"); onOpenChange(false); },
    onError: (err) => toast.error(extractError(err)),
  });
  const toggle = (method, on) => setForm((f) => ({ ...f, supported_methods: on ? [...f.supported_methods, method] : f.supported_methods.filter((m) => m !== method) }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]" data-testid="webstore-fulfillment-settings">
        <DialogHeader>
          <DialogTitle>Webstore fulfillment settings <ContextualHelp surfaceKey="webstores.fulfillment" module="webstores" /></DialogTitle>
          <DialogDescription>Choose how your shop can get orders to buyers. Questionnaires only offer these methods.{form?.timezone ? ` Times use your shop timezone (${form.timezone}).` : ""}</DialogDescription>
        </DialogHeader>
        {form && (
          <div className="grid gap-3 text-sm">
            <div className="grid gap-2">
              {Object.entries(FULFILLMENT_METHOD_LABELS).map(([method, label]) => (
                <label key={method} className="flex items-center gap-2">
                  <Checkbox checked={form.supported_methods.includes(method)} onCheckedChange={(v) => toggle(method, Boolean(v))} data-testid={`fulfillment-method-${method}`} />{label}
                </label>
              ))}
            </div>
            <div className="grid gap-1"><Label>Default pickup location</Label><Input value={form.default_pickup_location} onChange={(e) => setForm({ ...form, default_pickup_location: e.target.value })} /></div>
            <div className="grid gap-1"><Label>Pickup instructions</Label><Textarea rows={2} value={form.pickup_instructions} onChange={(e) => setForm({ ...form, pickup_instructions: e.target.value })} /></div>
            <label className="flex items-center gap-2"><Checkbox checked={form.pickup_windows_enabled} onCheckedChange={(v) => setForm({ ...form, pickup_windows_enabled: Boolean(v) })} />Let owners choose up to three pickup times</label>
            <div className="grid grid-cols-2 gap-2">
              <div className="grid gap-1"><Label>Default pickup start</Label><Input type="time" value={form.default_window_start} onChange={(e) => setForm({ ...form, default_window_start: e.target.value })} /></div>
              <div className="grid gap-1"><Label>Default pickup end</Label><Input type="time" value={form.default_window_end} onChange={(e) => setForm({ ...form, default_window_end: e.target.value })} /></div>
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => save.mutate()} disabled={!form || !form.supported_methods.length || save.isPending} data-testid="fulfillment-settings-save">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
