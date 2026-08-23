import { FileUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import WebstoreBrandingEditor from "@/components/webstores/WebstoreBranding";

export function SetupFilesCard({
  files,
  fileCategory,
  setupFile,
  onFileCategoryChange,
  onSetupFileChange,
  onUpload,
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Setup Files</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-2">
          <input
            className="border rounded px-3 py-2 text-sm"
            value={fileCategory}
            onChange={(e) => onFileCategoryChange(e.target.value)}
            data-testid="portal-webstore-file-category"
          />
          <input
            className="border rounded px-3 py-2 text-sm"
            type="file"
            onChange={(e) => onSetupFileChange(e.target.files?.[0] || null)}
            data-testid="portal-webstore-file"
          />
          <Button disabled={!setupFile} onClick={onUpload}>
            <FileUp className="size-4 mr-2" />
            Upload
          </Button>
        </div>
        <div className="rounded border divide-y">
          {files.map((file) => (
            <div
              key={file.id}
              className="p-3 flex items-center justify-between gap-3 text-sm"
            >
              <span>{file.file_name}</span>
              <span className="text-muted-foreground">
                {file.category} -{" "}
                {file.private_download_only ? "download only" : "preview safe"}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function BrandingCard({ webstoreId, products }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Branding</CardTitle>
      </CardHeader>
      <CardContent>
        <WebstoreBrandingEditor
          webstoreId={webstoreId}
          portal
          products={products}
        />
      </CardContent>
    </Card>
  );
}
