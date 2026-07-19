import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Sparkles } from "lucide-react";

function query(params) {
  return new URLSearchParams(Object.entries(params).filter(([, value]) => value)).toString();
}

export default function AIContextualActions({ contextType, contextId, actions = [] }) {
  if (!contextType || !contextId || actions.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="ai-contextual-actions">
      {actions.map((action) => (
        <Button key={`${action.tool}-${action.mode}`} asChild size="sm" variant={action.variant || "outline"}>
          <Link to={`/studio?${query({ context_type: contextType, context_id: contextId, tool: action.tool, mode: action.mode })}`}>
            <Sparkles className="size-4 mr-2" />{action.label}
          </Link>
        </Button>
      ))}
    </div>
  );
}
