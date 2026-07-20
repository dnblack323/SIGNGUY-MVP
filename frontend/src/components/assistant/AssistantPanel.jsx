import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  createAssistantRoutine,
  createStudioDelegation,
  createVoiceSession,
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
  recordVoiceUsage,
  saveAssistantMemory,
  sendAssistantMessage,
  updateAssistantRoutine,
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
  microphone_denied: "Microphone denied",
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
  const [memoryItems, setMemoryItems] = useState([]);
  const [memoryDraft, setMemoryDraft] = useState("");
  const [routines, setRoutines] = useState([]);
  const [routineDraft, setRoutineDraft] = useState("");
  const [insights, setInsights] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [voiceState, setVoiceState] = useState("idle");
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const [voiceSessionId, setVoiceSessionId] = useState(null);
  const [pushToTalk, setPushToTalk] = useState(true);
  const [vadEnabled, setVadEnabled] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const rtcRef = useRef({ pc: null, stream: null, dc: null, reconnecting: false, voiceSessionId: null });

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

  const appendVoiceTranscript = (speaker, text) => {
    if (!text) return;
    setVoiceTranscript((prev) => `${prev ? `${prev}\n` : ""}${speaker}: ${text}`.trim());
  };

  const setAudioTracksEnabled = (enabled) => {
    rtcRef.current.stream?.getAudioTracks?.().forEach((track) => {
      track.enabled = enabled;
    });
  };

  const sendRealtimeEvent = (event) => {
    const dc = rtcRef.current.dc;
    if (dc?.readyState === "open") {
      dc.send(JSON.stringify(event));
    }
  };

  const updateRealtimeTurnDetection = (useVad) => {
    sendRealtimeEvent({
      type: "session.update",
      session: {
        turn_detection: useVad ? { type: voiceConfig?.turn_detection || "server_vad" } : null,
      },
    });
  };

  const proposeActionFromRealtime = async (args, callId) => {
    const payload = {
      action_type: args.action_type || "internal_task",
      title: args.title || "Assistant proposed action",
      summary: args.summary || "Review before anything changes.",
      body: args.body,
      route: args.route,
      target_refs: args.target_refs || [],
      mode,
      conversation_id: conversationId || undefined,
      idempotency_key: `voice-tool-${voiceSessionId || "pending"}-${callId || Date.now()}`,
      metering_idempotency_key: `voice-tool-meter-${voiceSessionId || "pending"}-${callId || Date.now()}`,
    };
    const proposal = await proposeAssistantAction(payload);
    setProposals((prev) => [proposal, ...prev.filter((item) => item.id !== proposal.id)]);
    sendRealtimeEvent({
      type: "conversation.item.create",
      item: {
        type: "function_call_output",
        call_id: callId,
        output: JSON.stringify({ proposal_id: proposal.id, status: proposal.status, message: "Proposal created and visible to the user. Explicit confirmation is required before execution." }),
      },
    });
    sendRealtimeEvent({ type: "response.create" });
  };

  const handleRealtimeEvent = async (data) => {
    if (data.type === "conversation.item.input_audio_transcription.completed") {
      appendVoiceTranscript("You", data.transcript);
      setVoiceState("thinking");
    }
    if (data.type === "response.audio_transcript.delta") {
      appendVoiceTranscript("Assistant", data.delta);
      setVoiceState("speaking");
    }
    if (data.type === "response.audio_transcript.done") {
      appendVoiceTranscript("Assistant", data.transcript);
    }
    if (data.type === "response.audio.delta") setVoiceState("speaking");
    if (data.type === "input_audio_buffer.speech_started") setVoiceState("listening");
    if (data.type === "response.done") {
      setVoiceState(pushToTalk ? "idle" : "listening");
      const usage = data.response?.usage;
      const activeVoiceSessionId = voiceSessionId || rtcRef.current.voiceSessionId;
      if (activeVoiceSessionId && data.response?.id) {
        recordVoiceUsage(activeVoiceSessionId, {
          provider_event_id: data.response.id,
          input_audio_seconds: Math.max(0, Math.round((usage?.input_token_details?.audio_tokens || 0) / 50)),
          output_audio_seconds: Math.max(0, Math.round((usage?.output_token_details?.audio_tokens || 0) / 50)),
        }).catch(() => {});
      }
    }
    const functionCall = data.item?.type === "function_call" ? data.item : data.response?.output?.find?.((item) => item.type === "function_call");
    if (functionCall?.name === "propose_assistant_action" && functionCall.arguments) {
      try {
        await proposeActionFromRealtime(JSON.parse(functionCall.arguments), functionCall.call_id);
      } catch (err) {
        setError(extractError(err, "Unable to create assistant proposal from voice"));
      }
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
      const nextVoiceSessionId = result.voice_session?.id || null;
      setVoiceSessionId(nextVoiceSessionId);
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
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (err) {
        if (err?.name === "NotAllowedError" || err?.name === "PermissionDeniedError") {
          setVoiceState("microphone_denied");
          setVoiceTranscript("Microphone permission was denied. Text assistant remains available.");
          return;
        }
        throw err;
      }
      const pc = new RTCPeerConnection();
      const dc = pc.createDataChannel("oai-events");
      stream.getAudioTracks().forEach((track) => pc.addTrack(track, stream));
      if (pushToTalk) {
        stream.getAudioTracks().forEach((track) => {
          track.enabled = false;
        });
      }
      pc.ontrack = (event) => {
        const audio = new Audio();
        audio.autoplay = true;
        audio.srcObject = event.streams[0];
      };
      dc.onopen = () => {
        updateRealtimeTurnDetection(vadEnabled);
        setVoiceState(pushToTalk ? "idle" : "listening");
      };
      dc.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          await handleRealtimeEvent(data);
        } catch {
          appendVoiceTranscript("Event", event.data);
        }
      };
      pc.onconnectionstatechange = () => {
        if (["failed", "disconnected"].includes(pc.connectionState)) {
          setVoiceState("reconnecting");
          setReconnectCount((count) => count + 1);
        }
        if (pc.connectionState === "connected") {
          setVoiceState(pushToTalk ? "idle" : "listening");
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
      rtcRef.current = { pc, stream, dc, reconnecting: false, voiceSessionId: nextVoiceSessionId };
      setVoiceState(pushToTalk ? "idle" : "listening");
    } catch (err) {
      setVoiceState("error");
      setError(err.message || "Unable to connect voice");
    }
  };

  const disconnectVoice = () => {
    rtcRef.current.dc?.close?.();
    rtcRef.current.pc?.close?.();
    rtcRef.current.stream?.getTracks?.().forEach((track) => track.stop());
    rtcRef.current = { pc: null, stream: null, dc: null, reconnecting: false, voiceSessionId: null };
    setVoiceState("idle");
  };

  const interruptVoice = () => {
    try {
      rtcRef.current.dc?.send?.(JSON.stringify({ type: "response.cancel" }));
    } catch { /* best effort */ }
    setVoiceState("interrupted");
  };

  const startPushToTalk = () => {
    if (!pushToTalk) return;
    setAudioTracksEnabled(true);
    setVoiceState("listening");
  };

  const stopPushToTalk = () => {
    if (!pushToTalk) return;
    setAudioTracksEnabled(false);
    sendRealtimeEvent({ type: "input_audio_buffer.commit" });
    sendRealtimeEvent({ type: "response.create" });
    setVoiceState("thinking");
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
              <Button variant={pushToTalk ? "default" : "outline"} onClick={() => { setPushToTalk(true); setVadEnabled(false); setAudioTracksEnabled(false); updateRealtimeTurnDetection(false); }}><Mic className="mr-2 size-4" />Push</Button>
              <Button variant={vadEnabled ? "default" : "outline"} onClick={() => { setVadEnabled(true); setPushToTalk(false); setAudioTracksEnabled(true); updateRealtimeTurnDetection(true); }}><Volume2 className="mr-2 size-4" />VAD</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={connectVoice} disabled={voiceState === "connecting" || voiceState === "listening"} data-testid="assistant-voice-connect"><Mic className="mr-2 size-4" />Start</Button>
              {pushToTalk && (
                <Button
                  size="sm"
                  variant="secondary"
                  onPointerDown={startPushToTalk}
                  onPointerUp={stopPushToTalk}
                  onPointerLeave={stopPushToTalk}
                  onKeyDown={(event) => { if (event.key === " " || event.key === "Enter") startPushToTalk(); }}
                  onKeyUp={(event) => { if (event.key === " " || event.key === "Enter") stopPushToTalk(); }}
                  data-testid="assistant-push-to-talk"
                >
                  <Mic className="mr-2 size-4" />Hold
                </Button>
              )}
              <Button size="sm" variant="outline" onClick={interruptVoice} disabled={!["listening", "speaking", "thinking"].includes(voiceState)}><Pause className="mr-2 size-4" />Interrupt</Button>
              {voiceState === "reconnecting" && <Button size="sm" variant="outline" onClick={connectVoice}>Retry {reconnectCount ? `(${reconnectCount})` : ""}</Button>}
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
            <Button size="sm" variant="link" onClick={() => setVoiceState("idle")} data-testid="assistant-text-fallback">Use text instead</Button>
          </CardContent>
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

function SparklesIcon() {
  return <Bot className="size-4" />;
}
