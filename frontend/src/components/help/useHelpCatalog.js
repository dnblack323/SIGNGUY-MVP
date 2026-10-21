import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Briefcase, Calculator, Car, Factory, Landmark, LifeBuoy, Rocket, Sparkles, Store, UserCog, Users } from "lucide-react";
import { listHelpArticles, listHelpCategories } from "@/lib/help";

export const CATEGORY_ICONS = {
  getting_started: Rocket,
  shop_management: Briefcase,
  customers_sales: Users,
  production: Factory,
  pricing: Calculator,
  webstores: Store,
  wrap_lab: Car,
  business: Landmark,
  ai_tools: Sparkles,
  support: LifeBuoy,
  role_guides: UserCog,
};

export const iconForCategory = (key) => CATEGORY_ICONS[key] || BookOpen;

/**
 * Lightweight catalog of every published article (no bodies) plus the ordered categories. One cached
 * query pair feeds the Help Center home, the Documentation navigation, related links and previous/next.
 */
export default function useHelpCatalog(enabled = true) {
  const articlesQuery = useQuery({ queryKey: ["help", "articles", "all"], queryFn: () => listHelpArticles({}), enabled, staleTime: 60_000 });
  const categoriesQuery = useQuery({ queryKey: ["help", "categories"], queryFn: listHelpCategories, enabled, staleTime: 60_000 });

  const catalog = useMemo(() => {
    const articles = articlesQuery.data?.items || [];
    const byName = new Map();
    articles.forEach((article) => {
      byName.set(article.slug, article);
      (article.aliases || []).forEach((alias) => byName.set(alias, article));
    });
    const categories = (categoriesQuery.data?.items || []).filter((c) => c.key !== "release_notes");
    const known = new Set((categoriesQuery.data?.items || []).map((c) => c.key));
    const groups = categories
      .map((category) => ({ ...category, articles: articles.filter((a) => a.category === category.key) }))
      .filter((group) => group.articles.length);
    // Platform-managed articles may use a category outside the fixed list; keep them reachable.
    const other = articles.filter((a) => !known.has(a.category));
    if (other.length) groups.push({ key: "other", label: "Other", description: "Additional articles.", count: other.length, articles: other });
    return { articles, byName, groups, ordered: groups.flatMap((g) => g.articles), categories: categoriesQuery.data?.items || [] };
  }, [articlesQuery.data, categoriesQuery.data]);

  return { ...catalog, isLoading: articlesQuery.isLoading || categoriesQuery.isLoading, isError: articlesQuery.isError };
}
