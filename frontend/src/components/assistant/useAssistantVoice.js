import { useLayoutEffect, useRef, useState } from "react";
import { createVoiceSession, getVoiceSession, interruptVoiceSession, stopVoiceSession } from "@/lib/businessAssistant";

const empty = { state: "off", error: "", active: false, muted: false };
const terminal = ["ended", "failed", "recovery_required"];
const endReasons = {
  duration_limit: "The session time limit was reached.", idle_limit: "The session ended after a period of inactivity.",
  response_limit: "The session response limit was reached.", input_turn_limit: "The session question limit was reached.",
  access_or_budget_changed: "Your access or the shop's AI budget changed.", client_disconnected: "The browser connection was lost.",
  usage_incomplete: "Provider usage could not be confirmed, so voice stopped safely.",
  reserved_cost_exceeded: "The session spending allowance was reached.", provider_failure: "The voice provider connection failed.",
  provider_error: "The voice provider reported an error.", sideband_disconnected: "The server lost its voice control connection.",
  transcription_failed: "Speech could not be transcribed.",
};

// Shared with the existing authenticated conversation owner, not either panel.
export default function useAssistantVoice(identity, callbacks) {
  const [view, setView] = useState(empty);
  const current = useRef({ epoch: 0, sessionId: null, pc: null, stream: null, audio: null, timer: null, starting: false });
  const handlers = useRef(callbacks);
  handlers.current = callbacks;
  const cleanup = () => {
    const r = current.current;
    r.epoch += 1; r.starting = false;
    clearTimeout(r.timer);
    if (r.pc) { r.pc.ontrack = null; r.pc.onconnectionstatechange = null; r.pc.close(); }
    r.stream?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
    if (r.audio) { r.audio.pause(); r.audio.srcObject = null; r.audio.removeAttribute("src"); r.audio.load(); }
    r.pc = r.stream = r.audio = null;
  };
  useLayoutEffect(() => {
    const owned = current.current;
    setView(empty);
    return () => {
      const id = owned.sessionId;
      cleanup(); owned.sessionId = null;
      if (id) stopVoiceSession(id).catch(() => {});
    };
  }, [identity]);

  const end = async () => {
    const id = current.current.sessionId;
    cleanup();
    const epoch = current.current.epoch;
    setView({ ...empty, state: id ? "ending" : "off" });
    if (!id) return;
    let result;
    try { result = await stopVoiceSession(id); }
    finally { if (current.current.epoch === epoch) await handlers.current.refresh(); }
    if (current.current.epoch !== epoch) return;
    if (!terminal.includes(result.status)) throw new Error("Voice is still ending safely. Try text again after the session closes.");
    current.current.sessionId = null;
    setView(empty);
  };
  const fail = async (message, epoch) => {
    if (current.current.epoch !== epoch) return;
    try { await end(); } catch { /* Server watchdog/recovery retains control and reservations. */ }
    if (current.current.epoch !== epoch + 1) return;
    setView({ ...empty, state: "error", error: message });
  };
  const start = async (context, mode) => {
    const r = current.current;
    if (r.starting || r.pc) return;
    if (r.sessionId) await end();
    cleanup(); r.starting = true;
    const epoch = r.epoch;
    const valid = () => r.epoch === epoch;
    setView({ ...empty, state: "connecting", active: true });
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof RTCPeerConnection === "undefined") throw new Error("Voice requires a microphone, WebRTC and HTTPS or localhost. Text remains available.");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!valid()) { stream.getTracks().forEach((track) => track.stop()); return; }
      r.stream = stream;
      stream.getAudioTracks().forEach((track) => { track.enabled = false; track.onended = () => fail("Microphone disconnected. Reconnect your device or continue in text.", epoch); });
      const conversationId = await handlers.current.ensureConversation();
      if (!valid()) return;
      const pc = new RTCPeerConnection(); r.pc = pc;
      const audio = new Audio(); r.audio = audio;
      pc.ontrack = (event) => {
        audio.srcObject = event.streams[0];
        audio.play().catch(() => fail("Speaker playback was blocked. Check your speaker/browser settings; text remains available.", epoch));
      };
      stream.getAudioTracks().forEach((track) => pc.addTrack(track, stream));
      // Intentionally no data channel. Backend is the only Realtime controller.
      const offer = await pc.createOffer(); await pc.setLocalDescription(offer);
      if (!valid()) return;
      const result = await createVoiceSession({ conversation_id: conversationId, mode, context, offer_sdp: offer.sdp, idempotency_key: window.crypto?.randomUUID?.() || `voice-${Date.now()}-${Math.random().toString(36).slice(2)}` });
      if (!valid()) { if (result.session_id) stopVoiceSession(result.session_id).catch(() => {}); return; }
      r.sessionId = result.session_id;
      if (!result.configured || !result.session_id || !result.answer_sdp) throw new Error("Voice could not connect. Text remains available.");
      await pc.setRemoteDescription({ type: "answer", sdp: result.answer_sdp });
      if (!valid()) return;
      stream.getAudioTracks().forEach((track) => { track.enabled = true; });
      pc.onconnectionstatechange = () => {
        if (["failed", "disconnected", "closed"].includes(pc.connectionState)) fail("Voice connection ended. Reconnect explicitly or continue in text; your conversation is saved.", epoch);
      };
      let revision = -1;
      const poll = async () => {
        if (!valid()) return;
        try {
          const snapshot = await getVoiceSession(r.sessionId);
          if (!valid()) return;
          if (snapshot.revision !== revision) { revision = snapshot.revision; await handlers.current.refresh(); }
          if (!valid()) return;
          if (terminal.includes(snapshot.status)) {
            cleanup(); r.sessionId = null;
            setView({ ...empty, state: "ended", error: snapshot.reason === "user_ended" ? "" : `${endReasons[snapshot.reason] || "Voice ended safely. Reconnect explicitly to try again."} Text remains available.` });
            return;
          }
          setView((old) => ({ ...old, active: true, state: snapshot.state || "listening" }));
          r.timer = setTimeout(poll, 1000);
        } catch (err) {
          if ([401, 403].includes(err?.response?.status)) handlers.current.clear?.();
          await fail("Voice status is unavailable. The server will end the session safely; text remains available after cleanup.", epoch);
        }
      };
      r.starting = false;
      await poll();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const message = ["NotAllowedError", "PermissionDeniedError"].includes(err?.name) ? "Microphone permission denied. Allow it in your browser or use text." : (typeof detail === "string" ? detail : err.message) || "Voice connection failed; text remains available.";
      await fail(message, epoch);
    }
  };
  const interrupt = async () => {
    if (!current.current.sessionId) return;
    await interruptVoiceSession(current.current.sessionId);
    setView((old) => ({ ...old, state: "interrupted" }));
  };
  const mute = () => {
    const muted = !view.muted;
    current.current.stream?.getAudioTracks().forEach((track) => { track.enabled = !muted; });
    setView((old) => ({ ...old, muted }));
  };
  return { ...view, start, end, interrupt, mute, hasSession: () => !!current.current.sessionId };
}
