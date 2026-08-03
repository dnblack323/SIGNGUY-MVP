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

test("verified checkout opens only after collecting buyer details", async () => {
  const user = userEvent.setup();
  const originalLocation = window.location;
  const assign = jest.fn();
  Object.defineProperty(window, "location", { configurable: true, value: { assign } });
  axios.get.mockResolvedValue({
    data: {
      webstore: {
        id: "ws-stage7",
        name: "Stage 7 Store",
        store_type: "general",
        checkout_enabled: true,
        cart_config: {},
      },
      products: [{
        id: "prod-stage7",
        name: "Team Hat",
        product_type: "hat",
        selling_price_cents: 1800,
        fulfillment_methods: ["pickup"],
        default_fulfillment_method: "pickup",
      }],
    },
  });
  axios.post.mockImplementation((url) => {
    if (url.endsWith("/cart-quote")) {
      return Promise.resolve({ data: { subtotal_cents: 1800, shipping_cents: 0, donation_cents: 0, discount_cents: 0, total_cents: 1800 } });
    }
    return Promise.resolve({ data: { checkout: { checkout_url: "https://checkout.stripe.test/session" } } });
  });

  renderWithProviders(<PublicWebstorePage />, { route: "/p/webstores/stage7", path: "/p/webstores/:slug" });
  await screen.findByText("Stage 7 Store");
  await user.click(screen.getByRole("button", { name: /Add$/ }));
  await screen.findByTestId("public-cart-total");
  await user.type(screen.getByLabelText("Name"), "Buyer");
  await user.type(screen.getByLabelText("Email"), "buyer@example.com");
  await user.click(screen.getByRole("button", { name: /Continue to secure checkout/ }));

  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(
    "/api/public/webstores/stage7/checkout-session",
    expect.objectContaining({ buyer_name: "Buyer", buyer_email: "buyer@example.com" }),
  ));
  await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.test/session"));
  Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
});
