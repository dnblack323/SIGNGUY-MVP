import { useQuery } from "@tanstack/react-query";
import { HelpCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { getContextualHelp, helpDocsPath } from "@/lib/help";

export default function ContextualHelp({ surfaceKey, module, label = "Help" }) {
  const help = useQuery({
    queryKey: ["contextual-help", surfaceKey, module],
    queryFn: () => getContextualHelp(surfaceKey, module ? { module } : {}),
    enabled: !!surfaceKey,
  });
  const items = help.data?.items || [];
  if (!items.length && !help.isLoading) return null;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={label} data-testid={`contextual-help-${surfaceKey}`}>
          <HelpCircle className="size-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id || item.help_key} className="space-y-1">
              <div className="font-medium text-sm">{item.title}</div>
              <p className="text-sm text-muted-foreground">{item.body}</p>
              {item.article_slug && (
                <Link to={helpDocsPath(item.article_slug)} className="text-sm text-primary underline underline-offset-2" data-testid={`contextual-help-article-${item.help_key}`}>
                  Read the full article
                </Link>
              )}
            </div>
          ))}
          {help.isLoading && <div className="text-sm text-muted-foreground">Loading...</div>}
        </div>
      </PopoverContent>
    </Popover>
  );
}
