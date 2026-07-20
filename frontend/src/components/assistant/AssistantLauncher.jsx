import { useState } from "react";
import { Link } from "react-router-dom";
import { Bot, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useAuth } from "@/auth/AuthContext";
import AssistantPanel from "@/components/assistant/AssistantPanel";

export default function AssistantLauncher() {
  const { hasPerm } = useAuth();
  const [open, setOpen] = useState(false);
  if (!hasPerm?.("ai_assistant:use")) return null;
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button className="fixed bottom-5 right-5 z-40 h-12 rounded-full shadow-lg" data-testid="assistant-launcher">
          <Bot className="mr-2 size-5" />Assistant
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-full overflow-y-auto p-4 sm:max-w-[720px]">
        <SheetHeader className="mb-4">
          <div className="flex items-center justify-between gap-3 pr-8">
            <SheetTitle>Business Assistant</SheetTitle>
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
