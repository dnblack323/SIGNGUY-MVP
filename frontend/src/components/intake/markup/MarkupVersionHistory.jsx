import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { CheckCircle2, History } from "lucide-react";

/**
 * EC10 Phase 10C §12/§16 — read-only version history list. Selecting a
 * version loads it (read-only) via `onView`; only the current version can
 * be built upon by saving a new version from the toolbar.
 */
export default function MarkupVersionHistory({ markupId, currentVersionId, onView }) {
  const { data } = useQuery({
    queryKey: ["markup-versions", markupId],
    queryFn: async () => (await api.get(`/markup/${markupId}/versions`)).data,
    enabled: !!markupId,
  });
  const versions = data?.items || [];

  return (
    <div className="grid gap-1.5 rounded-lg border bg-card p-2 max-h-56 overflow-auto" data-testid="markup-version-history">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground px-1">
        <History className="size-3.5" /> Version history
      </div>
      {versions.length === 0 && <div className="text-xs text-muted-foreground px-1">No versions saved yet.</div>}
      {versions.map((v) => (
        <button
          key={v.id} type="button" onClick={() => onView?.(v)}
          className="flex items-center justify-between text-left text-xs rounded px-2 py-1 hover:bg-muted"
          data-testid={`markup-version-row-${v.version_number}`}
        >
          <span className="flex items-center gap-1.5">
            {v.id === currentVersionId && <CheckCircle2 className="size-3.5 text-emerald-600" />}
            v{v.version_number}{v.change_summary ? ` · ${v.change_summary}` : ""}
          </span>
          <span className="text-muted-foreground">{relativeTime(v.created_at)}</span>
        </button>
      ))}
    </div>
  );
}
