import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BookOpen, Bug, LifeBuoy, Search, Sparkles } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import useHelpCatalog, { iconForCategory } from "@/components/help/useHelpCatalog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/auth/AuthContext";
import { getFailedSubscriptionGuidance, helpDocsPath, HELP_ARTICLE_SLUGS, listHelpArticles } from "@/lib/help";

const GETTING_STARTED = [
  { slug: HELP_ARTICLE_SLUGS.gettingStarted, text: "Read the short path from a new account to a finished order." },
  { slug: HELP_ARTICLE_SLUGS.companyProfile, text: "Enter your business details once." },
  { slug: HELP_ARTICLE_SLUGS.pricingSetup, text: "Make estimates usable with your own costs." },
  { slug: HELP_ARTICLE_SLUGS.firstOrder, text: "Run one real job from customer to payment." },
];
const POPULAR = ["quotes", "orders", "invoices-and-payments", "production-board", "customer-portal", "webstore-setup", "time-clock", "pricing-methods"];
const COMMON_TASKS = [
  ["Create an order", "first-order"],
  ["Record a payment", "invoices-and-payments"],
  ["Add an employee", "employees-and-permissions"],
  ["Set labor rates and overhead", "materials-labor-equipment"],
  ["Publish a Webstore", "webstore-products-and-launch"],
  ["Get customer artwork approved", "approvals-and-proofs"],
];

