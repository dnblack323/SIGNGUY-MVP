import "@testing-library/jest-dom";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import ProductAiPanel from "@/components/webstores/detail/ProductAiPanel";

test.each([true, false])("backend demonstration availability controls execution: %s", async (available) => {
  const mutate = jest.fn();
  renderWithProviders(<ProductAiPanel model={{
    previewProductAi: { mutate: jest.fn() }, runProductAi: { mutate }, setProductAiPrompt: jest.fn(),
    productAiPreview: { label: "Mockup demonstration", h7_local_mock: true, can_run: available,
      credit_display: "Demonstration · 0 customer credits", available_credits: 0,
      insufficient_credits: false, unavailable_reason: available ? null : "Local demonstrations are unavailable in production." },
  }} />);
  expect(screen.getByTestId("webstore-ai-credit-display")).toHaveTextContent("0 customer credits");
  expect(screen.getByText(/Customer credits are not charged/)).toBeInTheDocument();
  const run = screen.getByTestId("webstore-ai-run-confirmed");
  if (available) {
    expect(run).toBeEnabled();
    await userEvent.click(run);
    expect(mutate).toHaveBeenCalledTimes(1);
  } else {
    expect(run).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("unavailable in production");
  }
});

test("a legitimate paid preview retains its server-provided charge and balance gate", () => {
  renderWithProviders(<ProductAiPanel model={{ previewProductAi: {}, runProductAi: {}, setProductAiPrompt: jest.fn(),
    productAiPreview: { label: "Provider action", can_run: false, credit_display: "7 AI credits", available_credits: 2, insufficient_credits: true },
  }} />);
  expect(screen.getByTestId("webstore-ai-credit-display")).toHaveTextContent("7 AI credits");
  expect(screen.getByTestId("webstore-ai-run-confirmed")).toBeDisabled();
  expect(screen.queryByText(/Customer credits are not charged/)).not.toBeInTheDocument();
});
