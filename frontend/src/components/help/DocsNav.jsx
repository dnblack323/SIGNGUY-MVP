import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { helpDocsPath } from "@/lib/help";
import { iconForCategory } from "@/components/help/useHelpCatalog";

/** Collapsible category groups. Only the category being read is open by default. */
export default function DocsNav({ groups, activeSlug, activeCategory, onNavigate }) {
  const [open, setOpen] = useState(() => new Set(activeCategory ? [activeCategory] : []));
  useEffect(() => {
    if (activeCategory) setOpen((prev) => (prev.has(activeCategory) ? prev : new Set(prev).add(activeCategory)));
  }, [activeCategory]);

  const toggle = (key) => setOpen((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  return (
    <nav aria-label="Documentation categories" className="space-y-1" data-testid="docs-nav">
      {groups.map((group) => {
        const Icon = iconForCategory(group.key);
        const expanded = open.has(group.key);
        return (
          <div key={group.key}>
            <button
              type="button"
              onClick={() => toggle(group.key)}
              aria-expanded={expanded}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm font-medium hover:bg-muted"
              data-testid={`docs-group-${group.key}`}
            >
              <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
              <span className="flex-1">{group.label}</span>
              {expanded ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
            </button>
            {expanded && (
              <ul className="ml-4 mt-0.5 space-y-0.5 border-l pl-2">
                {group.articles.map((article) => (
                  <li key={article.slug}>
                    <Link
                      to={helpDocsPath(article.slug)}
                      onClick={onNavigate}
                      aria-current={article.slug === activeSlug ? "page" : undefined}
                      className={cn("block rounded-md px-2 py-1 text-sm hover:bg-muted", article.slug === activeSlug ? "bg-muted font-medium text-foreground" : "text-muted-foreground")}
                      data-testid={`docs-nav-${article.slug}`}
                    >
                      {article.title}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </nav>
  );
}
