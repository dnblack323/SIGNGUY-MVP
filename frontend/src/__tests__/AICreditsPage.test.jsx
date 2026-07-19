import React from "react";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";

jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({
    hasPerm: (perm) => ["ai_credit:read", "ai_history:read"].includes(perm),
    user: { id: "u1", tenant_id: "t1", role: "owner" },
  }),
}));

jest.mock("@/lib/aiGateway", () => ({
  __esModule: true,
  getAICreditAccount: jest.fn(),
  listAICreditLedger: jest.fn(),
  listAIHistory: jest.fn(),
  listAIAlerts: jest.fn(),
}));

import { getAICreditAccount, listAIAlerts, listAICreditLedger, listAIHistory } from "@/lib/aiGateway";
import AICreditsPage from "@/pages/AICreditsPage";

beforeEach(() => {
  jest.clearAllMocks();
  getAICreditAccount.mockResolvedValue({
    available_credits: 12,
    included_balance_credits: 7,
    purchased_balance_credits: 5,
    reserved_credits: 0,
  });
  listAICreditLedger.mockResolvedValue([
    {
      id: "ledger-1",
      entry_type: "commit",
      amount_credits: -3,
      balance_after_included_credits: 7,
      balance_after_purchased_credits: 5,
      reserved_after_credits: 0,
      reason: null,
    },
  ]);
  listAIHistory.mockResolvedValue([
    {
      id: "action-1",
      capability_key: "pricing.analysis",
      status: "succeeded",
      provider_key: "local",
      model_key: "contract",
      credit_charge_credits: 3,
    },
  ]);
  listAIAlerts.mockResolvedValue([]);
});

test("renders AI credit account, ledger, and history", async () => {
  renderWithProviders(<AICreditsPage />);
  expect(await screen.findByTestId("ai-credits-page")).toBeInTheDocument();
  await waitFor(() => expect(getAICreditAccount).toHaveBeenCalled());
  expect(screen.getByTestId("ai-available-credits")).toHaveTextContent("12");
  expect(screen.getByTestId("ai-ledger-table")).toBeInTheDocument();
  expect(screen.getByText("pricing.analysis")).toBeInTheDocument();
});
