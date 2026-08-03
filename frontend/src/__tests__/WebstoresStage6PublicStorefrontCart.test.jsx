import "@testing-library/jest-dom";
import { screen, waitFor } from "@testing-library/react";
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
