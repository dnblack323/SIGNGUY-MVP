import { useState } from "react";
import { Link } from "react-router-dom";
import { Bot, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAuth } from "@/auth/AuthContext";
import AssistantPanel from "@/components/assistant/AssistantPanel";

export default function AssistantLauncher() {
  const { hasPerm } = useAuth();
  const [open, setOpen] = useState(false);
  if (!hasPerm?.("ai_assistant:use")) return null;
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <Tooltip>
        <TooltipTrigger asChild>
          <SheetTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className="h-9 shrink-0 rounded-sm border-slate-700 bg-slate-950 px-2 text-white hover:bg-slate-900 hover:text-white focus-visible:ring-blue-300"
              data-testid="workspace-dock-assistant"
              aria-label="Assistant"
              title="Assistant"
            >
              <Bot className="size-4" aria-hidden="true" />
              <span className="hidden xl:inline">Assistant</span>
            </Button>
          </SheetTrigger>
        </TooltipTrigger>
        <TooltipContent side="top">Assistant</TooltipContent>
      </Tooltip>
      <SheetContent side="right" className="w-full overflow-y-auto p-4 sm:max-w-[720px]">
        <SheetHeader className="mb-4">
          <div className="flex items-center justify-between gap-3 pr-8">
            <SheetTitle>Business Assistant</SheetTitle>
            <SheetDescription className="sr-only">Ask the SignGuy AI business assistant for help with the current workspace.</SheetDescription>
            <Button asChild size="sm" variant="outline" onClick={() => setOpen(false)}>
              <Link to="/studio/assistant"><Maximize2 className="mr-2 size-4" />Workspace</Link>
            </Button>
          </div>
        </SheetHeader>
        <AssistantPanel compact />
      </SheetContent>
    </Sheet>
  );
}
