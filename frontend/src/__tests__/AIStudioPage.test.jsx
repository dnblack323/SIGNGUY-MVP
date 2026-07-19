import React from "react";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";

jest.mock("@/auth/AuthContext", () => ({
  __esModule: true,
  useAuth: () => ({
    hasPerm: (perm) => ["ai_tool:use", "ai_prompt:read", "document:read", "ai_history:read"].includes(perm),
    user: { id: "u1", tenant_id: "t1", role: "owner" },
  }),
}));

jest.mock("@/lib/aiStudio", () => ({
  __esModule: true,
  getAIStudioCatalog: jest.fn(),
  runAIStudioTool: jest.fn(),
}));

import { getAIStudioCatalog } from "@/lib/aiStudio";
import AIStudioPage from "@/pages/AIStudioPage";

beforeEach(() => {
  jest.clearAllMocks();
  getAIStudioCatalog.mockResolvedValue({
    credit_display: "AI credits apply",
    usage_bands: {
      light: "Short rewrite",
      standard: "Normal text generation",
      heavy: "Long-form",
      premium: "Image generation",
    },
    families: [
      { family_key: "design_image", name: "Design & Image Studio" },
      { family_key: "marketing_brand", name: "Marketing & Brand Studio" },
      { family_key: "writing_documents", name: "Business Writing & Documents" },
      { family_key: "pricing_profitability", name: "Pricing & Profitability" },
    ],
    tools: [
      {
        tool_key: "ai_image_generator",
        name: "AI Image Generator",
        family_key: "design_image",
        modes: [
          {
            mode_key: "general_text_to_image",
            name: "General Text-to-Image",
            usage_band: "premium",
            credit_display: "AI credits apply",
            fields: [{ name: "prompt", label: "Prompt", type: "textarea", required: true }],
            warnings: [],
          },
        ],
      },
      {
        tool_key: "social_post_builder",
        name: "Social Post Builder",
        family_key: "marketing_brand",
        modes: [
          {
            mode_key: "completed_work_showcase",
            name: "Completed-Work Showcase",
            usage_band: "standard",
            credit_display: "AI credits apply",
            fields: [
              { name: "prompt", label: "Prompt", type: "textarea", required: true },
              { name: "publicity_permission_state", label: "Customer/publicity permission", type: "select", required: true, options: ["confirmed", "unknown", "missing"] },
            ],
            warnings: ["Draft only. No direct publishing."],
          },
        ],
      },
    ],
  });
});

test("renders four EC17 families, featured image generator, and mode fields", async () => {
  renderWithProviders(<AIStudioPage />, { route: "/studio?tool=social_post_builder&mode=completed_work_showcase" });
  expect(await screen.findByTestId("ai-studio-page")).toBeInTheDocument();
  await waitFor(() => expect(getAIStudioCatalog).toHaveBeenCalled());
  expect(screen.getByText("Design & Image Studio")).toBeInTheDocument();
  expect(screen.getByText("Marketing & Brand Studio")).toBeInTheDocument();
  expect(screen.getByText("Business Writing & Documents")).toBeInTheDocument();
  expect(screen.getByText("Pricing & Profitability")).toBeInTheDocument();
  expect(screen.getByTestId("featured-image-generator")).toHaveTextContent("AI Image Generator");
  expect(screen.getByText("Customer/publicity permission")).toBeInTheDocument();
  expect(screen.getAllByText("AI credits apply").length).toBeGreaterThan(0);
});
