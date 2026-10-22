import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { AssistantBoundary, useAssistantSession } from "./AssistantSession";
import VoiceConversation from "./VoiceConversation";
import { Bot, Check, ExternalLink, Mic, Send, X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { extractError } from "@/lib/api";
import {
  cancelAssistantProposal,
  confirmAssistantProposal,
  createAssistantRoutine,
  createStudioDelegation,
  deleteAssistantMemory,
  deleteAssistantRoutine,
  disableAssistantRoutine,
  dismissAssistantInsight,
  enableAssistantRoutine,
  executeAssistantProposal,
  getAssistantCatalog,
  getVoiceConfig,
  listAssistantInsights,
  listAssistantMemory,
  listAssistantQuickActions,
  listAssistantRoutines,
  proposeAssistantAction,
  saveAssistantMemory,
  updateAssistantRoutine,
} from "@/lib/businessAssistant";



function SourceList({ sources = [] }) {
  if (!sources.length) return null;
  return (
    <div className="space-y-2" data-testid="assistant-sources">
      <div className="text-xs font-medium uppercase text-muted-foreground">Sources</div>
      <div className="flex flex-wrap gap-2">
        {sources.map((source) => (
          <Badge key={source.id || `${source.source_type}-${source.source_id}`} variant="outline" className="rounded-md">
            {source.route ? (
              <Link to={source.route} className="inline-flex items-center gap-1">
                {source.source_label || source.source_type}
                <ExternalLink className="size-3" />
              </Link>
            ) : (
              source.source_label || source.source_type
            )}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function ProposalCard({ proposal, onUpdated }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const act = async (kind) => {
    setBusy(kind);
    setError("");
    try {
      const next = kind === "confirm"
        ? await confirmAssistantProposal(proposal.id)
        : kind === "cancel"
          ? await cancelAssistantProposal(proposal.id)
          : await executeAssistantProposal(proposal.id, `assistant-exec-${proposal.id}`);
      onUpdated?.(next);
    } catch (err) {
      setError(extractError(err, "Unable to update proposal"));
    } finally {
      setBusy("");
    }
  };

  return (
    <Card className="border-amber-200 bg-amber-50/60" data-testid="assistant-action-proposal">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between gap-2 text-base">
          <span>{proposal.title}</span>
          <Badge variant="outline">{proposal.status}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">{proposal.summary}</p>
        <div className="rounded border bg-background p-3">
          <pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify(proposal.preview || proposal.editable_payload || {}, null, 2)}</pre>
        </div>
        {(proposal.warnings || []).map((warning) => <div key={warning} className="text-amber-800">{warning}</div>)}
        {error && <div className="text-destructive">{error}</div>}
        <div className="flex flex-wrap gap-2">
          {["proposed", "edited"].includes(proposal.status) && (
            <Button size="sm" onClick={() => act("confirm")} disabled={!!busy}><Check className="mr-2 size-4" />Confirm</Button>
          )}
          {proposal.status === "confirmed" && (
            <Button size="sm" onClick={() => act("execute")} disabled={!!busy}><Check className="mr-2 size-4" />Execute</Button>
          )}
          {!["succeeded", "failed", "canceled"].includes(proposal.status) && (
            <Button size="sm" variant="outline" onClick={() => act("cancel")} disabled={!!busy}><X className="mr-2 size-4" />Cancel</Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function AssistantPanelContent({ compact = false }) {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const session = useAssistantSession();
  const { mode, setMode, message, setMessage, conversationId, messages, sources, proposals,
    setProposals, loading, setLoading, activate } = session;
  useEffect(() => { activate(); }, [activate]);
  const [catalog, setCatalog] = useState(null);
  const [voiceConfig, setVoiceConfig] = useState(null);
  const [quickActions, setQuickActions] = useState([]);
  const [delegation, setDelegation] = useState(null);
  const [memoryItems, setMemoryItems] = useState([]);
  const [memoryDraft, setMemoryDraft] = useState("");
  const [routines, setRoutines] = useState([]);
  const [routineDraft, setRoutineDraft] = useState("");
  const [insights, setInsights] = useState([]);
  const [error, setError] = useState("");
  const context = useMemo(() => {
    const contextType = searchParams.get("context_type");
    const contextId = searchParams.get("context_id");
    if (contextType && contextId) return { source_entity_type: contextType, source_entity_id: contextId };
    const match = location.pathname.match(/^\/(customers|quotes|orders|invoices|work-orders)\/([^/]+)$/);
    const types = { customers: "customer", quotes: "quote", orders: "order", invoices: "invoice", "work-orders": "work_order" };
    return match ? { source_entity_type: types[match[1]], source_entity_id: match[2] } : {};
  }, [searchParams, location.pathname]);

  useEffect(() => {
    let active = true;
    Promise.all([getAssistantCatalog(), getVoiceConfig()]).then(([cat, voice]) => {
      if (!active) return;
      setCatalog(cat);
      setVoiceConfig(voice);
    }).catch((err) => setError(extractError(err, "Unable to load Business Assistant")));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    listAssistantQuickActions({ mode }).then((items) => {
      if (active) setQuickActions(items);
    }).catch(() => {
      if (active) setQuickActions([]);
    });
    return () => { active = false; };
  }, [mode]);

  const refreshAssistantSideData = useCallback(async () => {
    const [mem, routineList, insightList] = await Promise.all([
      listAssistantMemory().catch(() => []),
      listAssistantRoutines().catch(() => []),
      listAssistantInsights({ generate: true }).catch(() => []),
    ]);
    setMemoryItems(mem);
    setRoutines(routineList);
    setInsights(insightList);
  }, []);

  useEffect(() => {
    refreshAssistantSideData();
  }, [refreshAssistantSideData]);

  const submit = async () => {
    if (!message.trim()) return;
    setError("");
    try {
      await session.send(context);
    } catch (err) {
      setError(extractError(err, "Unable to ask the assistant"));
    }
  };

  const saveMemory = async () => {
    if (!memoryDraft.trim()) return;
    try {
      await saveAssistantMemory({ memory_key: `note-${Date.now()}`, content_text: memoryDraft });
      setMemoryDraft("");
      await refreshAssistantSideData();
    } catch (err) {
      setError(extractError(err, "Unable to save memory"));
    }
  };

  const createRoutine = async () => {
    if (!routineDraft.trim()) return;
    try {
      await createAssistantRoutine({ name: routineDraft, prompt: routineDraft, mode });
      setRoutineDraft("");
      await refreshAssistantSideData();
    } catch (err) {
      setError(extractError(err, "Unable to create routine"));
    }
  };

  const toggleRoutine = async (routine) => {
    try {
      if (routine.status === "active") await disableAssistantRoutine(routine.id);
      else await enableAssistantRoutine(routine.id);
      await refreshAssistantSideData();
    } catch (err) {
      setError(extractError(err, "Unable to update routine"));
    }
  };

  const handleQuickAction = async (action) => {
    setDelegation(null);
    if (action.action_type === "studio_delegation") {
      setLoading(true);
      setError("");
      try {
        setDelegation(await createStudioDelegation({
          tool_key: "social_post_builder",
          mode_key: "completed_work_showcase",
          mode,
          context,
        }));
      } catch (err) {
        setError(extractError(err, "Unable to open Studio delegation"));
      } finally {
        setLoading(false);
      }
      return;
    }
    if (action.action_type) {
      setLoading(true);
      setError("");
      try {
        const proposal = await proposeAssistantAction({
          action_type: action.action_type,
          title: action.label,
          summary: action.prompt,
          body: message,
          mode: action.mode || mode,
          conversation_id: conversationId || undefined,
          target_refs: context.source_entity_type ? [{ type: context.source_entity_type, id: context.source_entity_id }] : [],
          idempotency_key: `quick-action-${action.action_type}-${Date.now()}`,
          metering_idempotency_key: `quick-action-meter-${action.action_type}-${Date.now()}`,
        });
        setProposals((prev) => [proposal, ...prev]);
      } catch (err) {
        setError(extractError(err, "Unable to create assistant proposal"));
      } finally {
        setLoading(false);
      }
      return;
    }
    setMode(action.mode || mode);
    setMessage(action.prompt);
  };

  const contextLabel = context.source_entity_type ? `${context.source_entity_type.replace("_", " ")} ${context.source_entity_id}` : "No record context";
  const modes = catalog?.modes || [];

  return (
    <div className={compact ? "space-y-4" : "grid gap-4 xl:grid-cols-[1fr_360px]"} data-testid="business-assistant-panel">
      <section className="space-y-4">
        {error && <Alert variant="destructive" data-testid="assistant-error"><AlertTitle>Business Assistant</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
        <div className="flex flex-wrap items-center gap-3">
          <label>Conversation <select aria-label="Conversation" value={conversationId || ""} disabled={loading} onChange={(event) => session.selectConversation(event.target.value || null).catch(() => setError("Unable to load conversation"))}>
            <option value="">New conversation</option>{session.conversations.map((item) => <option key={item.id} value={item.id}>{item.title || "Conversation"}</option>)}
          </select></label>
          <Link className="text-sm underline" to="/settings/assistant">Assistant Settings</Link>
          <div className="min-w-[180px]">
            <Label>Mode</Label>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger data-testid="assistant-mode"><SelectValue /></SelectTrigger>
              <SelectContent>{modes.map((item) => <SelectItem key={item.mode_key} value={item.mode_key}>{item.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="min-w-[220px] flex-1">
            <Label>Context</Label>
            <Input readOnly value={contextLabel} data-testid="assistant-context" />
          </div>
          <Badge variant="outline" className="mt-6">{catalog?.credit_display || "AI credits apply"}</Badge>
        </div>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Bot className="size-5" />Conversation</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {quickActions.length > 0 && (
              <div className="flex flex-wrap gap-2" data-testid="assistant-quick-actions">
                {quickActions.slice(0, 8).map((action) => (
                  <Button key={action.label} size="sm" variant="outline" onClick={() => handleQuickAction(action)}>
                    {action.label}
                  </Button>
                ))}
              </div>
            )}
            {delegation && (
              <Alert data-testid="assistant-studio-delegation">
                <SparklesIcon />
                <AlertTitle>Studio draft ready to open</AlertTitle>
                <AlertDescription>
                  <Link to={delegation.route} className="underline">{delegation.message}</Link>
                </AlertDescription>
              </Alert>
            )}
            <div className="min-h-[260px] space-y-3 rounded border bg-muted/20 p-3" data-testid="assistant-history">
              {messages.length === 0 ? (
                <div className="text-sm text-muted-foreground">Ask about invoices, production blockers, workers today, quote follow-ups, or reports.</div>
              ) : messages.map((item) => (
                <div key={item.id} className={item.role === "user" ? "ml-auto max-w-[86%] rounded bg-primary p-3 text-sm text-primary-foreground" : "max-w-[92%] rounded border bg-background p-3 text-sm"}>
                          {item.metadata?.interrupted && !item.content_text?.startsWith("[Interrupted") && <span className="block text-xs">Interrupted; generated transcript may include unplayed speech.</span>}{item.content_text}
                </div>
              ))}
            </div>
            <SourceList sources={sources} />
            <div className="grid gap-2 md:grid-cols-[1fr_auto]">
              <Textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ask the Business Assistant..." rows={3} data-testid="assistant-message-input" />
              <Button onClick={submit} disabled={loading || !session.ready || !message.trim()} data-testid="assistant-send"><Send className="mr-2 size-4" />Send</Button>
            </div>
          </CardContent>
        </Card>

        {proposals.map((proposal) => (
          <ProposalCard key={proposal.id} proposal={proposal} onUpdated={(next) => setProposals((prev) => prev.map((item) => (item.id === next.id || item.id === next.proposal_id ? { ...item, ...next } : item)))} />
        ))}
      </section>

      <aside className="space-y-4">
        <Card data-testid="assistant-voice">
          <CardHeader><CardTitle className="flex items-center justify-between text-base"><span className="flex items-center gap-2"><Mic className="size-5" />Voice</span><Badge>{voiceConfig?.interactions_available ? session.voice.state : "Setup"}</Badge></CardTitle></CardHeader>
          <CardContent className="space-y-4"><VoiceConversation config={voiceConfig} context={context} /></CardContent>
        </Card>

        <Card data-testid="assistant-memory">
          <CardHeader><CardTitle className="text-base">Memory</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input value={memoryDraft} onChange={(event) => setMemoryDraft(event.target.value)} placeholder="Retain a preference" data-testid="assistant-memory-input" />
              <Button size="sm" onClick={saveMemory}>Save</Button>
            </div>
            <div className="space-y-2">
              {memoryItems.length === 0 ? <div className="text-sm text-muted-foreground">No retained memory.</div> : memoryItems.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-2 rounded border p-2 text-sm">
                  <span>{item.content_text}</span>
                  <Button size="sm" variant="ghost" onClick={async () => { await deleteAssistantMemory(item.id); await refreshAssistantSideData(); }}><X className="size-4" /></Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card data-testid="assistant-routines">
          <CardHeader><CardTitle className="text-base">Routines</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input value={routineDraft} onChange={(event) => setRoutineDraft(event.target.value)} placeholder="Routine prompt" data-testid="assistant-routine-input" />
              <Button size="sm" onClick={createRoutine}>Add</Button>
            </div>
            {routines.length === 0 ? <div className="text-sm text-muted-foreground">No routines.</div> : routines.map((routine) => (
              <div key={routine.id} className="space-y-2 rounded border p-2 text-sm">
                <Input
                  value={routine.name}
                  onChange={(event) => setRoutines((prev) => prev.map((item) => item.id === routine.id ? { ...item, name: event.target.value } : item))}
                  onBlur={async (event) => { await updateAssistantRoutine(routine.id, { name: event.target.value }); await refreshAssistantSideData(); }}
                />
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{routine.status}</Badge>
                  <Button size="sm" variant="outline" onClick={() => toggleRoutine(routine)}>{routine.status === "active" ? "Disable" : "Enable"}</Button>
                  <Button size="sm" variant="ghost" onClick={async () => { await deleteAssistantRoutine(routine.id); await refreshAssistantSideData(); }}>Delete</Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card data-testid="assistant-insights">
          <CardHeader><CardTitle className="text-base">Insights</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {insights.length === 0 ? <div className="text-sm text-muted-foreground">No current insights.</div> : insights.map((insight) => (
              <div key={insight.id} className="rounded border p-2 text-sm">
                <div className="font-medium">{insight.title}</div>
                <div className="text-muted-foreground">{insight.summary}</div>
                <Button size="sm" variant="ghost" onClick={async () => { await dismissAssistantInsight(insight.id); await refreshAssistantSideData(); }}>Dismiss</Button>
              </div>
            ))}
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}

function PrivatePanel(props) {
  const session = useAssistantSession();
  return <AssistantPanelContent key={session.identity} {...props} />;
}

export default function AssistantPanel(props) { return <AssistantBoundary><PrivatePanel {...props} /></AssistantBoundary>; }

function SparklesIcon() {
  return <Bot className="size-4" />;
}
