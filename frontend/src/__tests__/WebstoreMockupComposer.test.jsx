import "@testing-library/jest-dom";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import ProductMockupComposer from "@/components/webstores/detail/ProductMockupComposer";
import { acceptWebstoreMockupComposition, previewWebstoreMockupComposition, uploadWebstoreSetupFile } from "@/lib/webstores";

jest.mock("@/lib/webstores", () => ({ acceptWebstoreMockupComposition: jest.fn(), previewWebstoreMockupComposition: jest.fn(), uploadWebstoreSetupFile: jest.fn() }));
jest.mock("@/components/decisionRoom/DecisionRoomMedia", () => ({ DecisionRoomMedia: ({ src, authToken, alt }) => <img src={src} data-token={authToken} alt={alt} /> }));
jest.mock("sonner", () => ({ toast: { success: jest.fn() } }));
const files = ["blank", "logo"].map((id) => ({ id, file_name: id + ".png", extension: "png", safe_preview_available: true, inline_preview_allowed: true }));
const model = { id: "store", productDraft: { id: "tee", product_type: "t-shirt", revision: 3, variants: [{ id: "navy", color: "Navy", size: "M" }, { id: "inactive", color: "Red", status: "inactive" }] } };
beforeEach(() => {
  jest.clearAllMocks(); localStorage.setItem("signguy.token", "staff-token");
  URL.createObjectURL = jest.fn(() => "blob:private-preview"); URL.revokeObjectURL = jest.fn();
  previewWebstoreMockupComposition.mockResolvedValue({ image: new Blob(["png"]), sha256: "abc" });
  acceptWebstoreMockupComposition.mockResolvedValue({ mockup: { id: "new-mockup" }, artwork: { id: "art" } });
});
afterEach(() => localStorage.clear());
async function prepare(user) {
  fireEvent.change(screen.getByLabelText("Blank product image"), { target: { value: "blank" } });
  fireEvent.change(screen.getByLabelText("Original artwork file"), { target: { value: "logo" } });
  fireEvent.change(screen.getByLabelText("Product color and size"), { target: { value: "navy" } });
  await user.click(screen.getByRole("checkbox", { name: /I verified this is/ }));
  await user.click(screen.getByRole("button", { name: "Preview composition" }));
  await screen.findByTestId("composition-preview");
}

test("staff previews protected original artwork and explicitly accepts the exact composition into the existing private draft", async () => {
  const user = userEvent.setup(); const accepted = jest.fn(); renderWithProviders(<ProductMockupComposer model={model} files={files} onAccepted={accepted} />);
  expect(screen.getByRole("button", { name: "Preview composition" })).toBeDisabled();
  expect(screen.queryByRole("option", { name: "Red" })).not.toBeInTheDocument();
  await prepare(user);
  expect(screen.getByAltText("Original customer artwork")).toHaveAttribute("data-token", "staff-token");
  expect(previewWebstoreMockupComposition).toHaveBeenCalledWith("store", "tee", expect.objectContaining({ expected_revision: 3, placement: { x: .35, y: .28, width: .3, height: .35 } }));
  expect(acceptWebstoreMockupComposition).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Accept mockup into draft" })).toBeDisabled();
  await user.type(screen.getByLabelText("Composed mockup description"), "Navy original logo");
  await user.click(screen.getByRole("checkbox", { name: /I reviewed the original/ }));
  await user.click(screen.getByRole("button", { name: "Accept mockup into draft" }));
  await waitFor(() => expect(accepted).toHaveBeenCalled());
  expect(acceptWebstoreMockupComposition).toHaveBeenCalledWith("store", "tee", expect.objectContaining({ reviewed: true, preview_sha256: "abc", alt_text: "Navy original logo" }));
  expect(acceptWebstoreMockupComposition.mock.calls[0][2]).not.toHaveProperty("owner_visible");
});

test("changing placement invalidates the preview and requires a fresh review", async () => {
  const user = userEvent.setup(); renderWithProviders(<ProductMockupComposer model={model} files={files} onAccepted={jest.fn()} />);
  await prepare(user);
  fireEvent.change(screen.getByLabelText("Left (%)"), { target: { value: "40" } });
  expect(screen.queryByTestId("composition-preview")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Accept mockup into draft" })).not.toBeInTheDocument();
  expect(acceptWebstoreMockupComposition).not.toHaveBeenCalled();
});

test("unsupported products retain the manual upload fallback", () => {
  renderWithProviders(<ProductMockupComposer model={{ ...model, productDraft: { ...model.productDraft, product_type: "hat" } }} files={files} onAccepted={jest.fn()} />);
  expect(screen.getByText(/Use the prepared mockup upload/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Preview composition" })).not.toBeInTheDocument();
});

test("backend placement validation errors remain readable when preview uses a blob response", async () => {
  const blob = new Blob(); blob.text = async () => JSON.stringify({ detail: [{ msg: "Decoration area must stay inside the product image" }] });
  previewWebstoreMockupComposition.mockRejectedValue({ response: { data: blob } });
  const user = userEvent.setup(); renderWithProviders(<ProductMockupComposer model={model} files={files} onAccepted={jest.fn()} />);
  fireEvent.change(screen.getByLabelText("Blank product image"), { target: { value: "blank" } });
  fireEvent.change(screen.getByLabelText("Original artwork file"), { target: { value: "logo" } });
  fireEvent.change(screen.getByLabelText("Product color and size"), { target: { value: "navy" } });
  await user.click(screen.getByRole("checkbox", { name: /I verified this is/ }));
  await user.click(screen.getByRole("button", { name: "Preview composition" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Decoration area must stay inside the product image");
  expect(acceptWebstoreMockupComposition).not.toHaveBeenCalled();
});

test("blank uploads reuse private canonical artwork storage without claiming AI output", async () => {
  uploadWebstoreSetupFile.mockResolvedValue({ file: { ...files[0], id: "uploaded-blank" } });
  const user = userEvent.setup(); renderWithProviders(<ProductMockupComposer model={model} files={files} onAccepted={jest.fn()} />);
  await user.upload(screen.getByLabelText("Upload a matching blank"), new File(["image"], "blue.png", { type: "image/png" }));
  await waitFor(() => expect(screen.getByLabelText("Blank product image")).toHaveValue("uploaded-blank"));
  expect(uploadWebstoreSetupFile.mock.calls[0][1].get("category")).toBe("artwork");
  expect(screen.getByText(/Real AI presentation generation is not connected/)).toBeInTheDocument();
});
