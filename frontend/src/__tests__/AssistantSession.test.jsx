import React, { useState } from "react";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import { AssistantProvider, useAssistantSession } from "@/components/assistant/AssistantSession";
import AssistantSettings from "@/components/assistant/AssistantSettings";
import * as api from "@/lib/businessAssistant";

let mockUser = { id: "u1", tenant_id: "t1", role: "owner" };
jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ user: mockUser, permissions: ["ai_assistant:use"] }) }));
jest.mock("@/lib/businessAssistant", () => ({
  createAssistantConversation: jest.fn(), getAssistantConversation: jest.fn(),
  getAssistantPreferences: jest.fn(), listAssistantConversations: jest.fn(),
  sendAssistantMessage: jest.fn(), saveAssistantPreferences: jest.fn(),
}));

const options = ["Sharp Ops Partner", "Wise Mentor", "Cheerful Helper", "No-BS Direct", "Sarcastic & Funny"].map((name, i) => ({
  name, key: ["ops_partner", "wise_mentor", "cheerful_helper", "no_bs_direct", "sarcastic_funny"][i],
  tagline: i === 4 ? "⚠️ Use at Your Own Risk" : "Useful shop coworker", description: "Accurate answers",
}));
const preferences = { options, preferences: { personality_key: "ops_partner", voice: "independent", timezone: "UTC", response_length: "concise" } };
const result = { conversation: { id: "c1" }, user_message: { id: "m1", role: "user", content_text: "Question" }, assistant_message: { id: "m2", role: "assistant", content_text: "Persisted useful answer" }, sources: [] };

function Probe() {
  const state = useAssistantSession();
  const { activate } = state;
  React.useEffect(() => activate(), [activate]);
  return <div><input aria-label="Question" value={state.message} onChange={(event) => state.setMessage(event.target.value)} />
    <button onClick={() => state.send({}).catch(() => {})} disabled={!state.ready}>Send probe</button>
    <button onClick={() => state.selectConversation(null)}>New probe</button>
    <p data-testid="probe-history">{state.messages.map((m) => m.content_text).join("\n")}</p>
  </div>;
}

beforeEach(() => {
  jest.resetAllMocks(); localStorage.clear();
  mockUser = { id: "u1", tenant_id: "t1", role: "owner" };
  api.getAssistantPreferences.mockResolvedValue(preferences);
  api.listAssistantConversations.mockResolvedValue([]);
  api.createAssistantConversation.mockResolvedValue({ id: "c1", title: "Conversation" });
  api.getAssistantConversation.mockResolvedValue({ messages: [result.user_message, result.assistant_message] });
  api.sendAssistantMessage.mockResolvedValue(result);
});

test("switching full and compact surfaces retains one conversation and history", async () => {
  const user = userEvent.setup();
  function Harness() { const [compact, setCompact] = useState(false); return <><button onClick={() => setCompact(!compact)}>Switch surface</button><Probe key={String(compact)} /></>; }
  renderWithProviders(<AssistantProvider><Harness /></AssistantProvider>);
  await waitFor(() => expect(screen.getByText("Send probe")).toBeEnabled());
  await user.type(screen.getByLabelText("Question"), "Question");
  await user.click(screen.getByText("Send probe"));
  await screen.findByText(/Persisted useful answer/);
  await user.click(screen.getByText("Switch surface"));
  expect(screen.getByTestId("probe-history")).toHaveTextContent("Persisted useful answer");
  expect(api.createAssistantConversation).toHaveBeenCalledTimes(1);
  expect(api.sendAssistantMessage).toHaveBeenCalledTimes(1);
});

test("history resumes from a user-scoped active reference without another paid request", async () => {
  api.listAssistantConversations.mockResolvedValue([{ id: "c1" }]);
  localStorage.setItem("signguy.assistant.active:t1:u1", "c1");
  renderWithProviders(<AssistantProvider><Probe /></AssistantProvider>);
  expect(await screen.findByText(/Persisted useful answer/)).toBeInTheDocument();
  expect(api.getAssistantConversation).toHaveBeenCalledWith("c1");
  expect(api.sendAssistantMessage).not.toHaveBeenCalled();
});

