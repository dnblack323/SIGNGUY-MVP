import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, BookOpen, ExternalLink, Menu, Search, X } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/layout/PageHeader";
import EmptyState from "@/components/common/EmptyState";
import DocsNav from "@/components/help/DocsNav";
import MarkdownContent from "@/components/help/MarkdownContent";
import useHelpCatalog, { iconForCategory } from "@/components/help/useHelpCatalog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { getHelpArticle, helpDocsPath, listHelpArticles, sendHelpFeedback } from "@/lib/help";

function useDebounced(value, delay = 200) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function SearchResults({ query, results, isLoading }) {
  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (!results.length) {
    return (
      <EmptyState
        icon={Search}
        title={`No articles match "${query}"`}
        description="Try fewer or different words, or browse the categories. If you still cannot find it, contact support."
        action={<Button asChild variant="outline" size="sm"><Link to="/help/contact">Contact Support</Link></Button>}
      />
    );
  }
  return (
    <ul className="divide-y rounded-md border" data-testid="docs-search-results" aria-label="Search results">
      {results.map((article) => (
        <li key={article.slug}>
          <Link to={helpDocsPath(article.slug)} className="block p-3 hover:bg-muted/60" data-testid={`docs-result-${article.slug}`}>
            <div className="text-sm font-medium">{article.title}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">{article.snippet || article.summary}</div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function DocsHome({ groups, categoryKey }) {
  const visible = categoryKey ? groups.filter((g) => g.key === categoryKey) : groups;
  return (
    <div className="space-y-6" data-testid="docs-home">
      <div>
        <h2 className="text-lg font-semibold">{categoryKey && visible[0] ? visible[0].label : "Documentation"}</h2>
        <p className="text-sm text-muted-foreground">
          {categoryKey && visible[0] ? visible[0].description : "Guides for every area of SIGNGUY. Search, or choose a category on the left."}
        </p>
      </div>
      <div className="grid gap-x-8 gap-y-6 md:grid-cols-2">
        {visible.map((group) => {
          const Icon = iconForCategory(group.key);
          return (
            <section key={group.key} aria-labelledby={`docs-home-${group.key}`}>
              <h3 id={`docs-home-${group.key}`} className="mb-1 flex items-center gap-2 text-sm font-semibold">
                <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
                <Link to={helpDocsPath(null, { category: group.key })} className="hover:underline">{group.label}</Link>
              </h3>
              {!categoryKey && <p className="mb-1 text-xs text-muted-foreground">{group.description}</p>}
              <ul className="space-y-0.5 text-sm">
                {group.articles.map((article) => (
                  <li key={article.slug}>
                    <Link to={helpDocsPath(article.slug)} className="text-primary hover:underline">{article.title}</Link>
                    {categoryKey && <span className="block text-xs text-muted-foreground">{article.summary}</span>}
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function ArticleView({ article, catalog, user }) {
  const index = catalog.ordered.findIndex((a) => a.slug === article.slug);
  const previous = index > 0 ? catalog.ordered[index - 1] : null;
  const next = index >= 0 && index < catalog.ordered.length - 1 ? catalog.ordered[index + 1] : null;
  const related = (article.related || []).map((slug) => catalog.byName.get(slug)).filter(Boolean);
  const group = catalog.categories.find((c) => c.key === article.category);
  const [sent, setSent] = useState(null);
  useEffect(() => setSent(null), [article.slug]);
  const feedback = useMutation({
    mutationFn: (helpful) => sendHelpFeedback({ article_id: article.id, article_slug: article.slug, helpful, idempotency_key: `${user?.id}-${article.slug}-${helpful}` }),
    onSuccess: (_data, helpful) => { setSent(helpful); toast.success("Thanks for the feedback"); },
    onError: (err) => toast.error(extractError(err)),
  });
  const isRelease = article.category === "release_notes";

  return (
    <article className="space-y-4" data-testid="docs-article">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem><BreadcrumbLink asChild><Link to="/help">Help Center</Link></BreadcrumbLink></BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem><BreadcrumbLink asChild><Link to={isRelease ? "/help/whats-new" : "/help/docs"}>{isRelease ? "What's New" : "Documentation"}</Link></BreadcrumbLink></BreadcrumbItem>
          {group && !isRelease && (<><BreadcrumbSeparator /><BreadcrumbItem><BreadcrumbLink asChild><Link to={helpDocsPath(null, { category: group.key })}>{group.label}</Link></BreadcrumbLink></BreadcrumbItem></>)}
          <BreadcrumbSeparator />
          <BreadcrumbItem><BreadcrumbPage>{article.title}</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <header className="space-y-1">
        <h2 className="font-display text-2xl font-semibold tracking-tight" data-testid="docs-article-title">{article.title}</h2>
        {article.summary && <p className="text-sm text-muted-foreground">{article.summary}</p>}
      </header>

      <MarkdownContent markdown={article.body} />

      {(article.links || []).length > 0 && (
        <section aria-label="Open in the app" className="flex flex-wrap items-center gap-2 border-t pt-4">
          <span className="text-sm text-muted-foreground">Open in the app:</span>
          {article.links.map((link) => (
            <Button key={link.to} asChild variant="outline" size="sm"><Link to={link.to}><ExternalLink className="mr-1 size-3.5" aria-hidden="true" />{link.label}</Link></Button>
          ))}
        </section>
      )}

      {related.length > 0 && (
        <section aria-label="Related articles" className="border-t pt-4">
          <h3 className="mb-1 text-sm font-semibold">Related articles</h3>
          <ul className="space-y-0.5 text-sm">
            {related.map((item) => <li key={item.slug}><Link to={helpDocsPath(item.slug)} className="text-primary hover:underline">{item.title}</Link></li>)}
          </ul>
        </section>
      )}

      <section aria-label="Was this helpful" className="flex flex-wrap items-center gap-2 border-t pt-4">
        <span className="text-sm text-muted-foreground">{sent === null ? "Was this article helpful?" : "Thanks for letting us know."}</span>
        <Button variant="outline" size="sm" disabled={feedback.isPending || sent !== null} onClick={() => feedback.mutate(true)}>Helpful</Button>
        <Button variant="outline" size="sm" disabled={feedback.isPending || sent !== null} onClick={() => feedback.mutate(false)}>Needs work</Button>
        <Button asChild variant="link" size="sm"><Link to="/help/contact">Still need help?</Link></Button>
      </section>

      {!isRelease && (previous || next) && (
        <nav aria-label="Article navigation" className="grid gap-2 sm:grid-cols-2" data-testid="docs-prev-next">
          {previous ? (
            <Link to={helpDocsPath(previous.slug)} className="rounded-md border p-3 hover:bg-muted/60" data-testid="docs-prev">
              <span className="flex items-center gap-1 text-xs text-muted-foreground"><ArrowLeft className="size-3" aria-hidden="true" />Previous</span>
              <span className="text-sm font-medium">{previous.title}</span>
            </Link>
          ) : <span />}
          {next && (
            <Link to={helpDocsPath(next.slug)} className="rounded-md border p-3 text-right hover:bg-muted/60 sm:col-start-2" data-testid="docs-next">
              <span className="flex items-center justify-end gap-1 text-xs text-muted-foreground">Next<ArrowRight className="size-3" aria-hidden="true" /></span>
              <span className="text-sm font-medium">{next.title}</span>
            </Link>
          )}
        </nav>
      )}
    </article>
  );
}

export default function HelpDocsPage() {
  const { hasPerm, user } = useAuth();
  const canRead = hasPerm("help:read");
  const [params, setParams] = useSearchParams();
  const slug = params.get("article") || "";
  const categoryKey = params.get("category") || "";
  const q = params.get("q") || "";
  const [navOpen, setNavOpen] = useState(false);
  const [draft, setDraft] = useState(q);
  const search = useDebounced(draft.trim());
  const catalog = useHelpCatalog(canRead);

  const article = useQuery({ queryKey: ["help", "article", slug], queryFn: () => getHelpArticle(slug), enabled: canRead && !!slug, retry: false });
  const results = useQuery({
    queryKey: ["help", "search", q],
    queryFn: () => listHelpArticles({ q }),
    enabled: canRead && q.length >= 2,
  });

  // The URL is the source of truth for ?q= (so Back works). Typing updates it after a short pause, without
  // a history entry per keystroke; navigating elsewhere (a result, a nav link) clears the box.
  const written = useRef(q);
  useEffect(() => {
    if (search === written.current) return;
    written.current = search;
    const next = new URLSearchParams(params);
    if (search) { next.set("q", search); next.delete("article"); next.delete("category"); } else next.delete("q");
    setParams(next, { replace: true });
  }, [search]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (q !== written.current) { written.current = q; setDraft(q); }
  }, [q]);

  // An alias (older or onboarding-era link) resolves server-side; show the canonical address.
  useEffect(() => {
    if (article.data?.slug && slug && article.data.slug !== slug) setParams({ article: article.data.slug }, { replace: true });
  }, [article.data, slug, setParams]);

  const activeCategory = article.data?.category || categoryKey;
  const searching = q.length >= 2;
  const resultItems = useMemo(() => (results.data?.items || []).filter((a) => a.category !== "release_notes"), [results.data]);

  if (!canRead) {
    return (
      <div className="space-y-4" data-testid="help-docs-page">
        <PageHeader title="Documentation" subtitle="Documentation is available to internal shop users." />
        <Alert><BookOpen className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account cannot read Help Center articles.</AlertDescription></Alert>
      </div>
    );
  }

  let body;
  if (searching) body = <SearchResults query={q} results={resultItems} isLoading={results.isLoading || results.isFetching} />;
  else if (slug && article.isLoading) body = <Skeleton className="h-64 w-full" />;
  else if (slug && article.isError) {
    body = (
      <EmptyState
        icon={BookOpen}
        title="We could not find that article"
        description="The link may be out of date. Search the documentation or browse a category."
        action={<Button asChild variant="outline" size="sm"><Link to="/help/docs">Browse Documentation</Link></Button>}
      />
    );
  } else if (slug && article.data) body = <ArticleView article={article.data} catalog={catalog} user={user} />;
  else body = catalog.isLoading ? <Skeleton className="h-64 w-full" /> : <DocsHome groups={catalog.groups} categoryKey={categoryKey} />;

  return (
    <div className="space-y-4" data-testid="help-docs-page">
      <PageHeader
        title="Documentation"
        subtitle="How to use each part of SIGNGUY, step by step."
        actions={<Button asChild variant="outline" size="sm"><Link to="/help"><ArrowLeft className="mr-1 size-4" aria-hidden="true" />Back to Help Center</Link></Button>}
      />
      <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="space-y-3 lg:sticky lg:top-4 lg:max-h-[calc(100vh-6rem)] lg:self-start lg:overflow-y-auto" aria-label="Documentation navigation">
          <div className="relative">
            <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" aria-hidden="true" />
            <Input
              className="pl-8 pr-8"
              type="search"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setDraft("");
                if (e.key === "Enter" && resultItems[0]) { setParams({ article: resultItems[0].slug }); setDraft(""); }
              }}
              placeholder="Search documentation"
              aria-label="Search documentation"
              data-testid="docs-search-input"
            />
            {draft && (
              <button type="button" className="absolute right-2 top-2.5 text-muted-foreground" aria-label="Clear search" onClick={() => setDraft("")}><X className="size-4" /></button>
            )}
          </div>
          <Button variant="outline" size="sm" className="w-full lg:hidden" aria-expanded={navOpen} aria-controls="docs-nav-panel" onClick={() => setNavOpen((v) => !v)} data-testid="docs-nav-toggle">
            <Menu className="mr-1 size-4" aria-hidden="true" />{navOpen ? "Hide topics" : "Browse topics"}
          </Button>
          <div id="docs-nav-panel" className={navOpen ? "block" : "hidden lg:block"}>
            <DocsNav groups={catalog.groups} activeSlug={article.data?.slug} activeCategory={activeCategory} onNavigate={() => setNavOpen(false)} />
          </div>
        </aside>
        <main className="min-w-0" aria-live="polite">{body}</main>
      </div>
    </div>
  );
}