export default function HelpCenterPage() {
  const { hasPerm } = useAuth();
  const navigate = useNavigate();
  const canRead = hasPerm("help:read");
  const [q, setQ] = useState("");
  const term = q.trim();
  const catalog = useHelpCatalog(canRead);
  const suggestions = useQuery({ queryKey: ["help", "suggest", term], queryFn: () => listHelpArticles({ q: term }), enabled: canRead && term.length >= 2 });
  const billing = useQuery({ queryKey: ["failed-subscription-guidance"], queryFn: getFailedSubscriptionGuidance, enabled: hasPerm("subscription:read") });

  if (!canRead) {
    return (
      <div className="space-y-4" data-testid="help-center-page">
        <PageHeader title="Help Center" subtitle="Documentation is available to internal shop users." />
        <Alert><BookOpen className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account cannot read Help Center articles.</AlertDescription></Alert>
      </div>
    );
  }

  const items = (suggestions.data?.items || []).filter((a) => a.category !== "release_notes");
  const popular = POPULAR.map((slug) => catalog.byName.get(slug)).filter(Boolean);
  const submit = (e) => {
    e.preventDefault();
    if (term) navigate(helpDocsPath(null, { q: term }));
  };
  const pastDue = billing.data && billing.data.dunning_state && billing.data.dunning_state !== "current";

  return (
    <div className="space-y-8" data-testid="help-center-page">
      <PageHeader title="Help Center" subtitle="Find answers, learn how SIGNGUY works, or get in touch." actions={<Button asChild variant="outline" size="sm"><Link to="/help/docs"><BookOpen className="mr-1 size-4" aria-hidden="true" />Browse Documentation</Link></Button>} />

      <section aria-label="Search for help" className="max-w-2xl space-y-2">
        <form onSubmit={submit} role="search" className="relative">
          <Search className="absolute left-3 top-3 size-4 text-muted-foreground" aria-hidden="true" />
          <Input className="h-10 pl-9" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search for help, e.g. deposit, labor rate, Webstore" aria-label="Search for help" data-testid="help-search-input" />
        </form>
        {term.length >= 2 && !suggestions.isLoading && (
          items.length ? (
            <ul className="divide-y rounded-md border bg-card" data-testid="help-search-results">
              {items.slice(0, 6).map((a) => (
                <li key={a.slug}><Link to={helpDocsPath(a.slug)} className="block p-2.5 hover:bg-muted/60"><span className="text-sm font-medium">{a.title}</span><span className="block text-xs text-muted-foreground">{a.snippet || a.summary}</span></Link></li>
              ))}
              {items.length > 6 && <li><Link to={helpDocsPath(null, { q: term })} className="block p-2.5 text-sm text-primary hover:underline">See all {items.length} results</Link></li>}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground" data-testid="help-search-empty">No articles match "{term}". Try different words, or <Link to="/help/contact" className="text-primary underline">contact support</Link>.</p>
          )
        )}
      </section>

      {pastDue && (
        <Alert data-testid="billing-guidance"><AlertTriangle className="size-4" /><AlertTitle>Subscription payment needs attention</AlertTitle><AlertDescription>{billing.data.guidance} <Link className="underline" to={helpDocsPath("subscription-and-billing")}>Learn more</Link></AlertDescription></Alert>
      )}

      <section aria-labelledby="hc-start" className="space-y-2">
        <h2 id="hc-start" className="text-base font-semibold">Getting started</h2>
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          {GETTING_STARTED.map(({ slug, text }) => {
            const a = catalog.byName.get(slug);
            return <li key={slug}><Link to={helpDocsPath(slug)} className="font-medium text-primary hover:underline">{a?.title || slug}</Link> <span className="text-muted-foreground">{text}</span></li>;
          })}
        </ol>
        <p className="text-sm text-muted-foreground">Prefer a checklist? Use <Link to="/help/onboarding" className="text-primary underline">Guided Onboarding</Link>.</p>
      </section>

      <div className="grid gap-8 md:grid-cols-2">
        <section aria-labelledby="hc-popular" className="space-y-2">
          <h2 id="hc-popular" className="text-base font-semibold">Popular topics</h2>
          <ul className="space-y-1.5 text-sm">
            {popular.map((a) => <li key={a.slug}><Link to={helpDocsPath(a.slug)} className="font-medium text-primary hover:underline">{a.title}</Link><span className="block text-xs text-muted-foreground">{a.summary}</span></li>)}
          </ul>
        </section>
        <section aria-labelledby="hc-tasks" className="space-y-2">
          <h2 id="hc-tasks" className="text-base font-semibold">Common tasks</h2>
          <ul className="space-y-1 text-sm">
            {COMMON_TASKS.map(([label, slug]) => <li key={slug}><Link to={helpDocsPath(slug)} className="text-primary hover:underline">{label}</Link></li>)}
          </ul>
        </section>
      </div>

      <section aria-labelledby="hc-browse" className="space-y-2">
        <h2 id="hc-browse" className="text-base font-semibold">Browse by category</h2>
        <div className="grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
          {catalog.groups.map((g) => {
            const Icon = iconForCategory(g.key);
            return (
              <Link key={g.key} to={helpDocsPath(null, { category: g.key })} className="flex gap-2 rounded-md p-2 hover:bg-muted/60" data-testid={`help-category-${g.key}`}>
                <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span><span className="text-sm font-medium">{g.label}</span> <span className="text-xs text-muted-foreground">({g.articles.length})</span><span className="block text-xs text-muted-foreground">{g.description}</span></span>
              </Link>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="hc-help" className="grid gap-6 border-t pt-6 md:grid-cols-2">
        <div className="space-y-1">
          <h2 id="hc-help" className="text-base font-semibold">Troubleshooting</h2>
          <p className="text-sm text-muted-foreground">Something not working? Start with <Link to={helpDocsPath("troubleshooting")} className="text-primary underline">common problems</Link> or the <Link to={helpDocsPath("faq")} className="text-primary underline">FAQ</Link>.</p>
        </div>
        <div className="space-y-2">
          <h2 className="text-base font-semibold">Contact support</h2>
          <div className="flex flex-wrap gap-2">
            {hasPerm("support:write") && <Button asChild size="sm"><Link to="/help/contact"><LifeBuoy className="mr-1 size-4" aria-hidden="true" />Contact Support</Link></Button>}
            <Button asChild size="sm" variant="outline"><Link to="/help/bugs"><Bug className="mr-1 size-4" aria-hidden="true" />Report a bug</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to="/help/feature-requests"><Sparkles className="mr-1 size-4" aria-hidden="true" />Request a feature</Link></Button>
            <Button asChild size="sm" variant="ghost"><Link to="/help/whats-new">What's New</Link></Button>
          </div>
        </div>
      </section>
    </div>
  );
}
