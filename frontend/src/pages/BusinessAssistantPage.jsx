import PageHeader from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/AuthContext";
import AssistantPanel from "@/components/assistant/AssistantPanel";
import { Bot, Library, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

export default function BusinessAssistantPage() {
  const { hasPerm } = useAuth();
  if (!hasPerm("ai_assistant:use")) {
    return (
      <div className="space-y-4" data-testid="business-assistant-page">
        <PageHeader title="Business Assistant" subtitle="AI credits apply" />
        <Alert>
          <Bot className="size-4" />
          <AlertTitle>Access required</AlertTitle>
          <AlertDescription>Your account does not include Business Assistant access.</AlertDescription>
        </Alert>
      </div>
    );
  }
  return (
    <div className="space-y-4" data-testid="business-assistant-page">
      <PageHeader
        title="Business Assistant"
        subtitle="AI credits apply"
        actions={(
          <>
            <Button asChild size="sm" variant="outline"><Link to="/studio/prompts"><Library className="mr-2 size-4" />Prompts</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to="/studio"><Sparkles className="mr-2 size-4" />Studio</Link></Button>
          </>
        )}
      />
      <AssistantPanel />
    </div>
  );
}
