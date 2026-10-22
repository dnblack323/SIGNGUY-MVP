import React from "react";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import VoicePreview from "@/components/assistant/VoicePreview";
import VoiceReadiness from "@/components/assistant/VoiceReadiness";
import AssistantSettings from "@/components/assistant/AssistantSettings";
import * as api from "@/lib/businessAssistant";

let mockUser = { id: "u1", tenant_id: "t1", role: "owner" };
jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ user: mockUser, permissions: ["ai_assistant:use"] }) }));
jest.mock("@/lib/businessAssistant", () => ({ getAssistantPreferences: jest.fn(), saveAssistantPreferences: jest.fn() }));
const voices = ["alloy", "ash", "coral", "echo", "sage", "shimmer"].map((key) => ({ key, name: key[0].toUpperCase() + key.slice(1), preview_path: `/assistant-voice-samples/${key}.wav` }));
const originalAudio = global.Audio;
const originalDevices = navigator.mediaDevices;
let players;
beforeEach(() => {
  jest.resetAllMocks(); players = [];
  mockUser = { id: "u1", tenant_id: "t1", role: "owner" };
  global.Audio = jest.fn().mockImplementation((src) => {
    const audio = { src, play: jest.fn().mockResolvedValue(), pause: jest.fn(), removeAttribute: jest.fn(), load: jest.fn() };
    players.push(audio); return audio;
  });
});
afterEach(() => {
  global.Audio = originalAudio;
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: originalDevices });
  jest.useRealTimers();
});

test("every bundled voice previews on click without selecting, generating or overlapping audio", async () => {
  const user = userEvent.setup(); const select = jest.fn();
  const view = renderWithProviders(<VoicePreview voices={voices} selected="alloy" onSelect={select} />);
  expect(global.Audio).not.toHaveBeenCalled();
  for (const voice of voices) {
    await user.click(screen.getByRole("button", { name: `Preview ${voice.name}` }));
    expect(players.at(-1).src).toBe(voice.preview_path);
    expect(players.at(-1).play).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("status")).toHaveTextContent(`Playing ${voice.name}`);
  }
  expect(players.slice(0, -1).every((p) => p.pause.mock.calls.length === 1)).toBe(true);
  expect(select).not.toHaveBeenCalled();
  await user.click(screen.getByRole("radio", { name: "Ash" }));
  expect(select).toHaveBeenCalledWith("ash");
  view.unmount(); expect(players.at(-1).pause).toHaveBeenCalledTimes(1);
});

test("stop and media failure leave a retryable preview", async () => {
  const user = userEvent.setup();
  renderWithProviders(<VoicePreview voices={voices} selected="alloy" />);
  await user.click(screen.getByRole("button", { name: "Preview Alloy" }));
  await user.click(screen.getByRole("button", { name: "Stop Alloy" }));
  expect(screen.getByRole("status")).toHaveTextContent("stopped");
  await user.click(screen.getByRole("button", { name: "Preview Ash" }));
  act(() => players.at(-1).onerror());
  expect(screen.getByRole("alert")).toHaveTextContent("No AI request was made");
  await user.click(screen.getByRole("button", { name: "Preview Ash" }));
  act(() => players.at(-1).onended());
  expect(screen.getByRole("status")).toHaveTextContent("stopped");
});

test("a late play rejection cannot stop a newer sample", async () => {
  const user = userEvent.setup(); let rejectOld;
  global.Audio.mockImplementationOnce((src) => {
    const audio = { src, play: () => new Promise((resolve, reject) => { rejectOld = reject; }), pause: jest.fn(), removeAttribute: jest.fn(), load: jest.fn() };
    players.push(audio); return audio;
  });
  renderWithProviders(<VoicePreview voices={voices} />);
  await user.click(screen.getByRole("button", { name: "Preview Alloy" }));
  await user.click(screen.getByRole("button", { name: "Preview Ash" }));
  await act(async () => rejectOld(new Error("superseded")));
  expect(screen.getByRole("status")).toHaveTextContent("Playing Ash");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

function microphone(result) {
  const track = { enabled: true, stop: jest.fn() };
  const stream = { getTracks: () => [track], getAudioTracks: () => [track] };
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: jest.fn().mockImplementation(result || (() => Promise.resolve(stream))) } });
  return { track, stream };
}

