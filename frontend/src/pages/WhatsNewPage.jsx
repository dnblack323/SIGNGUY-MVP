import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BookOpen } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import EmptyState from "@/components/common/EmptyState";
import MarkdownContent from "@/components/help/MarkdownContent";
import useHelpCatalog from "@/components/help/useHelpCatalog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/auth/AuthContext";
import { helpDocsPath, listHelpArticles } from "@/lib/help";

export default function WhatsNewPage() {
  const { hasPerm } = useAuth();
  const canRead = hasPerm("help:read");
  const catalog = useHelpCatalog(canRead);
  const releases = useQuery({ queryKey: ["help", "releases"], queryFn: () => listHelpArticles({ category: "release_notes", include_body: true }), enabled: canRead });

  if (!canRead) {
    return (
      <div className="space-y-4" data-testid="whats-new-page">
        <PageHeader title="What's New" subtitle="Release history is available to internal shop users." />
        <Alert><BookOpen className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account cannot read Help Center articles.</AlertDescription></Alert>
      </div>
    );
  }

  const items = [...(releases.data?.items || [])].sort((a, b) => (b.release_date || "").localeCompare(a.release_date || ""));

  return (
    <div className="space-y-6" data-testid="whats-new-page">
      <PageHeader title="What's New" subtitle="Changes that have shipped. A release identifier is the date the changes were released." />
      {releases.isLoading ? <Skeleton className="h-48 w-full" /> : !items.length ? (
        <EmptyState icon={BookOpen} title="No releases yet" description="Shipped changes will be listed here." />
      ) : (
        <ol className="max-w-3xl space-y-8">
          {items.map((release) => {
            const related = (release.related || []).map((slug) => catalog.byName.get(slug)).filter(Boolean);
            return (
              <li key={release.slug} className="space-y-2 border-l-2 pl-4" data-testid={`release-${release.release}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">Release {release.release}</Badge>
                  <time className="text-xs text-muted-foreground" dateTime={release.release_date}>{release.release_date}</time>
                </div>
                <h2 className="text-base font-semibold">{release.title}</h2>
                <p className="text-sm text-muted-foreground">{release.summary}</p>
                <MarkdownContent markdown={release.body} />
                {related.length > 0 && (
                  <p className="text-sm">Learn more: {related.map((a, i) => (
                    <span key={a.slug}>{i > 0 && ", "}<Link to={helpDocsPath(a.slug)} className="text-primary underline">{a.title}</Link></span>
                  ))}</p>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
