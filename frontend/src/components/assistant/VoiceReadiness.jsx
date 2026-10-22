import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import VoicePreview from "./VoicePreview";

export default function VoiceReadiness({ preferences, onUseText }) {
  const stream = useRef(null);
  const generation = useRef(0);
  const timer = useRef(null);
  const [state, setState] = useState("Microphone off");
  const [error, setError] = useState("");
  const release = () => {
    generation.current += 1;
    clearTimeout(timer.current);
    stream.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
    stream.current = null;
  };
  useEffect(() => () => release(), []);
  const end = () => { release(); setState("Microphone off"); };
  const start = async () => {
    release(); setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setState("Microphone unavailable");
      setError("Microphone access needs a supported browser and HTTPS or localhost. Text remains available.");
      return;
    }
    const current = generation.current;
    setState("Waiting for microphone permission");
    try {
      const next = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (current !== generation.current) { next.getTracks().forEach((track) => track.stop()); return; }
      stream.current = next;
      next.getAudioTracks().forEach((track) => {
        track.enabled = false;
        track.onended = () => { if (current === generation.current) { end(); setError("Microphone disconnected. You can test it again or continue in text."); } };
      });
      setState("Microphone ready · audio is not sent");
      timer.current = setTimeout(() => { if (current === generation.current) end(); }, 30000);
    } catch (err) {
      if (current !== generation.current) return;
      setState("Microphone unavailable");
      setError(err?.name === "NotAllowedError" || err?.name === "PermissionDeniedError"
        ? "Microphone permission was denied. Allow microphone access in your browser, then try again. Text remains available."
        : "No available microphone could be opened. Check your device and try again. Text remains available.");
    }
  };
  return <div className="space-y-3" data-testid="assistant-voice-readiness">
    <p role="status">Connection: not connected. {state}.</p>
    <p className="text-sm">Live voice conversations are not available yet. You can choose a voice and check microphone access. This check does not listen to or send speech.</p>
    {error && <p role="alert">{error}</p>}
    <VoicePreview key={preferences?.preferences?.voice || "default"} voices={preferences?.voices || []} selected={preferences?.effective_voice || "alloy"} compact />
    <Link className="underline text-sm" to="/settings/assistant">Voice settings</Link>
    <div className="flex flex-wrap gap-2">
      <Button size="sm" onClick={start} disabled={state.startsWith("Waiting") || !!stream.current}>Test microphone</Button>
      <Button size="sm" variant="outline" onClick={end}>End microphone check</Button>
      <Button size="sm" variant="link" onClick={() => { end(); onUseText?.(); }}>Use text instead</Button>
    </div>
  </div>;
}
