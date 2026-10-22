import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAssistantSession } from "./AssistantSession";
import VoiceReadiness from "./VoiceReadiness";
import VoicePreview from "./VoicePreview";

export default function VoiceConversation({ config, context }) {
  const session = useAssistantSession();
  const voice = session.voice;
  const [error, setError] = useState("");
  const act = (operation) => { setError(""); Promise.resolve(operation()).catch((err) => setError(err.message || "Voice control failed. Text remains available.")); };
  if (!config?.interactions_available) return <VoiceReadiness key={session.identity} preferences={session.preferences} onUseText={() => document.querySelector('[data-testid="assistant-message-input"]')?.focus()} />;
  return <div className="space-y-3" data-testid="assistant-voice-conversation">
    <p role="status">Connection: {voice.state}. Microphone: {voice.active && !voice.muted ? "on" : "off"}.</p>
    <p className="text-sm">AI-generated speech. Voice uses the same private conversation, permitted shop tools and saved personality as text. Audio is sent to OpenAI; transcripts are saved here. Raw audio is not stored by this application.</p>
    <p className="text-sm">Session limit: {config.max_seconds} seconds; idle limit: {config.idle_seconds} seconds. AI credits apply. Reconnect starts a new bounded session.</p>
    {(voice.error || error) && <p role="alert">{voice.error || error}</p>}
    <VoicePreview voices={session.preferences?.voices || []} selected={session.preferences?.effective_voice || "alloy"} compact />
    <Link className="underline text-sm" to="/settings/assistant">Voice and personality settings</Link>
    <p className="text-sm">Saved setting changes apply after ending and reconnecting voice; your history is preserved.</p>
    <div className="flex flex-wrap gap-2">
      <Button size="sm" onClick={() => act(() => voice.start(context, session.mode))} disabled={voice.active || session.loading || !session.ready} data-testid="assistant-voice-connect">{["error", "ended"].includes(voice.state) ? "Reconnect voice" : "Start voice"}</Button>
      <Button size="sm" variant="outline" onClick={voice.mute} disabled={!voice.active}>{voice.muted ? "Unmute" : "Mute"}</Button>
      <Button size="sm" variant="outline" onClick={() => act(voice.interrupt)} disabled={!voice.active}>Interrupt</Button>
      <Button size="sm" variant="outline" onClick={() => act(voice.end)}>End voice</Button>
      <Button size="sm" variant="link" onClick={() => act(async () => { await voice.end(); document.querySelector('[data-testid="assistant-message-input"]')?.focus(); })}>Use text instead</Button>
    </div>
    <p className="text-sm">Voice transcripts appear in the conversation above with record links. Interrupted generated text is labelled and excluded from future model context.</p>
  </div>;
}
