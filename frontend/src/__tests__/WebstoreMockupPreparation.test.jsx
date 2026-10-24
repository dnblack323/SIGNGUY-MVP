import "@testing-library/jest-dom";
jest.mock("@/components/webstores/detail/ProductAIPresentation", () => () => null);
import { useState } from "react";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import ProductMockupPreparation from "@/components/webstores/detail/ProductMockupPreparation";
import OwnerPortalProducts from "@/components/webstores/owner-portal/OwnerPortalProducts";
import { createWebstoreArtwork, createWebstoreMockup, uploadWebstoreSetupFile } from "@/lib/webstores";

jest.mock("@/lib/webstores", () => ({ createWebstoreArtwork: jest.fn(), createWebstoreMockup: jest.fn(), uploadWebstoreSetupFile: jest.fn() }));
jest.mock("@/components/decisionRoom/DecisionRoomMedia", () => ({ DecisionRoomMedia: ({ src, authToken, alt, testId }) => <img src={src} alt={alt} data-testid={testId} data-token={authToken} /> }));
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
const file = { id: "image-1", file_name: "Hat front.png", extension: "png", safe_preview_available: true, inline_preview_allowed: true };
const send = jest.fn();
function Workspace({ submitted = false }) {
  const [productDraft, setDraft] = useState({ id: "hat", revision: 2, approval_revision: submitted ? 2 : null, approval_snapshot: submitted ? { mockups: [{ id: "mockup-1" }] } : null, mockup_associations: [] });
  return <ProductMockupPreparation model={{ id: "store", productDraft, setupFileItems: [file], artworkOptions: { data: [{ id: "art-1", file_name: "Logo" }], refetch: jest.fn() }, mockupOptions: { data: [{ id: "mockup-1", mockup_file_id: "image-1", alt_text: "Navy Hat front", shop_approved: true }], refetch: jest.fn() }, submitMockupApproval: { mutate: send }, addAssociation: (field, key, id) => setDraft((draft) => ({ ...draft, [field]: [...(draft[field] || []), { [key]: id }] })), removeAssociation: jest.fn() }} />;
}
beforeEach(() => { jest.clearAllMocks(); localStorage.setItem("signguy.token", "staff-token"); localStorage.setItem("sg_portal_token", "owner-token"); createWebstoreMockup.mockResolvedValue({ id: "mockup-1" }); createWebstoreArtwork.mockResolvedValue({ id: "art-1" }); uploadWebstoreSetupFile.mockResolvedValue({ file: { ...file, id: "uploaded-1" } }); });
afterEach(() => localStorage.clear());

test("staff previews the protected image and explicitly reviews it before attaching a private mockup", async () => {
  const user = userEvent.setup(); renderWithProviders(<Workspace />);
  expect(screen.getByRole("button", { name: "Attach reviewed mockup" })).toBeDisabled();
  fireEvent.change(screen.getByTestId("webstore-mockup-file"), { target: { value: "image-1" } });
  expect(screen.getByTestId("webstore-prepared-mockup-image")).toHaveAttribute("data-token", "staff-token");
  await user.type(screen.getByTestId("webstore-mockup-description"), "Navy Hat front");
  fireEvent.change(screen.getByTestId("webstore-mockup-artwork"), { target: { value: "art-1" } });
  await user.click(screen.getByTestId("webstore-mockup-reviewed"));
  await user.click(screen.getByRole("button", { name: "Attach reviewed mockup" }));
  await waitFor(() => expect(createWebstoreMockup).toHaveBeenCalledWith("store", expect.objectContaining({ product_id: "hat", artwork_id: "art-1", mockup_file_id: "image-1", shop_approved: true, generation_source: "manual" })));
  expect(createWebstoreMockup.mock.calls[0][1]).not.toHaveProperty("owner_visible");
  expect(await screen.findByTestId("staff-mockup-image-mockup-1")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send Mockup Approval" })).toBeDisabled();
  expect(send).not.toHaveBeenCalled();
});

test("new artwork uses the existing managed upload and artwork association", async () => {
  const user = userEvent.setup(); renderWithProviders(<Workspace />);
  await user.upload(screen.getByTestId("webstore-artwork-upload"), new File(["fixture"], "logo.png", { type: "image/png" }));
  await waitFor(() => expect(screen.getByTestId("webstore-artwork-file")).toHaveValue("uploaded-1"));
  expect(uploadWebstoreSetupFile.mock.calls[0][1].get("category")).toBe("artwork");
  await user.click(screen.getByRole("button", { name: "Attach artwork to draft" }));
  await waitFor(() => expect(createWebstoreArtwork).toHaveBeenCalledWith("store", expect.objectContaining({ product_id: "hat", file_id: "uploaded-1" })));
});

test("only a mockup in the current product submission can be sent for owner approval", async () => {
  const user = userEvent.setup(); renderWithProviders(<Workspace submitted />);
  fireEvent.change(screen.getByTestId("webstore-product-mockup-associations"), { target: { value: "mockup-1" } });
  await user.click(screen.getByRole("button", { name: "Send Mockup Approval" }));
  expect(send).toHaveBeenCalledWith("mockup-1");
});

test("an approved product still offers a comment and change request for its pending mockup", async () => {
  const user = userEvent.setup(); const decide = jest.fn(); const comments = jest.fn();
  renderWithProviders(<OwnerPortalProducts products={[{ id: "hat", name: "Navy Hat", approval_status: "approved", mockups: [{ id: "mockup-1", alt_text: "Navy Hat front", approval_status: "pending_owner_approval", image_url: "/api/portal/webstores/store/products/hat/mockups/mockup-1/image" }] }]} productComments={{}} onProductCommentsChange={comments} onDecideProduct={jest.fn()} onDecideMockup={decide} />);
  expect(screen.getByTestId("owner-mockup-image-mockup-1")).toHaveAttribute("data-token", "owner-token");
  expect(screen.getByTestId("portal-product-approval-comment-hat")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Approve Product" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Request Changes" }));
  expect(decide).toHaveBeenCalledWith("mockup-1", "request_changes", "hat");
});
