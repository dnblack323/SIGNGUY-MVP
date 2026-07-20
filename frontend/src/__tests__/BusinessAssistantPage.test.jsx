import React from "react";
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";

jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({
    hasPerm: (perm) => perm === "ai_assistant:use" || perm === "ai_prompt:read",
    user: { id: "u1", tenant_id: "t1", role: "owner" },
  }),
}));

jest.mock("@/lib/businessAssistant", () => ({
  __esModule: true,
  getAssistantCatalog: jest.fn(),
  getVoiceConfig: jest.fn(),
  sendAssistantMessage: jest.fn(),
  proposeAssistantAction: jest.fn(),
  createVoiceSession: jest.fn(),
  recordVoiceUsage: jest.fn(),
  listAssistantQuickActions: jest.fn(),
  createStudioDelegation: jest.fn(),
  confirmAssistantProposal: jest.fn(),
  cancelAssistantProposal: jest.fn(),
  executeAssistantProposal: jest.fn(),
  listAssistantMemory: jest.fn(),
  saveAssistantMemory: jest.fn(),
  deleteAssistantMemory: jest.fn(),
  listAssistantRoutines: jest.fn(),
  createAssistantRoutine: jest.fn(),
  updateAssistantRoutine: jest.fn(),
  disableAssistantRoutine: jest.fn(),
  enableAssistantRoutine: jest.fn(),
  deleteAssistantRoutine: jest.fn(),
  listAssistantInsights: jest.fn(),
  dismissAssistantInsight: jest.fn(),
}));

import {
  createVoiceSession,
  getAssistantCatalog,
  getVoiceConfig,
  listAssistantInsights,
  listAssistantMemory,
  listAssistantQuickActions,
  listAssistantRoutines,
  recordVoiceUsage,
  sendAssistantMessage,
} from "@/lib/businessAssistant";
import BusinessAssistantPage from "@/pages/BusinessAssistantPage";

const originalFetch = global.fetch;
const originalRtcPeerConnection = global.RTCPeerConnection;
const originalMediaDevices = global.navigator.mediaDevices;

beforeEach(() => {
  jest.clearAllMocks();
  getAssistantCatalog.mockResolvedValue({
    entitlement_feature_key: "business_assistant",
    credit_display: "AI credits apply",
    modes: [
      { mode_key: "owner", name: "Owner" },
      { mode_key: "operations", name: "Operations" },
      { mode_key: "finance", name: "Finance" },
      { mode_key: "production", name: "Production" },
      { mode_key: "workforce", name: "Workforce" },
    ],
  });
  getVoiceConfig.mockResolvedValue({
    provider: "openai",
    configured: false,
    enabled: false,
    model: "gpt-realtime-2.1",
    voice: "alloy",
    push_to_talk_default: true,
  });
  sendAssistantMessage.mockResolvedValue({
    conversation: { id: "conv-1" },
    user_message: { id: "msg-u", role: "user", content_text: "What is the latest invoice?" },
    assistant_message: { id: "msg-a", role: "assistant", content_text: "Latest invoice: 1201 for $425.00." },
    sources: [{ id: "src-1", source_type: "invoice", source_id: "inv-1", source_label: "Invoice 1201", route: "/invoices/inv-1" }],
  });
  createVoiceSession.mockResolvedValue({
    configured: false,
    status: "unavailable",
    message: "OpenAI Voice is not configured",
  });
  listAssistantQuickActions.mockResolvedValue([
    { label: "Latest invoice", prompt: "What is the latest invoice?", mode: "finance", required_permissions: ["invoice:read"] },
  ]);
  listAssistantMemory.mockResolvedValue([{ id: "mem-1", content_text: "Use concise updates." }]);
  listAssistantRoutines.mockResolvedValue([{ id: "routine-1", name: "Morning check", status: "active" }]);
  listAssistantInsights.mockResolvedValue([{ id: "insight-1", title: "Open invoices", summary: "One invoice needs review." }]);
});

afterEach(() => {
  global.fetch = originalFetch;
  global.RTCPeerConnection = originalRtcPeerConnection;
  Object.defineProperty(global.navigator, "mediaDevices", {
    configurable: true,
    value: originalMediaDevices,
  });
});

