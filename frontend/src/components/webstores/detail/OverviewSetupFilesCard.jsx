import { FileUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function OverviewSetupFilesCard({ model }) {
  const {
    fileCategory,
    id,
    setFileCategory,
    setSetupFile,
    setupFile,
    setupFiles,
    uploadSetupFileMutation,
  } = model;

return (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Setup Files</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
                    <Input
                      value={fileCategory}
                      onChange={(e) => setFileCategory(e.target.value)}
                      data-testid="webstore-file-category"
                    />
                    <Input
                      type="file"
                      onChange={(e) =>
                        setSetupFile(e.target.files?.[0] || null)
                      }
                      data-testid="webstore-setup-file"
                    />
                    <Button
                      disabled={!setupFile || uploadSetupFileMutation.isPending}
                      onClick={() => uploadSetupFileMutation.mutate()}
                      data-testid="webstore-upload-file"
                    >
                      <FileUp className="size-4" />
                    </Button>
                  </div>
                  <div className="rounded border divide-y">
                    {(setupFiles.data || []).map((f) => (
                      <div
                        key={f.id}
                        className="p-2 flex items-center justify-between gap-2"
                      >
                        <span>{f.file_name}</span>
                        <span className="text-xs text-muted-foreground">
                          {f.category} - v{f.version} -{" "}
                          {f.private_download_only
                            ? "download only"
                            : "preview safe"}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
  );
}
