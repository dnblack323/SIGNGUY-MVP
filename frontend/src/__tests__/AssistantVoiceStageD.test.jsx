import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import useAssistantVoice from "@/components/assistant/useAssistantVoice";
import * as api from "@/lib/businessAssistant";
import { AssistantProvider, useAssistantSession } from "@/components/assistant/AssistantSession";

jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ user: { id: "u1", tenant_id: "t1", role: "owner" } }) }));
jest.mock("@/lib/businessAssistant", () => ({ createVoiceSession: jest.fn(), getVoiceSession: jest.fn(), stopVoiceSession: jest.fn(), interruptVoiceSession: jest.fn(), createAssistantConversation: jest.fn(), getAssistantConversation: jest.fn(), getAssistantPreferences: jest.fn(), listAssistantConversations: jest.fn(), sendAssistantMessage: jest.fn() }));
let voice;
const ensureConversation = jest.fn();
const refresh = jest.fn();
const clear = jest.fn();
function Probe({ identity = "shop:employee" }) {
  voice = useAssistantVoice(identity, { ensureConversation, refresh, clear });
  return <><p data-testid="state">{voice.state} {voice.error}</p><button onClick={() => voice.start({ source_type: "order", source_id: "o1" }, "operations")}>Start</button><button onClick={voice.end}>End</button><button onClick={voice.mute}>Mute</button><button onClick={voice.interrupt}>Interrupt</button></>;
}
let track, pc;
const originalRtc = global.RTCPeerConnection;
const originalAudio = global.Audio;
const originalMedia = navigator.mediaDevices;
beforeEach(() => {
  jest.resetAllMocks();
  track = { enabled: true, stop: jest.fn() };
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [track], getAudioTracks: () => [track] }) } });
  pc = { createOffer: jest.fn().mockResolvedValue({ type: "offer", sdp: "v=0\r\nm=audio" }), addTrack: jest.fn(), setLocalDescription: jest.fn(), setRemoteDescription: jest.fn(), close: jest.fn() };
  global.RTCPeerConnection = jest.fn(() => pc);
  global.Audio = jest.fn(() => ({ play: jest.fn().mockResolvedValue(), pause: jest.fn(), load: jest.fn(), removeAttribute: jest.fn() }));
  ensureConversation.mockResolvedValue("c1"); refresh.mockResolvedValue();
  api.createVoiceSession.mockResolvedValue({ configured: true, session_id: "s1", answer_sdp: "answer" });
  api.getVoiceSession.mockResolvedValue({ status: "active", state: "listening", revision: 1 });
  api.stopVoiceSession.mockResolvedValue({ status: "ended" });
  api.interruptVoiceSession.mockResolvedValue({ status: "interrupting" });
});
afterEach(() => { global.RTCPeerConnection = originalRtc; global.Audio = originalAudio; Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: originalMedia }); });

test("media-only WebRTC uses shared conversation, backend status and transcript refresh", async () => {
  render(<Probe />);
  fireEvent.click(screen.getByText("Start")); fireEvent.click(screen.getByText("Start"));
  await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("listening"));
  expect(api.createVoiceSession).toHaveBeenCalledTimes(1);
  expect(api.createVoiceSession).toHaveBeenCalledWith(expect.objectContaining({ conversation_id: "c1", context: { source_type: "order", source_id: "o1" }, offer_sdp: "v=0\r\nm=audio", mode: "operations" }));
  expect(pc.createDataChannel).toBeUndefined();
  expect(pc.setRemoteDescription).toHaveBeenCalledWith({ type: "answer", sdp: "answer" });
  expect(refresh).toHaveBeenCalledTimes(1);
  expect(track.enabled).toBe(true);
  fireEvent.click(screen.getByText("Mute")); expect(track.enabled).toBe(false);
  fireEvent.click(screen.getByText("Interrupt"));
  await waitFor(() => expect(api.interruptVoiceSession).toHaveBeenCalledWith("s1"));
  fireEvent.click(screen.getByText("End"));
  await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("off"));
  expect(track.stop).toHaveBeenCalled(); expect(pc.close).toHaveBeenCalled();
  expect(api.stopVoiceSession).toHaveBeenCalledWith("s1");
});

test("denied microphone preserves text fallback without a paid dispatch", async () => {
  navigator.mediaDevices.getUserMedia.mockRejectedValue({ name: "NotAllowedError" });
  render(<Probe />); fireEvent.click(screen.getByText("Start"));
  await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("Microphone permission denied"));
  expect(api.createVoiceSession).not.toHaveBeenCalled();
});