test("renders Business Assistant workspace with modes, text chat, sources, and voice state", async () => {
  const user = userEvent.setup();
  renderWithProviders(<BusinessAssistantPage />, { route: "/studio/assistant?context_type=invoice&context_id=inv-1" });

  expect(await screen.findByTestId("business-assistant-page")).toBeInTheDocument();
  await waitFor(() => expect(getAssistantCatalog).toHaveBeenCalled());
  expect(screen.getByTestId("assistant-context")).toHaveValue("invoice inv-1");
  await waitFor(() => expect(listAssistantQuickActions).toHaveBeenCalled());
  expect(screen.getByTestId("assistant-quick-actions")).toHaveTextContent("Latest invoice");
  expect(screen.getAllByText("AI credits apply").length).toBeGreaterThan(0);
  expect(screen.getByTestId("assistant-voice-unconfigured")).toHaveTextContent("OpenAI Voice is not configured");
  expect(await screen.findByTestId("assistant-memory")).toHaveTextContent("Use concise updates.");
  expect(await screen.findByDisplayValue("Morning check")).toBeInTheDocument();
  expect(await screen.findByTestId("assistant-insights")).toHaveTextContent("Open invoices");

  await user.type(screen.getByTestId("assistant-message-input"), "What is the latest invoice?");
  await user.click(screen.getByTestId("assistant-send"));

  await waitFor(() => expect(sendAssistantMessage).toHaveBeenCalled());
  expect(screen.getByTestId("assistant-history")).toHaveTextContent("Latest invoice: 1201");
  expect(screen.getByTestId("assistant-sources")).toHaveTextContent("Invoice 1201");

  await user.click(screen.getByTestId("assistant-voice-connect"));
  await waitFor(() => expect(createVoiceSession).toHaveBeenCalled());
  expect(screen.getByTestId("assistant-voice-transcript")).toHaveValue("OpenAI Voice is not configured");
  expect(screen.getByTestId("assistant-push-to-talk")).toBeInTheDocument();
  expect(screen.getByTestId("assistant-text-fallback")).toBeInTheDocument();
});

test("connects mocked WebRTC voice with push-to-talk, transcript, and usage metering", async () => {
  const user = userEvent.setup();
  const audioTrack = { enabled: true, stop: jest.fn() };
  const stream = { getAudioTracks: () => [audioTrack], getTracks: () => [audioTrack] };
  const addTrack = jest.fn();
  const setLocalDescription = jest.fn();
  const setRemoteDescription = jest.fn();
  let dataChannel;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, text: async () => "answer-sdp" });
  Object.defineProperty(global.navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: jest.fn().mockResolvedValue(stream) },
  });
  global.RTCPeerConnection = jest.fn().mockImplementation(() => ({
    addTrack,
    createDataChannel: jest.fn(() => {
      dataChannel = { readyState: "open", send: jest.fn(), close: jest.fn(), onopen: null, onmessage: null };
      return dataChannel;
    }),
    createOffer: jest.fn().mockResolvedValue({ type: "offer", sdp: "offer-sdp" }),
    setLocalDescription,
    setRemoteDescription,
    close: jest.fn(),
    connectionState: "connected",
  }));
  getVoiceConfig.mockResolvedValue({
    provider: "openai",
    configured: true,
    enabled: true,
    model: "gpt-realtime-2.1",
    voice: "alloy",
    push_to_talk_default: true,
    turn_detection: "server_vad",
  });
  createVoiceSession.mockResolvedValue({
    configured: true,
    model: "gpt-realtime-2.1",
    voice_session: { id: "voice-1" },
    realtime: { value: "eph-test" },
  });

  renderWithProviders(<BusinessAssistantPage />, { route: "/studio/assistant" });
  await screen.findByTestId("assistant-voice");
  await user.click(screen.getByTestId("assistant-voice-connect"));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/v1/realtime/calls"), expect.any(Object)));
  expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({ audio: true });
  expect(addTrack).toHaveBeenCalled();
  expect(audioTrack.enabled).toBe(false);

  dataChannel.onopen();
  await user.pointer([{ keys: "[MouseLeft>]", target: screen.getByTestId("assistant-push-to-talk") }, { keys: "[/MouseLeft]", target: screen.getByTestId("assistant-push-to-talk") }]);
  expect(dataChannel.send).toHaveBeenCalledWith(expect.stringContaining("input_audio_buffer.commit"));

  await act(async () => {
    await dataChannel.onmessage({ data: JSON.stringify({ type: "conversation.item.input_audio_transcription.completed", transcript: "hello" }) });
    await dataChannel.onmessage({ data: JSON.stringify({ type: "response.audio_transcript.done", transcript: "hi there" }) });
    await dataChannel.onmessage({ data: JSON.stringify({ type: "response.done", response: { id: "resp-1", usage: { input_token_details: { audio_tokens: 100 }, output_token_details: { audio_tokens: 50 } } } }) });
  });
  expect(await screen.findByDisplayValue(/You: hello/)).toBeInTheDocument();
  await waitFor(() => expect(recordVoiceUsage).toHaveBeenCalledWith("voice-1", expect.objectContaining({ provider_event_id: "resp-1" })));
});
