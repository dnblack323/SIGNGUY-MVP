import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  Download,
  FileSpreadsheet,
  FileText,
  Play,
  Printer,
  Save,
  Search,
} from "lucide-react";
import api, { extractError, API } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { basisLabel, money } from "@/lib/ec7";

const CATALOG_TABS = [
  ["overview", "Overview"],
  ["financial", "Financial"],
  ["operations", "Operations"],
  ["customers_sales", "Customers & Sales"],
  ["webstores", "Webstores"],
  ["materials_purchasing", "Materials & Purchasing"],
  ["team_labor", "Team & Labor"],
  ["wrap_lab", "Wrap Lab"],
  ["custom", "Custom Builder"],
  ["saved", "Saved"],
  ["scheduled", "Scheduled"],
  ["exports", "Exports"],
];

const FORMAT_OPTIONS = [
  ["csv", "CSV", Download],
  ["xlsx", "XLSX", FileSpreadsheet],
  ["pdf", "PDF", FileText],
  ["print", "Print", Printer],
];

function buildFilters(range, extra = {}) {
  return {
    ...extra,
    date_from: range.from || undefined,
    date_to: range.to || undefined,
  };
}

async function downloadExport(path, body) {
  const token = localStorage.getItem("signguy.token");
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: "include",
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    throw new Error(`Export failed (${res.status})`);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] || "report";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function formatCell(col, val) {
  if (val === null || val === undefined || val === "") return "-";
  if (col.money) return money(val);
  if (col.date) return String(val).slice(0, 10);
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (Array.isArray(val)) return `${val.length} link${val.length === 1 ? "" : "s"}`;
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

function ResultTable({ result }) {
  const columns = result?.columns || (result?.fields || []).map((field) => ({ key: field, label: field, money: field.endsWith("_cents") }));
  const rows = result?.rows || [];
  return (
    <div className="rounded-lg border overflow-auto max-h-[520px]" data-testid="report-result-table">
      <Table>
        <TableHeader>
          <TableRow>{columns.map((col) => <TableHead key={col.key} className={col.money ? "text-right" : ""}>{col.label}</TableHead>)}</TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow><TableCell colSpan={columns.length || 1} className="py-8 text-center text-sm text-muted-foreground">No rows for this report and filter set.</TableCell></TableRow>
          ) : rows.map((row, index) => (
            <TableRow key={index}>
              {columns.map((col) => <TableCell key={col.key} className={col.money ? "text-right" : ""}>{formatCell(col, row[col.key])}</TableCell>)}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ReportHeader({ report, result, onExport, onSave, busy }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle className="text-lg">{report?.title || result?.title || "Report"}</CardTitle>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
            <Badge variant="outline">{report?.category || result?.category || result?.dataset}</Badge>
            <span>Source: <b>{report?.data_source || result?.data_source || result?.dataset}</b></span>
            <span>Date basis: <b>{report?.date_basis || result?.date_basis || "dataset"}</b></span>
            <Badge variant="secondary">{basisLabel(report?.calc_basis || result?.calc_basis || "stored_values")}</Badge>
            {result && <span>{result.row_count ?? 0} rows</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={onSave} disabled={!result || busy} data-testid="report-save">
            <Save className="mr-1 size-4" />Save
          </Button>
          {FORMAT_OPTIONS.map(([format, label, Icon]) => (
            <Button key={format} type="button" variant="outline" size="sm" onClick={() => onExport(format)} disabled={!result || busy} data-testid={`report-export-${format}`}>
              <Icon className="mr-1 size-4" />{label}
            </Button>
          ))}
        </div>
      </div>
      {(report?.limitations || result?.limitations || []).length > 0 && (
        <div className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
          {(report?.limitations || result?.limitations || []).map((item, index) => <div key={index}>{item}</div>)}
        </div>
      )}
    </div>
  );
}

function StandardCatalog({ categoryKey, reports, catalog, refreshExports }) {
  const queryClient = useQueryClient();
  const [selectedKey, setSelectedKey] = useState(reports[0]?.key || "");
  const [range, setRange] = useState({ from: "", to: "" });
  const [mode, setMode] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const report = reports.find((item) => item.key === selectedKey) || reports[0];

  async function run() {
    if (!report) return;
    setBusy(true);
    try {
      const response = await api.post(`/reports/${report.key}/run`, {
        filters: buildFilters(range, mode ? { mode } : {}),
        preview_limit: 500,
      });
      setResult(response.data);
    } catch (error) {
      toast.error(extractError(error));
    } finally {
      setBusy(false);
    }
  }

  async function saveCurrent() {
    if (!report) return;
    try {
      await api.post("/reports/saved", {
        name: report.title,
        source_kind: "standard",
        standard_report_key: report.key,
        filters: buildFilters(range, mode ? { mode } : {}),
      });
      queryClient.invalidateQueries({ queryKey: ["reports-saved"] });
      toast.success("Report saved");
    } catch (error) {
      toast.error(extractError(error));
    }
  }

  async function exportCurrent(format) {
    if (!report) return;
    try {
      await downloadExport(`/reports/${report.key}/export/${format}`, { filters: buildFilters(range, mode ? { mode } : {}) });
      refreshExports();
    } catch (error) {
      toast.error(error.message);
    }
  }

  if (!reports.length) {
    return <div className="rounded-lg border bg-muted/30 p-6 text-sm text-muted-foreground">No authorized reports in this category.</div>;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]" data-testid={`reports-category-${categoryKey}`}>
      <div className="space-y-2">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <Input className="pl-9" placeholder="Search reports" aria-label="Search reports" />
        </div>
        {reports.map((item) => (
          <button
            type="button"
            key={item.key}
            onClick={() => { setSelectedKey(item.key); setResult(null); }}
            className={`w-full rounded-md border px-3 py-2 text-left text-sm ${report?.key === item.key ? "border-primary bg-primary/10" : "hover:bg-muted/60"}`}
            data-testid={`report-item-${item.key}`}
          >
            <div className="font-medium">{item.title}</div>
            <div className="text-xs text-muted-foreground">{item.data_source}</div>
          </button>
        ))}
      </div>
      <Card>
        <CardHeader>
          <ReportHeader report={report} result={result} onExport={exportCurrent} onSave={saveCurrent} busy={busy} />
          <div className="grid gap-2 md:grid-cols-[1fr_1fr_1fr_auto] md:items-end">
            <div className="grid gap-1"><Label className="text-xs">From</Label><Input type="date" value={range.from} onChange={(event) => { setRange({ ...range, from: event.target.value }); setResult(null); }} /></div>
            <div className="grid gap-1"><Label className="text-xs">To</Label><Input type="date" value={range.to} onChange={(event) => { setRange({ ...range, to: event.target.value }); setResult(null); }} /></div>
            <div className="grid gap-1">
              <Label className="text-xs">Mode</Label>
              <Select value={mode || "default"} onValueChange={(value) => { setMode(value === "default" ? "" : value); setResult(null); }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">Default</SelectItem>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="due_soon">Due soon</SelectItem>
                  <SelectItem value="late">Late</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button type="button" onClick={run} disabled={busy} data-testid="report-run"><Play className="mr-1 size-4" />{busy ? "Running" : "Run"}</Button>
          </div>
        </CardHeader>
        <CardContent>
          {busy ? (
            <div className="rounded-lg border bg-muted/30 p-8 text-center text-sm text-muted-foreground">Running report...</div>
          ) : result ? <ResultTable result={result} /> : (
            <div className="rounded-lg border bg-muted/30 p-8 text-center text-sm text-muted-foreground">Run the selected report to preview current source data.</div>
          )}
          {catalog?.blocked_requirements?.length > 0 && categoryKey === "overview" && (
            <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
              <div className="font-semibold">Blocked or deferred requirements</div>
              {catalog.blocked_requirements.map((item) => <div key={item.id}>{item.name}: {item.reason}</div>)}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function CustomBuilder({ catalog, refreshExports }) {
  const queryClient = useQueryClient();
  const datasets = useMemo(() => catalog?.custom_datasets || [], [catalog?.custom_datasets]);
  const [datasetKey, setDatasetKey] = useState("");
  const dataset = datasets.find((item) => item.key === datasetKey);
  const [fields, setFields] = useState([]);
  const [groupBy, setGroupBy] = useState([]);
  const [sortField, setSortField] = useState("");
  const [range, setRange] = useState({ from: "", to: "" });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!datasetKey && datasets.length > 0) {
      setDatasetKey(datasets[0].key);
    }
  }, [datasetKey, datasets]);

  function toggle(list, setter, value) {
    setter(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
    setResult(null);
  }

  function payload(limit = 500) {
    return {
      dataset: datasetKey,
      fields,
      filters: buildFilters(range),
      group_by: groupBy,
      sort: sortField ? [{ field: sortField, dir: "asc" }] : [],
      limit,
    };
  }

  async function run() {
    if (!datasetKey || fields.length === 0) {
      toast.error("Choose a dataset and at least one field");
      return;
    }
    setBusy(true);
    try {
      const response = await api.post("/reports/custom/preview", payload(500));
      setResult(response.data);
    } catch (error) {
      toast.error(extractError(error));
    } finally {
      setBusy(false);
    }
  }

  async function saveCurrent() {
    if (!result) return;
    try {
      await api.post("/reports/saved", {
        name: `Custom ${datasetKey}`,
        source_kind: "custom",
        custom_dataset: datasetKey,
        fields,
        filters: buildFilters(range),
        group_by: groupBy,
        sort: sortField ? [{ field: sortField, dir: "asc" }] : [],
      });
      queryClient.invalidateQueries({ queryKey: ["reports-saved"] });
      toast.success("Custom report saved");
    } catch (error) {
      toast.error(extractError(error));
    }
  }

  async function exportCurrent(format) {
    try {
      await downloadExport(`/reports/custom/export/${format}`, payload(25000));
      refreshExports();
    } catch (error) {
      toast.error(error.message);
    }
  }

  return (
    <div className="space-y-4" data-testid="reports-custom-panel">
      <Card>
        <CardHeader>
          <ReportHeader report={{ title: "Custom Report Builder", category: "custom", data_source: datasetKey || "approved datasets", date_basis: dataset?.date_field, calc_basis: "stored_source_values", limitations: ["Approved datasets, fields, filters, grouping, and sorting only."] }} result={result} onExport={exportCurrent} onSave={saveCurrent} busy={busy} />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4 md:items-end">
            <div className="grid gap-1 md:col-span-2">
              <Label>Dataset</Label>
              <Select value={datasetKey} onValueChange={(value) => { setDatasetKey(value); setFields([]); setGroupBy([]); setSortField(""); setResult(null); }}>
                <SelectTrigger data-testid="custom-dataset-select"><SelectValue placeholder="Pick approved source" /></SelectTrigger>
                <SelectContent>{datasets.map((item) => <SelectItem key={item.key} value={item.key}>{item.key}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1"><Label className="text-xs">From</Label><Input type="date" value={range.from} onChange={(event) => { setRange({ ...range, from: event.target.value }); setResult(null); }} /></div>
            <div className="grid gap-1"><Label className="text-xs">To</Label><Input type="date" value={range.to} onChange={(event) => { setRange({ ...range, to: event.target.value }); setResult(null); }} /></div>
          </div>
          {dataset && (
            <div className="grid gap-4 xl:grid-cols-3">
              <div>
                <Label className="text-xs">Fields</Label>
                <div className="mt-2 flex flex-wrap gap-1">
                  {dataset.fields.map((field) => <Button key={field} type="button" size="sm" variant={fields.includes(field) ? "default" : "outline"} onClick={() => toggle(fields, setFields, field)} data-testid={`custom-field-${field}`}>{field}</Button>)}
                </div>
              </div>
              <div>
                <Label className="text-xs">Group by</Label>
                <div className="mt-2 flex flex-wrap gap-1">
                  {dataset.group_by.map((field) => <Button key={field} type="button" size="sm" variant={groupBy.includes(field) ? "default" : "outline"} onClick={() => toggle(groupBy, setGroupBy, field)} data-testid={`custom-group-${field}`}>{field}</Button>)}
                </div>
              </div>
              <div className="grid gap-1 content-start">
                <Label className="text-xs">Sort</Label>
                <Select value={sortField || "none"} onValueChange={(value) => { setSortField(value === "none" ? "" : value); setResult(null); }}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {dataset.sort.map((field) => <SelectItem key={field} value={field}>{field}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
          <Button type="button" onClick={run} disabled={busy || !datasetKey} data-testid="custom-run-preview"><Play className="mr-1 size-4" />{busy ? "Running" : "Run custom report"}</Button>
          {result && <ResultTable result={result} />}
        </CardContent>
      </Card>
    </div>
  );
}

function SavedReports({ refreshExports }) {
  const queryClient = useQueryClient();
  const saved = useQuery({ queryKey: ["reports-saved"], queryFn: async () => (await api.get("/reports/saved")).data });
  const [activeResult, setActiveResult] = useState(null);

  async function runSaved(id) {
    try {
      const response = await api.post(`/reports/saved/${id}/run`, { filters: {}, preview_limit: 500 });
      setActiveResult(response.data);
    } catch (error) {
      toast.error(extractError(error));
    }
  }

  async function duplicate(id) {
    try {
      await api.post(`/reports/saved/${id}/duplicate`);
      queryClient.invalidateQueries({ queryKey: ["reports-saved"] });
    } catch (error) {
      toast.error(extractError(error));
    }
  }

  async function archive(id) {
    try {
      await api.post(`/reports/saved/${id}/archive`);
      queryClient.invalidateQueries({ queryKey: ["reports-saved"] });
    } catch (error) {
      toast.error(extractError(error));
    }
  }

  async function exportSaved(id, format) {
    try {
      await downloadExport(`/reports/saved/${id}/export/${format}`, { filters: {} });
      refreshExports();
    } catch (error) {
      toast.error(error.message);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]" data-testid="reports-saved-panel">
      <div className="space-y-2">
        {(saved.data?.saved_reports || []).map((item) => (
          <Card key={item.id} className={item.status === "archived" ? "opacity-60" : ""}>
            <CardContent className="space-y-2 p-3">
              <div className="font-medium">{item.name}</div>
              <div className="text-xs text-muted-foreground">{item.source_kind} {item.standard_report_key || item.custom_dataset}</div>
              <div className="flex flex-wrap gap-1">
                <Button size="sm" variant="outline" onClick={() => runSaved(item.id)} disabled={item.status === "archived"}>Run</Button>
                <Button size="sm" variant="outline" onClick={() => exportSaved(item.id, "csv")} disabled={item.status === "archived"}>CSV</Button>
                <Button size="sm" variant="outline" onClick={() => duplicate(item.id)}>Duplicate</Button>
                <Button size="sm" variant="outline" onClick={() => archive(item.id)} disabled={item.status === "archived"}>Archive</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader><CardTitle className="text-lg">Saved report result</CardTitle></CardHeader>
        <CardContent>{activeResult ? <ResultTable result={activeResult} /> : <div className="rounded-lg border bg-muted/30 p-8 text-sm text-muted-foreground">Run a saved report to see a fresh authorized result.</div>}</CardContent>
      </Card>
    </div>
  );
}

function Schedules() {
  const queryClient = useQueryClient();
  const saved = useQuery({ queryKey: ["reports-saved"], queryFn: async () => (await api.get("/reports/saved")).data });
  const schedules = useQuery({ queryKey: ["reports-schedules"], queryFn: async () => (await api.get("/reports/schedules")).data });
  const [reportDefinitionId, setReportDefinitionId] = useState("");
  const [cadence, setCadence] = useState("weekly");

  async function createSchedule() {
    if (!reportDefinitionId) {
      toast.error("Choose a saved report first");
      return;
    }
    try {
      await api.post("/reports/schedules", { report_definition_id: reportDefinitionId, cadence, delivery_formats: ["csv"] });
      queryClient.invalidateQueries({ queryKey: ["reports-schedules"] });
    } catch (error) {
      toast.error(extractError(error));
    }
  }

  async function runSchedule(id) {
    try {
      await api.post(`/reports/schedules/${id}/run`);
      queryClient.invalidateQueries({ queryKey: ["reports-schedules"] });
      queryClient.invalidateQueries({ queryKey: ["reports-exports"] });
      toast.success("Schedule run recorded");
    } catch (error) {
      toast.error(extractError(error));
    }
  }

  return (
    <div className="space-y-4" data-testid="reports-scheduled-panel">
      <Card>
        <CardHeader><CardTitle className="text-lg">Create schedule</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1fr_220px_auto] md:items-end">
          <div className="grid gap-1">
            <Label>Saved report</Label>
            <Select value={reportDefinitionId} onValueChange={setReportDefinitionId}>
              <SelectTrigger><SelectValue placeholder="Choose saved report" /></SelectTrigger>
              <SelectContent>{(saved.data?.saved_reports || []).filter((item) => item.status === "active").map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1">
            <Label>Cadence</Label>
            <Select value={cadence} onValueChange={setCadence}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
                <SelectItem value="monthly">Monthly</SelectItem>
                <SelectItem value="pay_period">Pay period</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button type="button" onClick={createSchedule}><CalendarClock className="mr-1 size-4" />Create</Button>
        </CardContent>
      </Card>
      <div className="grid gap-2">
        {(schedules.data?.schedules || []).map((schedule) => (
          <Card key={schedule.id}>
            <CardContent className="flex flex-wrap items-center justify-between gap-2 p-3">
              <div>
                <div className="font-medium">{schedule.cadence}</div>
                <div className="text-xs text-muted-foreground">{schedule.report_definition_id}</div>
              </div>
              <Button size="sm" variant="outline" onClick={() => runSchedule(schedule.id)}>Run now</Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ExportHistory() {
  const exports = useQuery({ queryKey: ["reports-exports"], queryFn: async () => (await api.get("/reports/exports/history")).data });
  return (
    <Card data-testid="reports-exports-panel">
      <CardHeader><CardTitle className="text-lg">Export history</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader><TableRow><TableHead>Format</TableHead><TableHead>Report</TableHead><TableHead>Rows</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead></TableRow></TableHeader>
          <TableBody>
            {(exports.data?.exports || []).map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.export_format}</TableCell>
                <TableCell>{item.standard_report_key || item.custom_dataset || item.report_definition_id}</TableCell>
                <TableCell>{item.row_count}</TableCell>
                <TableCell>{item.status}</TableCell>
                <TableCell>{String(item.created_at || "").slice(0, 19)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export default function ReportsPage() {
  const queryClient = useQueryClient();
  const catalog = useQuery({ queryKey: ["reports-list"], queryFn: async () => (await api.get("/reports")).data });
  const [activeTab, setActiveTab] = useState("overview");
  const reportsByCategory = useMemo(() => {
    const grouped = {};
    for (const report of catalog.data?.reports || []) {
      const category = report.category === "finance" || report.category === "tax" || report.category === "expenses" || report.category === "payroll" ? "financial" : report.category;
      const normalized = category === "inventory" || category === "purchasing" ? "materials_purchasing" : category;
      grouped[normalized] = [...(grouped[normalized] || []), report];
    }
    return grouped;
  }, [catalog.data?.reports]);
  const refreshExports = () => queryClient.invalidateQueries({ queryKey: ["reports-exports"] });

  return (
    <div className="space-y-4" data-testid="reports-page">
      <PageHeader
        title="Reports"
        subtitle="Business & Finance reports, custom builder, saved reports, scheduled runs, and approved exports."
      />
      {catalog.data?.authority && (
        <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
          Authority: {catalog.data.authority.title} ({catalog.data.authority.pages} pages). Location: {catalog.data.authority.location}. Webstore types: {(catalog.data.official_webstore_types || []).join(", ")}.
        </div>
      )}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="flex h-auto flex-wrap justify-start" data-testid="reports-tabs">
          {CATALOG_TABS.map(([value, label]) => <TabsTrigger key={value} value={value} data-testid={`tab-${value}`}>{label}</TabsTrigger>)}
        </TabsList>
        {CATALOG_TABS.filter(([value]) => !["custom", "saved", "scheduled", "exports"].includes(value)).map(([value]) => (
          <TabsContent key={value} value={value} className="mt-4">
            <StandardCatalog categoryKey={value} reports={reportsByCategory[value] || []} catalog={catalog.data} refreshExports={refreshExports} />
          </TabsContent>
        ))}
        <TabsContent value="custom" className="mt-4"><CustomBuilder catalog={catalog.data} refreshExports={refreshExports} /></TabsContent>
        <TabsContent value="saved" className="mt-4"><SavedReports refreshExports={refreshExports} /></TabsContent>
        <TabsContent value="scheduled" className="mt-4"><Schedules /></TabsContent>
        <TabsContent value="exports" className="mt-4"><ExportHistory /></TabsContent>
      </Tabs>
    </div>
  );
}
