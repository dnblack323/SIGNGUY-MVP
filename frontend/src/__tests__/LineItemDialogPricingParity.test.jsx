import React from "react";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom";
import { renderWithProviders } from "../test-utils";
import LineItemDialog from "@/components/commerce/LineItemDialog";
import api from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { toast } from "sonner";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    post: jest.fn(),
  },
  extractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children, ...props }) => <div {...props}>{children}</div>,
  DialogDescription: ({ children }) => <p>{children}</p>,
  DialogFooter: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
}));

jest.mock("@/components/ui/tabs", () => {
  const React = require("react");
  const TabsContext = React.createContext({ value: "", onValueChange: () => {} });
  return {
    Tabs: ({ value, onValueChange, children, ...props }) => (
      <TabsContext.Provider value={{ value, onValueChange }}>
        <div {...props}>{children}</div>
      </TabsContext.Provider>
    ),
    TabsList: ({ children }) => <div>{children}</div>,
    TabsTrigger: ({ value, children, ...props }) => {
      const ctx = React.useContext(TabsContext);
      return <button type="button" onClick={() => ctx.onValueChange(value)} {...props}>{children}</button>;
    },
    TabsContent: ({ value, children, ...props }) => {
      const ctx = React.useContext(TabsContext);
      return ctx.value === value ? <div {...props}>{children}</div> : null;
    },
  };
});

jest.mock("@/components/ui/select", () => {
  const React = require("react");
  const SelectContext = React.createContext({ value: "", onValueChange: () => {}, options: [] });
  function SelectItem({ value, children }) {
    return <option value={value}>{children}</option>;
  }
  function collectOptions(children, options = []) {
    React.Children.forEach(children, (child) => {
      if (!React.isValidElement(child)) return;
      if (child.type === SelectItem) {
        options.push(<option key={child.props.value} value={child.props.value}>{child.props.children}</option>);
      } else {
        collectOptions(child.props.children, options);
      }
    });
    return options;
  }
  return {
    Select: ({ value, onValueChange, children }) => (
      <SelectContext.Provider value={{ value: value || "", onValueChange, options: collectOptions(children) }}>
        {children}
      </SelectContext.Provider>
    ),
    SelectContent: () => null,
    SelectItem,
    SelectTrigger: ({ children, ...props }) => {
      const ctx = React.useContext(SelectContext);
      return <select value={ctx.value} onChange={(event) => ctx.onValueChange(event.target.value)} {...props}>{ctx.options}</select>;
    },
    SelectValue: () => null,
  };
});

jest.mock("@/components/pricing/CategorySpecificFields", () => ({
  CategorySpecificFields: ({ category, values, onChange }) => (
    <div data-testid={`li-category-fields-${category}`}>
      <button type="button" data-testid="li-mock-category-input" onClick={() => onChange({ ...values, finish: "matte" })}>
        Change category input
      </button>
    </div>
  ),
}));

jest.mock("@/components/pricing/selectors/SavedItemSelector", () => ({
  __esModule: true,
  default: ({ onChange, testIdPrefix }) => (
    <button type="button" data-testid={`${testIdPrefix}-selector`} onClick={() => onChange("saved-1")}>Saved item</button>
  ),
}));

jest.mock("@/components/pricing/selectors/PricingComponentSelector", () => ({
  __esModule: true,
  default: ({ onChange, testIdPrefix }) => (
    <button type="button" data-testid={`${testIdPrefix}-selector`} onClick={() => onChange(["component-1"])}>Component</button>
  ),
}));

jest.mock("@/components/pricing/selectors/MaterialProfileSelector", () => ({
  __esModule: true,
  default: ({ onChange, testIdPrefix }) => (
    <button type="button" data-testid={`${testIdPrefix}-selector`} onClick={() => onChange("profile-1")}>Material</button>
  ),
}));

function successfulMethod(methodId, amount, selected = false) {
  return {
    method_id: methodId,
    display_name: methodId.replaceAll("_", " "),
    status: ["available", selected ? "selected" : "candidate"],
    available: true,
    amount,
    selected,
  };
}

