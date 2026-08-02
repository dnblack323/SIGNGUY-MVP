import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { extractError, API } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
import TableSkeleton from "@/components/common/LoadingSkeleton";
import EmptyState from "@/components/common/EmptyState";
import {
  UploadCloud,
  Download,
  Trash2,
  Folder,
  Search,
  FileQuestion,
} from "lucide-react";
import { toast } from "sonner";
import { relativeTime } from "@/lib/format";
import { useAuth } from "@/auth/AuthContext";

function bytesToHuman(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentsPage() {
  const qc = useQueryClient();
  const { hasPerm } = useAuth();
  const canWrite = hasPerm("document:write");
  const [uploading, setUploading] = useState(false);
  const [visibility, setVisibility] = useState("internal");
  const [search, setSearch] = useState("");
  const fileRef = useRef(null);

  const { data, isLoading } = useQuery({
    queryKey: ["files"],
    queryFn: async () =>
      (await api.get("/files", { params: { limit: 200 } })).data,
  });
  const items = (data?.items || []).filter(
    (f) =>
      !search ||
      f.original_filename.toLowerCase().includes(search.toLowerCase()),
  );

  async function onDrop(e) {
    e.preventDefault();
    const files = e.dataTransfer?.files || fileRef.current?.files;
    if (!files || files.length === 0) return;
    await uploadFiles(Array.from(files));
  }

  async function uploadFiles(files) {
    setUploading(true);
    for (const f of files) {
      const form = new FormData();
      form.append("file", f);
      form.append("visibility", visibility);
      try {
        await api.post("/files/upload", form, {
          headers: { "Content-Type": "multipart/form-data" },
        });
      } catch (err) {
        toast.error(`${f.name}: ${extractError(err)}`);
      }
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
    qc.invalidateQueries({ queryKey: ["files"] });
    toast.success("Upload complete");
  }

  async function toggleVis(f) {
    const nextVis =
      f.visibility === "internal" ? "customer_visible" : "internal";
    try {
      await api.patch(`/files/${f.id}/visibility`, { visibility: nextVis });
      qc.invalidateQueries({ queryKey: ["files"] });
    } catch (err) {
      toast.error(extractError(err));
    }
  }

  async function archive(f) {
    if (!confirm(`Archive ${f.original_filename}?`)) return;
    try {
      await api.delete(`/files/${f.id}`);
      qc.invalidateQueries({ queryKey: ["files"] });
    } catch (err) {
      toast.error(extractError(err));
    }
  }

  async function download(f) {
    try {
      const { data } = await api.get(`/files/${f.id}/download`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = f.original_filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      toast.error(extractError(err));
    }
  }

  return (
    <div className="space-y-4" data-testid="documents-page">
      <PageHeader
        title="Documents"
        subtitle="Shared file library. Private-by-default; every download is authenticated."
        actions={
          <Button
            asChild
            variant="outline"
            data-testid="documents-open-form-maker"
          >
            <Link to="/forms">
              <FileQuestion className="size-4 mr-2" />
              Form Maker
            </Link>
          </Button>
        }
      />

      {canWrite && (
        <div
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
          className="rounded-xl border border-dashed bg-muted/20 p-6 hover:bg-muted/30 transition-colors"
          data-testid="file-upload-dropzone"
        >
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 justify-between">
            <div className="flex items-center gap-3">
              <div className="grid size-10 place-items-center rounded-lg bg-background border">
                <UploadCloud className="size-4" />
              </div>
              <div>
                <div className="font-medium">
                  Drop files here or click to browse
                </div>
                <div className="text-xs text-muted-foreground">
                  Up to 25 MB. Images, PDFs, docs.
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-sm">
                <Switch
                  id="vis"
                  checked={visibility === "customer_visible"}
                  onCheckedChange={(v) =>
                    setVisibility(v ? "customer_visible" : "internal")
                  }
                  data-testid="upload-visibility-switch"
                />
                <label htmlFor="vis">Customer-visible</label>
              </div>
              <input
                ref={fileRef}
                type="file"
                multiple
                className="hidden"
                onChange={onDrop}
                data-testid="file-upload-input"
              />
              <Button
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
                data-testid="file-upload-browse-button"
              >
                {uploading ? "Uploading…" : "Browse files"}
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2">
        <div className="relative w-full max-w-md">
          <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search files…"
            className="pl-9"
          />
        </div>
      </div>

      {isLoading ? (
        <TableSkeleton />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Folder}
          title="No documents yet"
          description={
            canWrite
              ? "Upload your first file above."
              : "Nothing has been uploaded."
          }
        />
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Visibility</TableHead>
                <TableHead>Uploaded</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((f) => (
                <TableRow key={f.id} data-testid={`file-row-${f.id}`}>
                  <TableCell className="max-w-[320px] truncate font-medium">
                    {f.original_filename}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground mono">
                    {f.mime_type}
                  </TableCell>
                  <TableCell className="text-sm tabular-nums">
                    {bytesToHuman(f.size_bytes)}
                  </TableCell>
                  <TableCell>
                    {canWrite ? (
                      <button
                        onClick={() => toggleVis(f)}
                        className="text-xs underline"
                        data-testid={`file-toggle-vis-${f.id}`}
                      >
                        {f.visibility === "customer_visible"
                          ? "Customer"
                          : "Internal"}
                      </button>
                    ) : (
                      <span className="text-xs">
                        {f.visibility === "customer_visible"
                          ? "Customer"
                          : "Internal"}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {relativeTime(f.created_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => download(f)}
                      data-testid={`file-download-${f.id}`}
                    >
                      <Download className="size-4" />
                    </Button>
                    {canWrite && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => archive(f)}
                        data-testid={`file-archive-${f.id}`}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