test("pending remote termination immediately stops local media and prevents another dispatch", async () => {
  api.getVoiceSession.mockResolvedValue({ status: "termination_pending", state: "ending", revision: 1 });
  render(<Probe />); fireEvent.click(screen.getByText("Start"));
  await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("Microphone and speaker stopped"));
  expect(track.stop).toHaveBeenCalled(); expect(pc.close).toHaveBeenCalled();
  expect(voice.active).toBe(false); expect(voice.hasSession()).toBe(true);
  api.stopVoiceSession.mockResolvedValue({ status: "ending" });
  await act(async () => { await expect(voice.start({}, "owner")).rejects.toThrow("still ending safely"); });
  expect(api.createVoiceSession).toHaveBeenCalledTimes(1);
});

test("identity change stops the owned session and clears prior state", async () => {
  const { rerender } = render(<Probe />); fireEvent.click(screen.getByText("Start"));
  await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("listening"));
  rerender(<Probe identity="other:employee" />);
  expect(screen.getByTestId("state")).toHaveTextContent("off");
  expect(api.stopVoiceSession).toHaveBeenCalledWith("s1"); expect(track.stop).toHaveBeenCalled();
});

test("late admission after logout is terminated without exposing previous session", async () => {
  let resolve;
  api.createVoiceSession.mockImplementation(() => new Promise((done) => { resolve = done; }));
  const { rerender } = render(<Probe />); fireEvent.click(screen.getByText("Start"));
  await waitFor(() => expect(api.createVoiceSession).toHaveBeenCalled());
  rerender(<Probe identity="other:employee" />);
  await act(async () => resolve({ configured: true, session_id: "late", answer_sdp: "answer" }));
  expect(api.stopVoiceSession).toHaveBeenCalledWith("late");
  expect(screen.getByTestId("state")).toHaveTextContent("off");
  expect(pc.setRemoteDescription).not.toHaveBeenCalled();
});

test("connection failure ends session and permits explicit reconnect only", async () => {
  render(<Probe />); fireEvent.click(screen.getByText("Start"));
  await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("listening"));
  await act(async () => { pc.connectionState = "failed"; pc.onconnectionstatechange(); });
  await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("Reconnect explicitly"));
  expect(api.createVoiceSession).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByText("Start"));
  await waitFor(() => expect(api.createVoiceSession).toHaveBeenCalledTimes(2));
});

test("one provider owns voice across panel remounts and refreshes transcripts before text", async () => {
  localStorage.clear();
  api.getAssistantPreferences.mockResolvedValue({ preferences: {} }); api.listAssistantConversations.mockResolvedValue([]);
  api.createAssistantConversation.mockResolvedValue({ id: "c1" });
  const spoken = { id: "spoken", role: "assistant", content_text: "Saved spoken answer" };
  api.getAssistantConversation.mockResolvedValue({ messages: [spoken] });
  api.sendAssistantMessage.mockResolvedValue({ user_message: { id: "typed", role: "user", content_text: "Follow up" }, assistant_message: { id: "reply", role: "assistant", content_text: "Typed continuation" } });
  function Panel() {
    const session = useAssistantSession();
    const { activate } = session;
    React.useEffect(() => activate(), [activate]);
    return <><button disabled={!session.ready} onClick={() => session.voice.start({}, "owner")}>Speak shared</button><button onClick={() => session.setMessage("Follow up")}>Prepare text</button><button onClick={() => session.send({})}>Send shared</button><p>{session.messages.map((m) => m.content_text).join(" | ")}</p><p>{session.voice.state}</p></>;
  }
  function Harness() { const [surface, setSurface] = React.useState(0); return <><button onClick={() => setSurface(surface + 1)}>Switch surface</button><Panel key={surface} /></>; }
  render(<AssistantProvider><Harness /></AssistantProvider>);
  await waitFor(() => expect(screen.getByText("Speak shared")).toBeEnabled());
  fireEvent.click(screen.getByText("Speak shared"));
  await screen.findByText("listening");
  fireEvent.click(screen.getByText("Switch surface"));
  expect(screen.getByText("listening")).toBeInTheDocument();
  expect(api.createVoiceSession).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByText("Prepare text")); fireEvent.click(screen.getByText("Send shared"));
  await screen.findByText(/Saved spoken answer.*Typed continuation/);
  expect(api.stopVoiceSession).toHaveBeenCalledWith("s1");
  expect(api.sendAssistantMessage).toHaveBeenCalledWith(expect.objectContaining({ conversation_id: "c1", message: "Follow up" }));
});

test("permission failure clears cached conversation and stops voice", async () => {
  api.getVoiceSession.mockRejectedValue({ response: { status: 403 } });
  render(<Probe />); fireEvent.click(screen.getByText("Start"));
  await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("Voice status is unavailable"));
  expect(clear).toHaveBeenCalled();
  expect(api.stopVoiceSession).toHaveBeenCalledWith("s1");
  expect(refresh).toHaveBeenCalled();
});