function pricingResult(category = "banners") {
  if (category === "banners") {
    return {
      category,
      selling_price: 192,
      pricing_method_used: "square_foot_plus_addons",
      canonical_method_id: "square_foot_plus_addons",
      selected_method_id: "square_foot_plus_addons",
      pricing_method_results: [
        successfulMethod("square_foot_plus_addons", 192, true),
        successfulMethod("cost_plus", 170),
        { method_id: "target_margin", display_name: "target margin", status: ["unavailable"], available: false, amount: null, reason: "missing true cost" },
      ],
      method_availability: [{ method_id: "target_margin", available: false, reason: "missing true cost" }],
      detail_sections: [{ section: "authoritative_result", lines: [{ key: "area", label: "Area", value: "24 sq ft" }] }],
      breakdown: [{ label: "Base square-foot amount", amount: 144 }],
      calculation_warnings: ["fixture warning"],
      true_cost: 100,
    };
  }
  return {
    category,
    selling_price: 48,
    pricing_method_used: "unit_price_x_quantity",
    canonical_method_id: "unit_price_x_quantity",
    selected_method_id: "unit_price_x_quantity",
    pricing_method_results: [
      successfulMethod("unit_price_x_quantity", 48, true),
      { method_id: "manual_override", display_name: "manual override", status: ["unavailable"], available: false, amount: null, reason: "no manual amount" },
    ],
    method_availability: [{ method_id: "manual_override", available: false, reason: "no manual amount" }],
    detail_sections: [{ section: `${category}_details`, lines: [{ key: "category_detail", label: "Category detail", value: "preserved" }] }],
    breakdown: [],
    calculation_warnings: [],
    true_cost: 20,
  };
}

function comparisonResult(primaryMethodId = "square_foot_plus_addons") {
  return {
    canonical_method_id: "square_foot_plus_addons",
    selected_method_id: primaryMethodId,
    primary_method_id: primaryMethodId,
    comparison_results: [
      successfulMethod("square_foot_plus_addons", 192, primaryMethodId === "square_foot_plus_addons"),
      successfulMethod("cost_plus", 170, primaryMethodId === "cost_plus"),
      { method_id: "target_margin", display_name: "target margin", status: ["unavailable"], available: false, amount: null, reason: "missing true cost" },
    ],
    availability: { methods: [{ method_id: "target_margin", available: false, reason: "missing true cost" }] },
  };
}

function mockApi({ failed = false } = {}) {
  api.post.mockImplementation((url, payload) => {
    if (url === "/pricing/calculate") {
      if (failed) {
        return Promise.resolve({ data: { category: payload.category, selling_price: null, errors: ["no exact tier"], pricing_method_results: [{ method_id: "tier_pricing", available: false, amount: null, selected: true, status: ["manual_price_required"] }] } });
      }
      return Promise.resolve({ data: pricingResult(payload.category) });
    }
    if (url === "/pricing/method-comparison") {
      return Promise.resolve({ data: comparisonResult(payload.primary_method_id || "square_foot_plus_addons") });
    }
    return Promise.resolve({ data: {} });
  });
}

function renderDialog(props = {}) {
  const onSubmit = props.onSubmit || jest.fn().mockResolvedValue({});
  renderWithProviders(
    <LineItemDialog
      open
      onOpenChange={jest.fn()}
      entryMode="detailed"
      mode="add"
      entityLabel="Quote"
      onSubmit={onSubmit}
      {...props}
    />,
  );
  return { onSubmit };
}

async function calculateBanner() {
  fireEvent.change(screen.getByTestId("li-description-detailed"), { target: { value: "Banner item" } });
  fireEvent.change(screen.getByTestId("li-category-detailed"), { target: { value: "banners" } });
  fireEvent.change(screen.getByTestId("li-width"), { target: { value: "96" } });
  fireEvent.change(screen.getByTestId("li-height"), { target: { value: "36" } });
  fireEvent.click(screen.getByTestId("li-calculator"));
  await screen.findByTestId("li-calc-result");
}

beforeEach(() => {
  jest.clearAllMocks();
  useAuth.mockReturnValue({ hasPerm: (permission) => permission === "pricing:calculate" });
  mockApi();
});

test("Quote and Order dialogs transfer the same backend authoritative price for identical Banner inputs", async () => {
  const quoteSubmit = jest.fn().mockResolvedValue({});
  renderDialog({ entityLabel: "Quote", onSubmit: quoteSubmit });
  await calculateBanner();
  fireEvent.click(screen.getByTestId("li-submit"));
  await waitFor(() => expect(quoteSubmit).toHaveBeenCalled());
  const quotePayload = quoteSubmit.mock.calls[0][0];

  cleanup();
  const orderSubmit = jest.fn().mockResolvedValue({});
  renderWithProviders(
    <LineItemDialog open onOpenChange={jest.fn()} entryMode="detailed" mode="add" entityLabel="Order" allowProductionRequired onSubmit={orderSubmit} />,
  );
  await calculateBanner();
  fireEvent.click(screen.getByTestId("li-submit"));
  await waitFor(() => expect(orderSubmit).toHaveBeenCalled());
  const orderPayload = orderSubmit.mock.calls[0][0];

  expect(quotePayload.unit_price_cents).toBe(19200);
  expect(orderPayload.unit_price_cents).toBe(19200);
  expect(quotePayload.selected_price_source).toBe("suggested");
  expect(orderPayload.selected_price_source).toBe("suggested");
  expect(quotePayload.category_inputs).toEqual(orderPayload.category_inputs);
});

