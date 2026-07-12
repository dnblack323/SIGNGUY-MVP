import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import api, { extractError, API } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Download } from "lucide-react";
import { money, basisLabel } from "@/lib/ec7";

// Download a CSV by posting filters via fetch (so we get Content-Disposition)
async function downloadCsv(path, body, filename) {
  const token = localStorage.getItem("signguy.token");
  const res = await fetch(`${API}${path}`, {
    method: "POST", headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body || {}),
    credentials: "include",
  });
  if (!res.ok) { toast.error(`Export failed (${res.status})`); return; }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
}

function formatCell(col, val) {
  if (val === null || val === undefined || val === "") return "—";
  if (col.money) return money(val);
  if (col.date) return String(val).slice(0, 10);
  return String(val);
}

function CuratedTab() {
  const [dateRange, setDateRange] = useState({ from: "", to: "" });
  const [selected, setSelected] = useState(null);
  const list = useQuery({ queryKey: ["reports-list"], queryFn: async () => (await api.get("/reports")).data });
  const report = list.data?.reports?.find((r) => r.key === selected);
  const preview = useQuery({
    queryKey: ["report-preview", selected, dateRange],
    queryFn: async () => (await api.post(`/reports/${selected}/run`, { filters: { date_from: dateRange.from || undefined, date_to: dateRange.to || undefined }, preview_limit: 100 })).data,
    enabled: !!selected,
  });
  return (
    <div className="grid md:grid-cols-[280px_1fr] gap-4" data-testid="reports-curated-panel">
      <div className="space-y-2" data-testid="reports-list">
        {(list.data?.reports || []).map((r) => (
          <button key={r.key} onClick={() => setSelected(r.key)} data-testid={`report-item-${r.key}`}
            className={`w-full text-left rounded-md border px-3 py-2 text-sm ${selected === r.key ? "bg-primary/10 border-primary" : "hover:bg-muted/60"}`}>
            <div className="font-medium">{r.title}</div>
            <div className="text-xs text-muted-foreground">{r.category}</div>
          </button>
        ))}
      </div>
      <div>
        {!selected ? (
          <div className="rounded-xl border bg-muted/40 p-6 text-center text-sm text-muted-foreground">Select a report to preview.</div>
        ) : (
          <Card data-testid="report-preview">
            <CardHeader>
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div>
                  <CardTitle className="text-base">{report?.title}</CardTitle>
                  <div className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-2">
                    <span>Data source: <b>{report?.data_source}</b></span>
                    <span>Date basis: <b>{report?.date_basis}</b></span>
                    <Badge variant="outline" className="text-[10px]">{basisLabel(report?.calc_basis)}</Badge>
                  </div>
                </div>
                <div className="flex items-end gap-2">
                  <div className="grid gap-1"><Label className="text-xs">From</Label><Input type="date" value={dateRange.from} onChange={(e) => setDateRange({ ...dateRange, from: e.target.value })} data-testid="report-from" /></div>
                  <div className="grid gap-1"><Label className="text-xs">To</Label><Input type="date" value={dateRange.to} onChange={(e) => setDateRange({ ...dateRange, to: e.target.value })} data-testid="report-to" /></div>
                  <Button
                    variant="outline"
                    onClick={() => downloadCsv(`/reports/${selected}/export.csv`, { filters: { date_from: dateRange.from || undefined, date_to: dateRange.to || undefined } }, `${selected.replace(/\./g, "_")}.csv`)}
                    data-testid="report-export-csv"
                  ><Download className="size-4 mr-1" />CSV</Button>
                </div>
              </div>
              {report?.limitations?.length > 0 && (
                <div className="text-[11px] text-muted-foreground mt-2 space-y-0.5">{report.limitations.map((l, i) => <div key={i}>• {l}</div>)}</div>
              )}
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border overflow-x-auto max-h-[520px] overflow-y-auto">
                <Table>
                  <TableHeader><TableRow>{(report?.columns || []).map((c) => <TableHead key={c.key} className={c.money ? "text-right" : ""}>{c.label}</TableHead>)}</TableRow></TableHeader>
                  <TableBody>
                    {preview.isLoading ? <TableRow><TableCell colSpan={report?.columns?.length || 1} className="text-center text-sm text-muted-foreground py-6">Loading…</TableCell></TableRow>
                    : (preview.data?.rows || []).length === 0 ? <TableRow><TableCell colSpan={report?.columns?.length || 1} className="text-center text-sm text-muted-foreground py-6">Empty result for these filters.</TableCell></TableRow>
                    : preview.data.rows.map((row, i) => (
                      <TableRow key={i}>{report.columns.map((c) => <TableCell key={c.key} className={c.money ? "text-right" : ""}>{formatCell(c, row[c.key])}</TableCell>)}</TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              {preview.data?.truncated && <div className="text-xs text-amber-700 mt-2">Preview truncated to {preview.data.preview_limit} rows — export CSV for the full result set (capped at 25 000).</div>}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function CustomTab() {
  const list = useQuery({ queryKey: ["reports-list"], queryFn: async () => (await api.get("/reports")).data });
  const datasets = list.data?.custom_datasets || [];
  const [datasetKey, setDatasetKey] = useState("");
  const dataset = datasets.find((d) => d.key === datasetKey);
  const [selectedFields, setSelectedFields] = useState([]);
  const [dateRange, setDateRange] = useState({ from: "", to: "" });
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  function toggle(f) {
    setSelectedFields((prev) => prev.includes(f) ? prev.filter((x) => x !== f) : [...prev, f]);
  }
  async function runPreview() {
    if (!datasetKey || selectedFields.length === 0) { toast.error("Choose a dataset and at least one field"); return; }
    setBusy(true);
    try {
      const res = await api.post("/reports/custom/preview", {
        dataset: datasetKey, fields: selectedFields,
        filters: { date_from: dateRange.from || undefined, date_to: dateRange.to || undefined },
        limit: 200,
      });
      setPreview(res.data);
    } catch (err) { toast.error(extractError(err)); }
    finally { setBusy(false); }
  }
  return (
    <div className="space-y-3" data-testid="reports-custom-panel">
      <div className="grid md:grid-cols-3 gap-3 items-end">
        <div className="grid gap-1"><Label>Dataset</Label>
          <Select value={datasetKey} onValueChange={(v) => { setDatasetKey(v); setSelectedFields([]); setPreview(null); }}>
            <SelectTrigger data-testid="custom-dataset-select"><SelectValue placeholder="Pick dataset" /></SelectTrigger>
            <SelectContent>{datasets.map((d) => <SelectItem key={d.key} value={d.key}>{d.key}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid gap-1"><Label className="text-xs">From</Label><Input type="date" value={dateRange.from} onChange={(e) => setDateRange({ ...dateRange, from: e.target.value })} data-testid="custom-from" /></div>
        <div className="grid gap-1"><Label className="text-xs">To</Label><Input type="date" value={dateRange.to} onChange={(e) => setDateRange({ ...dateRange, to: e.target.value })} data-testid="custom-to" /></div>
      </div>
      {dataset && (
        <div className="grid gap-2">
          <Label className="text-xs">Fields (whitelist — only approved fields are exportable)</Label>
          <div className="flex flex-wrap gap-1">
            {dataset.fields.map((f) => (
              <button key={f} onClick={() => toggle(f)} data-testid={`custom-field-${f}`}
                className={`px-2 py-1 text-xs rounded-md border ${selectedFields.includes(f) ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted/60"}`}>{f}</button>
            ))}
          </div>
        </div>
      )}
      <div className="flex gap-2">
        <Button onClick={runPreview} disabled={busy || !datasetKey} data-testid="custom-run-preview">{busy ? "Running…" : "Run preview"}</Button>
        <Button variant="outline" disabled={!datasetKey || selectedFields.length === 0}
          onClick={() => downloadCsv("/reports/custom/export.csv", { dataset: datasetKey, fields: selectedFields, filters: { date_from: dateRange.from || undefined, date_to: dateRange.to || undefined }, limit: 25000 }, `custom_${datasetKey}.csv`)}
          data-testid="custom-export-csv"><Download className="size-4 mr-1" />CSV</Button>
      </div>
      {preview && (
        <div className="rounded-xl border overflow-x-auto max-h-[400px] overflow-y-auto" data-testid="custom-preview-table">
          <Table>
            <TableHeader><TableRow>{selectedFields.map((f) => <TableHead key={f} className={f.endsWith("_cents") ? "text-right" : ""}>{f}</TableHead>)}</TableRow></TableHeader>
            <TableBody>
              {preview.rows.length === 0 ? <TableRow><TableCell colSpan={selectedFields.length || 1} className="text-center text-sm text-muted-foreground py-6">Empty result.</TableCell></TableRow>
              : preview.rows.map((row, i) => (
                <TableRow key={i}>{selectedFields.map((f) => (<TableCell key={f} className={f.endsWith("_cents") ? "text-right" : ""}>{f.endsWith("_cents") ? money(row[f]) : (row[f] ?? "—")}</TableCell>))}</TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <p className="text-xs text-muted-foreground">Custom Report Builder is intentionally restricted to approved datasets, fields, filters, sort, and grouping. No raw queries, no cross-tenant reads, no hidden fields, no unbounded exports.</p>
    </div>
  );
}

export default function ReportsPage() {
  return (
    <div className="space-y-4" data-testid="reports-page">
      <PageHeader title="Reports & Analytics" subtitle="Curated reports with declared data source, date basis, and calculation basis. Custom builder is restricted to approved datasets and fields." />
      <Tabs defaultValue="curated">
        <TabsList data-testid="reports-tabs">
          <TabsTrigger value="curated" data-testid="tab-curated">Curated reports</TabsTrigger>
          <TabsTrigger value="custom" data-testid="tab-custom">Custom builder</TabsTrigger>
        </TabsList>
        <TabsContent value="curated" className="mt-4"><CuratedTab /></TabsContent>
        <TabsContent value="custom" className="mt-4"><CustomTab /></TabsContent>
      </Tabs>
    </div>
  );
}
