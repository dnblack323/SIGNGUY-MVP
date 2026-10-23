import "@testing-library/jest-dom";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { renderWithProviders } from "../test-utils";
import PublicWebstorePage from "@/pages/PublicWebstorePage";

jest.mock("axios", () => ({
  get: jest.fn(),
  post: jest.fn(),
  create: jest.fn(() => ({
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    get: jest.fn(),
    post: jest.fn(),
  })),
}));

beforeEach(() => {
  window.HTMLElement.prototype.hasPointerCapture = () => false;
  window.HTMLElement.prototype.setPointerCapture = () => {};
  window.HTMLElement.prototype.releasePointerCapture = () => {};
  window.HTMLElement.prototype.scrollIntoView = () => {};
});

test("public product choices become a server-priced cart line without checkout", async () => {
  const user = userEvent.setup();
  axios.get.mockResolvedValue({
    data: {
      webstore: {
        id: "ws-stage6",
        name: "Stage 6 Store",
        store_type: "general",
        checkout_enabled: false,
        checkout_unavailable_reason: "Payment setup is not available yet.",
        cart_config: {},
      },
      products: [{
        id: "prod-stage6",
        name: "Team Shirt",
        product_type: "shirt",
        selling_price_cents: 2500,
        variants: [{ id: "large", name: "Large", selling_price_cents: 2900 }],
        personalization_fields: [{ key: "name", label: "Player name", required: true, type: "text" }],
        fulfillment_methods: ["shipping"],
        default_fulfillment_method: "shipping",
        shipping_cost_cents: 500,
      }],
    },
  });
  axios.post.mockResolvedValue({
    data: {
      quote_version: "webstore_cart_quote_v1",
      subtotal_cents: 2900,
      shipping_cents: 500,
      donation_cents: 0,
      discount_cents: 0,
      total_cents: 3400,
      line_items: [],
    },
  });

  renderWithProviders(<PublicWebstorePage />, { route: "/p/webstores/stage6", path: "/p/webstores/:slug" });
  await screen.findByText("Stage 6 Store");
  await user.click(screen.getByRole("button", { name: /Add$/ }));
  await user.type(screen.getByLabelText("Player name *"), "Alex");
  await user.click(screen.getByRole("button", { name: /Add to cart/ }));

  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(
    "/api/public/webstores/stage6/cart-quote",
    expect.objectContaining({
      line_items: [{
        product_id: "prod-stage6",
        quantity: 1,
        variant: expect.objectContaining({ id: "large" }),
        personalization: { name: "Alex" },
        fulfillment_method: "shipping",
      }],
    }),
  ));
  expect(await screen.findByTestId("public-cart-total")).toHaveTextContent("$34.00");
  expect(screen.queryByRole("button", { name: /checkout/i })).not.toBeInTheDocument();
});

test("configured select and text limits are usable and unavailable variants cannot be selected", async () => {
  const user = userEvent.setup();
  axios.get.mockResolvedValue({ data: {
    webstore: { id: "ws-hoodie", name: "School Store", cart_config: {} },
    products: [{ id: "hoodie", name: "School Hoodie", selling_price_cents: 4200,
      variants: [
        { id: "no", size: "L", color: "White", available: false },
        { id: "yes", size: "M", color: "Navy", available: true, status: "active" },
        { id: "inactive", size: "L", color: "Navy", status: "inactive" },
      ],
      personalization_fields: [
        { key: "name", label: "Player Name", type: "text", max_length: 20 },
        { key: "year", label: "Graduation Year", type: "select", required: true, choices: ["2026", "2027", "2028"] },
      ], default_fulfillment_method: "pickup",
    }],
  } });
  axios.post.mockClear();
  axios.post.mockResolvedValue({ data: { subtotal_cents: 4200, total_cents: 4200 } });
  renderWithProviders(<PublicWebstorePage />, { route: "/p/webstores/school", path: "/p/webstores/:slug" });
  await screen.findByText("School Store");
  await user.click(screen.getByRole("button", { name: "Details" }));
  await user.click(screen.getByLabelText("Options"));
  expect(screen.getByRole("option", { name: "L / White (unavailable)" })).toHaveAttribute("data-disabled");
  expect(screen.getByRole("option", { name: "L / Navy (unavailable)" })).toHaveAttribute("data-disabled");
  await user.click(screen.getByRole("option", { name: "M / Navy" }));
  expect(screen.getByLabelText("Player Name")).toHaveAttribute("maxlength", "20");
  await user.type(screen.getByLabelText("Player Name"), "A".repeat(21));
  expect(screen.getByLabelText("Player Name")).toHaveValue("A".repeat(20));
  await user.click(screen.getByRole("button", { name: /Add to cart/ }));
  expect(screen.getByRole("alert")).toHaveTextContent("Complete: Graduation Year");
  await user.selectOptions(screen.getByLabelText("Graduation Year *"), "2027");
  // Native personalization select uses the canonical choices.
  expect(within(screen.getByLabelText("Graduation Year *")).getAllByRole("option")).toHaveLength(4);
  await user.click(screen.getByRole("button", { name: /Add to cart/ }));
  await waitFor(() => expect(axios.post).toHaveBeenCalledWith("/api/public/webstores/school/cart-quote", expect.objectContaining({
    line_items: [expect.objectContaining({ variant: expect.objectContaining({ id: "yes" }), personalization: { name: "A".repeat(20), year: "2027" } })],
  })));
});

test("disabled personalization stays off and an entirely unavailable product cannot be added", async () => {
  const user = userEvent.setup();
  axios.get.mockResolvedValue({ data: {
    webstore: { id: "ws", name: "Unavailable Store", cart_config: {} },
    products: [{ id: "hoodie", name: "School Hoodie", selling_price_cents: 4200,
      variants: [{ id: "no", size: "L", available: false }],
      personalization_enabled: false,
      personalization_fields: [{ key: "old", label: "Disabled prompt", type: "text", required: true }],
    }],
  } });
  renderWithProviders(<PublicWebstorePage />, { route: "/p/webstores/school", path: "/p/webstores/:slug" });
  await screen.findByText("Unavailable Store");
  await user.click(screen.getByRole("button", { name: "Details" }));
  expect(screen.queryByLabelText("Disabled prompt *")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Add to cart/ })).toBeDisabled();
});
