import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderWithProviders } from "../test-utils";
import ProductRecommendations from "@/components/webstores/detail/ProductRecommendations";
import { getWebstoreProductRecommendations } from "@/lib/webstores";
import { useAuth } from "@/auth/AuthContext";

jest.mock("@/lib/webstores", () => ({ getWebstoreProductRecommendations: jest.fn() }));
jest.mock("@/auth/AuthContext", () => ({ useAuth: jest.fn() }));

const result = {
  submission_id: "submitted-1", submission_revision: 2,
  items: [
    { template_id: "hat-1", name: "Club Cap", reasons: ["Requested in questionnaire: Hats."], already_selected: false },
    { template_id: "hoodie-1", name: "Club Hoodie", reasons: ["Suitable for this store type."], already_selected: true },
  ],
  context: [{ key: "product_notes", label: "Colors and sizes", value: "Navy, adult and youth" }],
  unmatched_requests: ["Yard signs"], extra_suggestions_declined: true,
  review_note: "Confirm supplier stock and pricing before customer approval.",
};

beforeEach(() => {
  jest.resetAllMocks();
  useAuth.mockReturnValue({ hasPerm: () => true });
  getWebstoreProductRecommendations.mockResolvedValue(result);
});

test("explains request matches and selects into the existing picker without creating anything", async () => {
  const setTemplateId = jest.fn();
  renderWithProviders(<ProductRecommendations model={{ id: "store-1", templates: { isSuccess: true }, templateId: "", setTemplateId }} />);
  expect(await screen.findByText("Club Cap")).toBeVisible();
  expect(screen.getByText("Requested in questionnaire: Hats.")).toBeVisible();
  expect(screen.getByText("Navy, adult and youth")).toBeVisible();
  expect(screen.getByText(/No matching active template for: Yard signs/)).toBeVisible();
  expect(screen.getByText(/owner declined extra suggestions/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Select template" }));
  expect(setTemplateId).toHaveBeenCalledWith("hat-1");
  expect(screen.getByRole("button", { name: "Already in selected products" })).toBeDisabled();
  expect(getWebstoreProductRecommendations).toHaveBeenCalledWith("store-1");
});

test("read-only staff can inspect recommendations but cannot select a template", async () => {
  useAuth.mockReturnValue({ hasPerm: () => false });
  renderWithProviders(<ProductRecommendations model={{ id: "store-1", templates: { isSuccess: true }, setTemplateId: jest.fn() }} />);
  expect(await screen.findByRole("button", { name: "Select template" })).toBeDisabled();
});

test("waits for existing templates and explains an empty questionnaire result", async () => {
  getWebstoreProductRecommendations.mockResolvedValue({ items: [], unmatched_requests: [], context: [] });
  const model = { id: "store-1", templates: { isSuccess: false }, setTemplateId: jest.fn() };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const content = (ready) => <QueryClientProvider client={client}><ProductRecommendations model={{ ...model, templates: { isSuccess: ready } }} /></QueryClientProvider>;
  const { rerender } = render(content(false));
  expect(getWebstoreProductRecommendations).not.toHaveBeenCalled();
  rerender(content(true));
  expect(await screen.findByText(/No active templates match/)).toBeVisible();
  expect(screen.getByText(/A completed questionnaire is needed/)).toBeVisible();
});

test("failed recommendations leave the existing workflow available and support retry", async () => {
  getWebstoreProductRecommendations.mockRejectedValueOnce(new Error("Unavailable")).mockResolvedValue(result);
  renderWithProviders(<ProductRecommendations model={{ id: "store-1", templates: { isSuccess: true }, setTemplateId: jest.fn() }} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("existing templates and products are still available below");
  fireEvent.click(screen.getByRole("button", { name: "Retry recommendations" }));
  await waitFor(() => expect(screen.getByText("Club Cap")).toBeVisible());
});