test("microphone check never transmits and releases on end, fallback and unmount", async () => {
  const user = userEvent.setup(); const fallback = jest.fn(); const { track } = microphone();
  const view = renderWithProviders(<VoiceReadiness preferences={{ voices, effective_voice: "alloy" }} onUseText={fallback} />);
  expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Test microphone" }));
  expect(await screen.findByText(/Microphone ready/)).toBeInTheDocument();
  expect(track.enabled).toBe(false);
  await user.click(screen.getByRole("button", { name: "End microphone check" }));
  expect(track.stop).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole("button", { name: "Test microphone" }));
  await user.click(screen.getByRole("button", { name: "Use text instead" }));
  expect(track.stop).toHaveBeenCalledTimes(2); expect(fallback).toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Test microphone" }));
  view.unmount(); expect(track.stop).toHaveBeenCalledTimes(3);
});

test("ending while permission is pending stops late media and cannot reactivate the mic", async () => {
  const user = userEvent.setup(); let resolve;
  const { track, stream } = microphone(() => new Promise((done) => { resolve = done; }));
  renderWithProviders(<VoiceReadiness />);
  await user.click(screen.getByRole("button", { name: "Test microphone" }));
  await user.click(screen.getByRole("button", { name: "End microphone check" }));
  await act(async () => resolve(stream));
  expect(track.stop).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/Connection:/)).toHaveTextContent("Microphone off");
});

test("microphone denial, missing browser support and timeout keep text available", async () => {
  microphone(() => Promise.reject(Object.assign(new Error(), { name: "NotAllowedError" })));
  const view = renderWithProviders(<VoiceReadiness />);
  fireEvent.click(screen.getByRole("button", { name: "Test microphone" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("permission was denied");
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
  fireEvent.click(screen.getByRole("button", { name: "Test microphone" }));
  expect(screen.getByRole("alert")).toHaveTextContent("HTTPS or localhost");
  const { track } = microphone(); jest.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "Test microphone" }));
  await waitFor(() => expect(screen.getByText(/Connection:/)).toHaveTextContent("Microphone ready"));
  act(() => jest.advanceTimersByTime(30000));
  expect(track.stop).toHaveBeenCalledTimes(1);
  view.unmount();
});

test("voice settings save independently, survive remount and clear for another employee", async () => {
  const user = userEvent.setup();
  const original = { voices, effective_voice: "alloy", options: [{ key: "sarcastic_funny", name: "Sarcastic & Funny" }], preferences: { voice: null, personality_key: "sarcastic_funny", timezone: "UTC", response_length: "concise" } };
  const saved = { ...original, effective_voice: "ash", preferences: { ...original.preferences, voice: "ash" } };
  api.getAssistantPreferences.mockResolvedValue(original);
  api.saveAssistantPreferences.mockRejectedValueOnce(new Error("offline")).mockResolvedValue(saved);
  let view = renderWithProviders(<AssistantSettings />);
  await user.click(await screen.findByRole("radio", { name: "Ash" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("not saved");
  expect(screen.getByRole("radio", { name: "Alloy" })).toBeChecked();
  await user.click(screen.getByRole("radio", { name: "Ash" }));
  await waitFor(() => expect(screen.getByRole("radio", { name: "Ash" })).toBeChecked());
  expect(api.saveAssistantPreferences).toHaveBeenLastCalledWith({ voice: "ash" });
  expect(screen.getByRole("radio", { name: "Sarcastic & Funny" })).toBeChecked();
  view.unmount(); api.getAssistantPreferences.mockResolvedValue(saved);
  view = renderWithProviders(<AssistantSettings />);
  expect(await screen.findByRole("radio", { name: "Ash" })).toBeChecked();
  mockUser = { id: "u2", tenant_id: "t2", role: "owner" };
  api.getAssistantPreferences.mockResolvedValue(original);
  view.rerender(<AssistantSettings />);
  expect(await screen.findByRole("radio", { name: "Alloy" })).toBeChecked();
});
