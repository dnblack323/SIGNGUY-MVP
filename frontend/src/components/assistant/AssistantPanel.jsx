import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Bot, Check, ExternalLink, Mic, MicOff, Pause, Send, Square, Volume2, X } from "lucide-react";
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
  createStudioDelegation,
  createVoiceSession,
  executeAssistantProposal,
  getAssistantCatalog,
  getVoiceConfig,
  listAssistantQuickActions,
  sendAssistantMessage,
} from "@/lib/businessAssistant";

const VOICE_STATES = {
  idle: "Idle",
  connecting: "Connecting",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  interrupted: "Interrupted",
  reconnecting: "Reconnecting",
  unavailable: "Unavailable",
  error: "Error",
};

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

export default function AssistantPanel({ compact = false }) {
  const [searchParams] = useSearchParams();
  const [catalog, setCatalog] = useState(null);
  const [voiceConfig, setVoiceConfig] = useState(null);
  const [mode, setMode] = useState("owner");
  const [message, setMessage] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [sources, setSources] = useState([]);
  const [proposals, setProposals] = useState([]);
  const [quickActions, setQuickActions] = useState([]);
  const [delegation, setDelegation] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [voiceState, setVoiceState] = useState("idle");
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const [pushToTalk, setPushToTalk] = useState(true);
  const [vadEnabled, setVadEnabled] = useState(false);
  const rtcRef = useRef({ pc: null, stream: null, dc: null });

  const context = useMemo(() => {
    const contextType = searchParams.get("context_type");
    const contextId = searchParams.get("context_id");
    return contextType && contextId ? { source_entity_type: contextType, source_entity_id: contextId } : {};
  }, [searchParams]);

  useEffect(() => {
    let active = true;
    Promise.all([getAssistantCatalog(), getVoiceConfig()]).then(([cat, voice]) => {
      if (!active) return;
      setCatalog(cat);
      setVoiceConfig(voice);
      setPushToTalk(!!voice.push_to_talk_default);
      setVadEnabled(!voice.push_to_talk_default);
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

  const submit = async () => {
    if (!message.trim()) return;
    setLoading(true);
    setError("");
    try {
      const result = await sendAssistantMessage({
        message,
        mode,
        conversation_id: conversationId || undefined,
        context,
        idempotency_key: `assistant-message-${Date.now()}`,
      });
      setConversationId(result.conversation.id);
      setMessages((prev) => [...prev, result.user_message, result.assistant_message]);
      setSources(result.sources || []);
      setMessage("");
    } catch (err) {
      setError(extractError(err, "Unable to ask the assistant"));
    } finally {
      setLoading(false);
    }
  };

  const connectVoice = async () => {
    setError("");
    setVoiceState("connecting");
    try {
      const result = await createVoiceSession({ conversation_id: conversationId || undefined, mode });
      if (!result.configured) {
        setVoiceState("unavailable");
        setVoiceTranscript(result.message || "OpenAI Voice is not configured");
        return;
      }
      const clientSecret = result.realtime?.value || result.realtime?.client_secret?.value || result.realtime?.client_secret;
      if (!clientSecret) {
        setVoiceState("error");
        setError("Realtime credential response did not include a short-lived client secret.");
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia || typeof RTCPeerConnection === "undefined") {
        setVoiceState("unavailable");
        setVoiceTranscript("Voice requires browser microphone and WebRTC support.");
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const pc = new RTCPeerConnection();
      const dc = pc.createDataChannel("oai-events");
      stream.getAudioTracks().forEach((track) => pc.addTrack(track, stream));
      pc.ontrack = (event) => {
        const audio = new Audio();
        audio.autoplay = true;
        audio.srcObject = event.streams[0];
      };
      dc.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type?.includes("transcript")) setVoiceTranscript((prev) => `${prev}\n${data.transcript || data.delta || ""}`.trim());
          if (data.type === "response.audio.delta") setVoiceState("speaking");
          if (data.type === "input_audio_buffer.speech_started") setVoiceState("listening");
          if (data.type === "response.done") setVoiceState("listening");
        } catch {
          setVoiceTranscript((prev) => `${prev}\n${event.data}`.trim());
        }
      };
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      const sdp = await fetch(`https://api.openai.com/v1/realtime/calls?model=${encodeURIComponent(result.model)}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${clientSecret}`, "Content-Type": "application/sdp" },
        body: offer.sdp,
      });
      if (!sdp.ok) throw new Error("Realtime WebRTC answer failed");
      await pc.setRemoteDescription({ type: "answer", sdp: await sdp.text() });
      rtcRef.current = { pc, stream, dc };
      setVoiceState("listening");
    } catch (err) {
      setVoiceState("error");
      setError(err.message || "Unable to connect voice");
    }
  };

  const disconnectVoice = () => {
    rtcRef.current.dc?.close?.();
    rtcRef.current.pc?.close?.();
    rtcRef.current.stream?.getTracks?.().forEach((track) => track.stop());
    rtcRef.current = { pc: null, stream: null, dc: null };
    setVoiceState("idle");
  };

  const interruptVoice = () => {
    try {
      rtcRef.current.dc?.send?.(JSON.stringify({ type: "response.cancel" }));
    } catch { /* best effort */ }
    setVoiceState("interrupted");
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
                  {item.content_text}
                </div>
              ))}
            </div>
            <SourceList sources={sources} />
            <div className="grid gap-2 md:grid-cols-[1fr_auto]">
              <Textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ask the Business Assistant..." rows={3} data-testid="assistant-message-input" />
              <Button onClick={submit} disabled={loading || !message.trim()} data-testid="assistant-send"><Send className="mr-2 size-4" />Send</Button>
            </div>
          </CardContent>
        </Card>

        {proposals.map((proposal) => (
          <ProposalCard key={proposal.id} proposal={proposal} onUpdated={(next) => setProposals((prev) => prev.map((item) => (item.id === next.id || item.id === next.proposal_id ? { ...item, ...next } : item)))} />
        ))}
      </section>

      <aside className="space-y-4">
        <Card data-testid="assistant-voice">
          <CardHeader><CardTitle className="flex items-center justify-between text-base"><span className="flex items-center gap-2"><Mic className="size-5" />Voice</span><Badge>{VOICE_STATES[voiceState]}</Badge></CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <Button variant={pushToTalk ? "default" : "outline"} onClick={() => { setPushToTalk(true); setVadEnabled(false); }}><Mic className="mr-2 size-4" />Push</Button>
              <Button variant={vadEnabled ? "default" : "outline"} onClick={() => { setVadEnabled(true); setPushToTalk(false); }}><Volume2 className="mr-2 size-4" />VAD</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={connectVoice} disabled={voiceState === "connecting" || voiceState === "listening"} data-testid="assistant-voice-connect"><Mic className="mr-2 size-4" />Start</Button>
              <Button size="sm" variant="outline" onClick={interruptVoice} disabled={!["listening", "speaking", "thinking"].includes(voiceState)}><Pause className="mr-2 size-4" />Interrupt</Button>
              <Button size="sm" variant="outline" onClick={disconnectVoice}><Square className="mr-2 size-4" />End</Button>
            </div>
            {!voiceConfig?.configured && (
              <Alert data-testid="assistant-voice-unconfigured">
                <MicOff className="size-4" />
                <AlertTitle>OpenAI Voice is not configured</AlertTitle>
                <AlertDescription>Text assistant remains available.</AlertDescription>
              </Alert>
            )}
            <Textarea readOnly rows={6} value={voiceTranscript} placeholder="Voice transcript" data-testid="assistant-voice-transcript" />
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}

function SparklesIcon() {
  return <Bot className="size-4" />;
}
