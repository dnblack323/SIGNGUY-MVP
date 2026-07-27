import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

const CATEGORIES = [
  ["", "All categories"],
  ["banners", "Banners"],
  ["rigid_signs", "Rigid Signs"],
  ["cut_vinyl", "Cut Vinyl"],
  ["digital_print", "Digital Print"],
  ["vehicle_graphics", "Vehicle Graphics"],
  ["apparel", "Apparel"],
  ["promotional", "Promotional"],
  ["services", "Services"],
  ["custom", "Custom"],
];

const money = (value) => (
  value == null ? "Unavailable" : Number(value).toLocaleString("en-US", { style: "currency", currency: "USD" })
);
const humanize = (value) => String(value || "").replaceAll("_", " ");

export default function SavedCalculationLibrary({
  canRead = false,
  canWrite = false,
  canCalculate = false,
  onUseCalculation,
  compact = false,
}) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [archived, setArchived] = useState(false);
  const [selected, setSelected] = useState(null);
  const [editName, setEditName] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [reuseResult, setReuseResult] = useState(null);

  const params = useMemo(() => ({ search: search || undefined, category: category || undefined, archived }), [search, category, archived]);
  const listQuery = useQuery({
    queryKey: ["pricing-saved-calculations", params],
    queryFn: async () => (await api.get("/pricing/saved-calculations", { params })).data,
    enabled: canRead,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["pricing-saved-calculations"] });

  const patch = useMutation({
    mutationFn: async ({ id, body }) => (await api.patch(`/pricing/saved-calculations/${id}`, body)).data,
    onSuccess: (doc) => {
      setSelected(doc);
      setEditName(doc.name || "");
      setEditNotes(doc.notes || "");
      refresh();
      toast.success("Saved calculation updated");
    },
    onError: (error) => toast.error(extractError(error)),
  });

  const archive = useMutation({
    mutationFn: async (id) => (await api.post(`/pricing/saved-calculations/${id}/archive`)).data,
    onSuccess: (doc) => {
      setSelected(doc);
      refresh();
      toast.success("Saved calculation archived");
    },
    onError: (error) => toast.error(extractError(error)),
  });

  const restore = useMutation({
    mutationFn: async (id) => (await api.post(`/pricing/saved-calculations/${id}/restore`)).data,
    onSuccess: (doc) => {
      setSelected(doc);
      refresh();
      toast.success("Saved calculation restored");
    },
    onError: (error) => toast.error(extractError(error)),
  });

  const duplicate = useMutation({
    mutationFn: async (doc) => (await api.post(`/pricing/saved-calculations/${doc.id}/duplicate`, { name: `${doc.name} Copy` })).data,
    onSuccess: (doc) => {
      setSelected(doc);
      setEditName(doc.name || "");
      setEditNotes(doc.notes || "");
      refresh();
      toast.success("Saved calculation duplicated");
    },
    onError: (error) => toast.error(extractError(error)),
  });

  const useSaved = useMutation({
    mutationFn: async (doc) => (await api.post(`/pricing/saved-calculations/${doc.id}/recalculate`)).data,
    onSuccess: (data) => {
      setReuseResult(data);
      onUseCalculation?.(data);
      toast.success("Loaded saved calculation as a working copy");
    },
    onError: (error) => toast.error(extractError(error)),
  });

  function selectDoc(doc) {
    setSelected(doc);
    setEditName(doc.name || "");
    setEditNotes(doc.notes || "");
    setReuseResult(null);
  }

  if (!canRead) {
    return (
      <Card data-testid="saved-calculations-permission-denied">
        <CardContent className="py-6 text-sm text-muted-foreground">
          You do not have permission to view saved calculations.
        </CardContent>
      </Card>
    );
  }

  const items = listQuery.data?.items || [];

  return (
    <div className={compact ? "grid gap-3" : "grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)] gap-4"} data-testid="saved-calculation-library">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Saved Calculation Library</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-1.5">
            <Label>Search</Label>
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search names or notes" data-testid="saved-calc-search" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="grid gap-1.5">
              <Label>Category</Label>
              <select value={category} onChange={(event) => setCategory(event.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm" data-testid="saved-calc-category-filter">
                {CATEGORIES.map(([id, label]) => <option key={id || "all"} value={id}>{label}</option>)}
              </select>
            </div>
            <div className="grid gap-1.5">
              <Label>Status</Label>
              <select value={archived ? "archived" : "active"} onChange={(event) => setArchived(event.target.value === "archived")} className="h-9 rounded-md border border-input bg-background px-3 text-sm" data-testid="saved-calc-status-filter">
                <option value="active">Active</option>
                <option value="archived">Archived</option>
              </select>
            </div>
          </div>

          <div className="divide-y rounded-md border" data-testid="saved-calc-list">
            {listQuery.isLoading && <div className="p-3 text-sm text-muted-foreground">Loading saved calculations...</div>}
            {!listQuery.isLoading && items.length === 0 && <div className="p-3 text-sm text-muted-foreground">No saved calculations found.</div>}
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => selectDoc(item)}
                className={`w-full p-3 text-left hover:bg-muted/50 ${selected?.id === item.id ? "bg-primary/5" : ""}`}
                data-testid={`saved-calc-row-${item.id}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{item.name}</span>
                  {item.archived && <Badge variant="secondary">Archived</Badge>}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {humanize(item.category)} · Saved {money(item.selling_price)}
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Calculation Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3" data-testid="saved-calc-detail">
          {!selected ? (
            <div className="text-sm text-muted-foreground">Open a saved calculation to view, rename, duplicate, archive, restore, or use it.</div>
          ) : (
            <>
              <div className="grid gap-2 md:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label>Name</Label>
                  <Input value={editName} onChange={(event) => setEditName(event.target.value)} data-testid="saved-calc-edit-name" />
                </div>
                <div className="rounded-md border bg-muted/30 p-3 text-sm">
                  <div className="text-xs text-muted-foreground">Saved Price</div>
                  <div className="text-xl font-semibold tabular-nums" data-testid="saved-calc-saved-price">{money(selected.selling_price)}</div>
                </div>
              </div>
              <div className="grid gap-1.5">
                <Label>Notes</Label>
                <Textarea rows={2} value={editNotes} onChange={(event) => setEditNotes(event.target.value)} data-testid="saved-calc-edit-notes" />
              </div>
              <div className="grid gap-2 md:grid-cols-3 text-sm">
                <div><span className="text-muted-foreground">Category:</span> {humanize(selected.category)}</div>
                <div><span className="text-muted-foreground">Canonical:</span> {humanize(selected.canonical_method_id)}</div>
                <div><span className="text-muted-foreground">Selected:</span> {humanize(selected.selected_method_id)}</div>
              </div>
              <div className="rounded-md border p-2 text-xs" data-testid="saved-calc-method-results">
                {(selected.pricing_method_results || []).slice(0, 6).map((row) => (
                  <div key={row.method_id} className="flex justify-between gap-2">
                    <span>{row.display_name || humanize(row.method_id)} {row.available === false ? "(unavailable)" : ""}</span>
                    <span className="tabular-nums">{money(row.amount)}</span>
                  </div>
                ))}
              </div>
              {(selected.warnings || []).length > 0 && (
                <div className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800" data-testid="saved-calc-warnings">
                  {selected.warnings.join("; ")}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => patch.mutate({ id: selected.id, body: { name: editName, notes: editNotes } })} disabled={!canWrite || patch.isPending} data-testid="saved-calc-save-metadata">Save Metadata</Button>
                <Button size="sm" variant="outline" onClick={() => duplicate.mutate(selected)} disabled={!canWrite || duplicate.isPending} data-testid="saved-calc-duplicate">Duplicate</Button>
                {selected.archived ? (
                  <Button size="sm" variant="outline" onClick={() => restore.mutate(selected.id)} disabled={!canWrite || restore.isPending} data-testid="saved-calc-restore">Restore</Button>
                ) : (
                  <Button size="sm" variant="outline" onClick={() => archive.mutate(selected.id)} disabled={!canWrite || archive.isPending} data-testid="saved-calc-archive">Archive</Button>
                )}
                <Button size="sm" onClick={() => useSaved.mutate(selected)} disabled={!canCalculate || selected.archived || useSaved.isPending} data-testid="saved-calc-use">Use Calculation</Button>
              </div>
              {selected.archived && (
                <div className="text-xs text-muted-foreground" data-testid="saved-calc-archived-use-blocked">
                  Restore this saved calculation before using it.
                </div>
              )}
              {reuseResult && (
                <div className="rounded-md border bg-muted/30 p-3 text-sm" data-testid="saved-calc-reuse-result">
                  <div>Saved Price: <strong>{money(reuseResult.saved_price)}</strong></div>
                  <div>Current Price: <strong>{money(reuseResult.current_price)}</strong></div>
                  {reuseResult.price_changed && <Badge variant="secondary" data-testid="saved-calc-price-diff">Current price differs from saved price</Badge>}
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