test("dialog displays authoritative, canonical, selected, available, unavailable, warning, and detail data", async () => {
  renderDialog();
  await calculateBanner();

  expect(screen.getByTestId("li-authoritative-selling-price")).toHaveTextContent("$192.00");
  expect(screen.getByTestId("li-canonical-method")).toHaveTextContent("square foot plus addons");
  expect(screen.getByTestId("li-selected-method")).toHaveTextContent("square foot plus addons");
  expect(screen.getByTestId("li-method-square_foot_plus_addons")).toHaveTextContent("$192.00");
  expect(screen.getByTestId("li-method-cost_plus")).toHaveTextContent("$170.00");
  expect(screen.getByTestId("li-method-target_margin")).toHaveTextContent("Unavailable");
  expect(screen.getByTestId("li-unavailable-methods")).toHaveTextContent("missing true cost");
  expect(screen.getByTestId("li-calc-warnings")).toHaveTextContent("fixture warning");
  expect(screen.getByTestId("li-pricing-details")).toHaveTextContent("24 sq ft");
  expect(api.post).toHaveBeenCalledWith("/pricing/method-comparison", expect.objectContaining({ category: "banners" }));
});

test("non-Banner normalized categories use calculate results without Banner comparison", async () => {
  renderDialog();
  fireEvent.change(screen.getByTestId("li-description-detailed"), { target: { value: "Apparel item" } });
  fireEvent.change(screen.getByTestId("li-category-detailed"), { target: { value: "apparel" } });
  fireEvent.click(screen.getByTestId("li-calculator"));

  expect(await screen.findByTestId("li-authoritative-selling-price")).toHaveTextContent("$48.00");
  expect(screen.getByTestId("li-method-unit_price_x_quantity")).toHaveTextContent("$48.00");
  expect(screen.getByTestId("li-pricing-details")).toHaveTextContent("preserved");
  expect(api.post).toHaveBeenCalledWith("/pricing/calculate", expect.objectContaining({ category: "apparel" }));
  expect(api.post).not.toHaveBeenCalledWith("/pricing/method-comparison", expect.anything());
});

test("category switching and price-affecting input changes clear stale calculated results", async () => {
  renderDialog();
  await calculateBanner();
  expect(screen.getByTestId("li-calc-result")).toBeInTheDocument();

  fireEvent.change(screen.getByTestId("li-width"), { target: { value: "120" } });
  expect(screen.queryByTestId("li-calc-result")).not.toBeInTheDocument();

  await calculateBanner();
  fireEvent.change(screen.getByTestId("li-category-detailed"), { target: { value: "apparel" } });
  expect(screen.queryByTestId("li-calc-result")).not.toBeInTheDocument();
});

test("failed calculator result is shown as an error and cannot be transferred", async () => {
  mockApi({ failed: true });
  const onSubmit = jest.fn().mockResolvedValue({});
  renderDialog({ onSubmit });
  fireEvent.change(screen.getByTestId("li-description-detailed"), { target: { value: "Promotional tier" } });
  fireEvent.change(screen.getByTestId("li-category-detailed"), { target: { value: "promotional" } });
  fireEvent.click(screen.getByTestId("li-calculator"));

  expect(await screen.findByTestId("li-calc-error")).toHaveTextContent("transferable selling price");
  expect(screen.queryByTestId("li-price-source-suggested")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("li-submit"));
  await waitFor(() => expect(toast.error).toHaveBeenCalled());
  expect(onSubmit).not.toHaveBeenCalled();
});

test("permission-blocked users cannot calculate or transfer suggested pricing", async () => {
  useAuth.mockReturnValue({ hasPerm: () => false });
  const onSubmit = jest.fn().mockResolvedValue({});
  renderDialog({ onSubmit });
  fireEvent.change(screen.getByTestId("li-description-detailed"), { target: { value: "Banner item" } });
  fireEvent.change(screen.getByTestId("li-category-detailed"), { target: { value: "banners" } });

  expect(screen.getByTestId("li-calculator")).toBeDisabled();
  expect(screen.getByTestId("li-pricing-permission-blocked")).toBeInTheDocument();
  expect(api.post).not.toHaveBeenCalled();
});

test("manual override reason is still required for manual prices", async () => {
  const onSubmit = jest.fn().mockResolvedValue({});
  renderDialog({ onSubmit });
  fireEvent.change(screen.getByTestId("li-description-detailed"), { target: { value: "Manual item" } });
  fireEvent.change(screen.getByTestId("li-unit-price-detailed"), { target: { value: "42.00" } });
  fireEvent.click(screen.getByTestId("li-submit"));

  await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Override reason is required for a manual price"));
  expect(onSubmit).not.toHaveBeenCalled();
});

test("all nine categories are available in the shared Quote and Order dialog", () => {
  renderDialog();
  const options = within(screen.getByTestId("li-category-detailed")).getAllByRole("option").map((option) => option.value);
  expect(options).toEqual(["banners", "rigid_signs", "cut_vinyl", "digital_print", "vehicle_graphics", "apparel", "services", "promotional", "custom"]);
});