test("duplicate submits and retries retain a stable request key", async () => {
  const user = userEvent.setup();
  api.sendAssistantMessage.mockRejectedValueOnce(new Error("network"));
  renderWithProviders(<AssistantProvider><Probe /></AssistantProvider>);
  await waitFor(() => expect(screen.getByText("Send probe")).toBeEnabled());
  await user.type(screen.getByLabelText("Question"), "Question");
  fireEvent.click(screen.getByText("Send probe"));
  fireEvent.click(screen.getByText("Send probe"));
  await waitFor(() => expect(api.sendAssistantMessage).toHaveBeenCalledTimes(1));
  await user.click(screen.getByText("Send probe"));
  await waitFor(() => expect(api.sendAssistantMessage).toHaveBeenCalledTimes(2));
  expect(api.sendAssistantMessage.mock.calls[0][0].idempotency_key).toEqual(api.sendAssistantMessage.mock.calls[1][0].idempotency_key);
});

test("an identity change drops old history and ignores an old in-flight response", async () => {
  const user = userEvent.setup();
  let resolve;
  api.sendAssistantMessage.mockImplementation(() => new Promise((done) => { resolve = done; }));
  const view = renderWithProviders(<AssistantProvider><Probe /></AssistantProvider>);
  await waitFor(() => expect(screen.getByText("Send probe")).toBeEnabled());
  await user.type(screen.getByLabelText("Question"), "Question");
  await user.click(screen.getByText("Send probe"));
  await waitFor(() => expect(resolve).toBeDefined());
  mockUser = { id: "u2", tenant_id: "t2", role: "owner" };
  // Same provider instance observes the new authenticated identity.
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: "identity rerender" } });
  await act(async () => { resolve(result); });
  expect(screen.getByTestId("probe-history")).not.toHaveTextContent("Persisted useful answer");
  expect(screen.getByLabelText("Question")).toHaveValue("");
  view.unmount();
});

test("all five choices are accessible and failed saves retain the confirmed selection", async () => {
  const user = userEvent.setup();
  api.saveAssistantPreferences.mockRejectedValueOnce(new Error("save failed"));
  renderWithProviders(<AssistantProvider><AssistantSettings /></AssistantProvider>);
  expect(await screen.findAllByRole("radio")).toHaveLength(5);
  await user.click(screen.getByRole("radio", { name: /Sarcastic & Funny/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent("previous selection");
  expect(screen.getByRole("radio", { name: /Sharp Ops Partner/ })).toBeChecked();
  api.saveAssistantPreferences.mockResolvedValue({ ...preferences, preferences: { ...preferences.preferences, personality_key: "sarcastic_funny" } });
  await user.click(screen.getByRole("radio", { name: /Sarcastic & Funny/ }));
  await waitFor(() => expect(screen.getByRole("radio", { name: /Sarcastic & Funny/ })).toBeChecked());
  expect(screen.getByText(/Saved voice: independent/)).toBeInTheDocument();
  expect(api.saveAssistantPreferences).toHaveBeenLastCalledWith({ personality_key: "sarcastic_funny" });
});

test.each(options)("$name can be selected, saved and restored in the settings UI", async (option) => {
  const user = userEvent.setup();
  const saved = { ...preferences, preferences: { ...preferences.preferences, personality_key: option.key } };
  api.saveAssistantPreferences.mockResolvedValue(saved);
  // Start with another confirmed personality so each card triggers a real save.
  api.getAssistantPreferences.mockResolvedValue({ ...preferences, preferences: { ...preferences.preferences,
    personality_key: option.key === "ops_partner" ? "wise_mentor" : "ops_partner" } });
  const view = renderWithProviders(<AssistantProvider><AssistantSettings /></AssistantProvider>);
  const card = await screen.findByRole("radio", { name: new RegExp(option.name) });
  await user.click(card);
  await waitFor(() => expect(card).toBeChecked());
  expect(api.saveAssistantPreferences).toHaveBeenLastCalledWith({ personality_key: option.key });
  view.unmount();
  api.getAssistantPreferences.mockResolvedValue(saved);
  renderWithProviders(<AssistantProvider><AssistantSettings /></AssistantProvider>);
  expect(await screen.findByRole("radio", { name: new RegExp(option.name) })).toBeChecked();
});
