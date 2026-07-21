import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, MessageSquare, RotateCcw, Search } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import ContextualHelp from "@/components/help/ContextualHelp";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/auth/AuthContext";
import { extractError } from "@/lib/api";
import { createSupportEscalation, getFailedSubscriptionGuidance, searchHelp, sendHelpFeedback } from "@/lib/onboarding";
import { toast } from "sonner";

export default function HelpCenterPage() {
  const { hasPerm } = useAuth();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("all");
  const [selected, setSelected] = useState(null);
  const [support, setSupport] = useState({ subject: "", message: "" });

  const params = useMemo(() => ({ q: q || undefined, category: category === "all" ? undefined : category }), [q, category]);
  const help = useQuery({ queryKey: ["help-articles", params], queryFn: () => searchHelp(params), enabled: hasPerm("help:read") });
  const billingGuidance = useQuery({ queryKey: ["failed-subscription-guidance"], queryFn: getFailedSubscriptionGuidance, enabled: hasPerm("subscription:read") });
  const articles = help.data?.items || [];
  const current = selected || articles[0];
  const feedback = useMutation({
    mutationFn: (helpful) => sendHelpFeedback({ article_id: current?.id, article_slug: current?.slug, helpful, idempotency_key: `${current?.slug}-${helpful}` }),
    onSuccess: () => toast.success("Feedback saved"),
    onError: (err) => toast.error(extractError(err)),
  });
  const escalation = useMutation({
    mutationFn: () => createSupportEscalation({ ...support, source_surface: "help_center", idempotency_key: `help-${Date.now()}` }),
    onSuccess: async () => {
      toast.success("Support escalation created");
      setSupport({ subject: "", message: "" });
      await qc.invalidateQueries({ queryKey: ["help-articles"] });
    },
    onError: (err) => toast.error(extractError(err)),
  });

  if (!hasPerm("help:read")) {
    return (
      <div className="space-y-4" data-testid="help-center-page">
        <PageHeader title="Help Center" subtitle="Documentation is available to internal shop users." />
        <Alert><BookOpen className="size-4" /><AlertTitle>Access required</AlertTitle><AlertDescription>Your account cannot read Help Center articles.</AlertDescription></Alert>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="help-center-page">
      <PageHeader
        title="Help Center"
        subtitle="Searchable product documentation, role guides, module guides, and support escalation."
        actions={<><ContextualHelp surfaceKey="billing.subscriptions" module="billing" /><Button variant="outline" size="sm" onClick={() => help.refetch()}><RotateCcw className="size-4 mr-2" />Refresh</Button></>}
      />

      <div className="grid grid-cols-1 xl:grid-cols-[380px_1fr] gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Articles</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
              <Input className="pl-8" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search help" data-testid="help-search-input" />
            </div>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {["all", "onboarding", "role_guides", "module_guides", "billing", "ai", "trust", "release_notes"].map((v) => <SelectItem key={v} value={v}>{v.replace(/_/g, " ")}</SelectItem>)}
              </SelectContent>
            </Select>
            <div className="grid gap-2">
              {articles.map((article) => (
                <button
                  type="button"
                  key={article.id}
                  onClick={() => setSelected(article)}
                  className="rounded-md border p-3 text-left hover:bg-muted/60"
                  data-testid={`help-article-${article.slug}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-sm">{article.title}</span>
                    <Badge variant="outline">{article.category.replace(/_/g, " ")}</Badge>
                  </div>
                  <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{article.body}</div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">{current?.title || "No article selected"}</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {current ? (
                <>
                  <div className="prose prose-sm max-w-none whitespace-pre-wrap text-sm">{current.body}</div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => feedback.mutate(true)}>Helpful</Button>
                    <Button variant="outline" size="sm" onClick={() => feedback.mutate(false)}>Needs work</Button>
                  </div>
                </>
              ) : <div className="text-sm text-muted-foreground">No matching article.</div>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Subscription Guidance</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex items-center gap-2"><Badge variant="outline">{billingGuidance.data?.dunning_state || "current"}</Badge><span>{billingGuidance.data?.mutated_billing === false ? "read-only" : ""}</span></div>
              <p className="text-muted-foreground">{billingGuidance.data?.guidance || "Billing guidance is available to subscription-enabled users."}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Contact Support</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-1"><Label htmlFor="help-support-subject">Subject</Label><Input id="help-support-subject" value={support.subject} onChange={(e) => setSupport({ ...support, subject: e.target.value })} /></div>
              <div className="grid gap-1"><Label htmlFor="help-support-message">Message</Label><Textarea id="help-support-message" rows={4} value={support.message} onChange={(e) => setSupport({ ...support, message: e.target.value })} /></div>
              <Button disabled={!hasPerm("support:write") || escalation.isPending || !support.subject || !support.message} onClick={() => escalation.mutate()}>
                <MessageSquare className="size-4 mr-2" />Send
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
