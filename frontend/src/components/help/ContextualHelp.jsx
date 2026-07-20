import { useQuery } from "@tanstack/react-query";
import { HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { getContextualHelp } from "@/lib/onboarding";

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
            </div>
          ))}
          {help.isLoading && <div className="text-sm text-muted-foreground">Loading...</div>}
        </div>
      </PopoverContent>
    </Popover>
  );
}
