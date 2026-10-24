import "@testing-library/jest-dom";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import ProductAIPresentation from "@/components/webstores/detail/ProductAIPresentation";
import { previewWebstorePresentation, listWebstorePresentations, generateWebstorePresentation, reviewWebstorePresentation } from "@/lib/webstores";

jest.mock("@/lib/webstores", () => ({ previewWebstorePresentation: jest.fn(), listWebstorePresentations: jest.fn(), generateWebstorePresentation: jest.fn(), reviewWebstorePresentation: jest.fn() }));
jest.mock("@/components/decisionRoom/DecisionRoomMedia", () => ({ DecisionRoomMedia: ({ src, authToken, alt }) => <img src={src} data-token={authToken} alt={alt} /> }));
const model = { id: "store", productDraft: { id: "tee", product_type: "t-shirt", revision: 3 } };
const file = { id: "private-file", preview_url: "/api/private-image", ai_presentation: { color: "Navy", size: "M", review_status: "pending" } };
beforeEach(() => {
  jest.clearAllMocks(); localStorage.setItem("signguy.token", "staff-token");
  Object.defineProperty(global.crypto, "randomUUID", { configurable: true, value: jest.fn(() => "request-identity-123") });
  previewWebstorePresentation.mockResolvedValue({ can_run: true, credit_charge_credits: 7, model_key: "pinned-image-model" });
  listWebstorePresentations.mockResolvedValue({ items: [] });
  generateWebstorePresentation.mockResolvedValue({ items: [{ id: "action", status: "succeeded", credit_charge_credits: 7, file }] });
  reviewWebstorePresentation.mockResolvedValue({ items: [{ id: "action", status: "succeeded", credit_charge_credits: 7, file: { ...file, ai_presentation: { ...file.ai_presentation, review_status: "accepted" } } }] });
});
afterEach(() => localStorage.clear());

test("configured credit confirmation precedes private generation and explicit staff acceptance", async () => {
  const user = userEvent.setup(); const accepted = jest.fn();
  renderWithProviders(<ProductAIPresentation model={model} variantId="navy-m" onAccepted={accepted} />);
  const button = await screen.findByRole("button", { name: "Generate private presentation" });
  expect(button).toBeDisabled();
  await user.click(screen.getByRole("checkbox", { name: /I confirm 7 AI credits/ }));
  await user.click(button);
  expect(generateWebstorePresentation).toHaveBeenCalledWith("store", "tee", { expected_revision: 3, variant_id: "navy-m", idempotency_key: "request-identity-123", confirmed_credit_charge_credits: 7 });
  expect(await screen.findByAltText("Private AI product presentation for staff review")).toHaveAttribute("data-token", "staff-token");
  expect(accepted).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Accept product appearance for composition" }));
  await waitFor(() => expect(accepted).toHaveBeenCalledWith(file));
  expect(reviewWebstorePresentation).toHaveBeenCalledWith("store", "tee", "private-file", { expected_revision: 3, decision: "accepted" });
});

test("disabled paid execution remains unavailable with no generation call", async () => {
  previewWebstorePresentation.mockResolvedValue({ can_run: false, unavailable_reason: "Paid image generation is disabled" });
  renderWithProviders(<ProductAIPresentation model={model} variantId="navy-m" onAccepted={jest.fn()} />);
  expect(await screen.findByText("Paid image generation is disabled")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Generate private presentation" })).not.toBeInTheDocument();
  expect(generateWebstorePresentation).not.toHaveBeenCalled();
});

test("ambiguous request blocks another generation and only offers read-only status refresh", async () => {
  listWebstorePresentations.mockResolvedValue({ items: [{ id: "uncertain", status: "executing", credit_charge_credits: 7 }] });
  renderWithProviders(<ProductAIPresentation model={model} variantId="navy-m" onAccepted={jest.fn()} />);
  expect(await screen.findByText(/Awaiting reconciliation/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Generate private presentation" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Check request status" }));
  expect(generateWebstorePresentation).not.toHaveBeenCalled();
});

test("staff can reject a delivered private image without selecting it for composition", async () => {
  listWebstorePresentations.mockResolvedValue({ items: [{ id: "action", status: "succeeded", credit_charge_credits: 7, file }] });
  const accepted = jest.fn(); renderWithProviders(<ProductAIPresentation model={model} variantId="navy-m" onAccepted={accepted} />);
  await userEvent.click(await screen.findByRole("button", { name: "Reject presentation" }));
  await waitFor(() => expect(reviewWebstorePresentation).toHaveBeenCalledWith("store", "tee", "private-file", { expected_revision: 3, decision: "rejected" }));
  expect(accepted).not.toHaveBeenCalled();
});

test("a lost browser response never automatically retries a paid POST", async () => {
  generateWebstorePresentation.mockRejectedValue(new Error("Network interrupted"));
  renderWithProviders(<ProductAIPresentation model={model} variantId="navy-m" onAccepted={jest.fn()} />);
  await userEvent.click(await screen.findByRole("checkbox", { name: /I confirm 7 AI credits/ }));
  await userEvent.click(screen.getByRole("button", { name: "Generate private presentation" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/same request identity is retained/);
  expect(generateWebstorePresentation).toHaveBeenCalledTimes(1);
});
