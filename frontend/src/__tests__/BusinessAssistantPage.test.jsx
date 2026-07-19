import React from "react";
import { screen, waitFor } from "@testing-library/react";
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
  createVoiceSession: jest.fn(),
  listAssistantQuickActions: jest.fn(),
  createStudioDelegation: jest.fn(),
  confirmAssistantProposal: jest.fn(),
  cancelAssistantProposal: jest.fn(),
  executeAssistantProposal: jest.fn(),
}));

import {
  createVoiceSession,
  getAssistantCatalog,
  getVoiceConfig,
  listAssistantQuickActions,
  sendAssistantMessage,
} from "@/lib/businessAssistant";
import BusinessAssistantPage from "@/pages/BusinessAssistantPage";

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

  await user.type(screen.getByTestId("assistant-message-input"), "What is the latest invoice?");
  await user.click(screen.getByTestId("assistant-send"));

  await waitFor(() => expect(sendAssistantMessage).toHaveBeenCalled());
  expect(screen.getByTestId("assistant-history")).toHaveTextContent("Latest invoice: 1201");
  expect(screen.getByTestId("assistant-sources")).toHaveTextContent("Invoice 1201");

  await user.click(screen.getByTestId("assistant-voice-connect"));
  await waitFor(() => expect(createVoiceSession).toHaveBeenCalled());
  expect(screen.getByTestId("assistant-voice-transcript")).toHaveValue("OpenAI Voice is not configured");
});
