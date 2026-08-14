import React from "react";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom";
import { renderWithProviders } from "../test-utils";
import PricingCalculatorPage from "@/pages/PricingCalculatorPage";
import { NAV_AREAS } from "@/lib/navigation";
import api from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    patch: jest.fn(),
  },
  extractError: (error) => error?.response?.data?.detail || error?.message || "Request failed",
}));

jest.mock("@/auth/AuthContext", () => ({
  useAuth: jest.fn(),
}));

jest.mock("@/components/pricing/selectors/SavedItemSelector", () => ({
  __esModule: true,
  default: ({ onChange, testIdPrefix }) => (
    <button
      type="button"
      data-testid={`${testIdPrefix}-selector`}
      onClick={() => onChange("saved-1", { id: "saved-1", name: "Saved banner", saved_config: {}, default_pricing_method: "tier_pricing" })}
    >
      Saved banner
    </button>
  ),
}));

jest.mock("@/components/pricing/selectors/MaterialProfileSelector", () => ({
  __esModule: true,
  default: ({ onChange, testIdPrefix }) => (
    <button type="button" data-testid={`${testIdPrefix}-selector`} onClick={() => onChange("vinyl-13oz")}>
      13oz vinyl
    </button>
  ),
}));

jest.mock("@/components/pricing/selectors/PricingComponentSelector", () => ({
  __esModule: true,
  default: ({ onChange, testIdPrefix }) => (
    <button type="button" data-testid={`${testIdPrefix}-selector`} onClick={() => onChange(["grommets"])}>
      Grommets
    </button>
  ),
}));

jest.mock("@/components/pricing/CategorySpecificFields", () => ({
  CategorySpecificFields: ({ category, values, onChange }) => (
    <div data-testid={`calc-category-fields-${category.replaceAll("_", "-")}`}>
      <button type="button" data-testid="mock-category-field-change" onClick={() => onChange({ ...values, finish: "matte" })}>
        Set category option
      </button>
    </div>
  ),
}));

const categoryMeta = {
  banners: { name: "Banners" },
  rigid_signs: { name: "Rigid Signs" },
  cut_vinyl: { name: "Cut Vinyl" },
  digital_print: { name: "Digital Print" },
  vehicle_graphics: { name: "Vehicle Graphics" },
  apparel: { name: "Apparel" },
  promotional: { name: "Promotional" },
  services: { name: "Services" },
  custom: { name: "Custom" },
};

function successfulMethod(id, amount, selected = false) {
  return {
    method_id: id,
    display_name: id.replaceAll("_", " "),
    status: "success",
    available: true,
    amount,
    amount_cents: amount == null ? null : centsFor(amount),
    selected,
    details: { source: "fixture" },
  };
}

const CENTS = {
  "3.55": 355,
  "16.45": 1645,
  "20": 2000,
  "40": 4000,
  "48": 4800,
  "144": 14400,
  "170": 17000,
  "180": 18000,
  "192": 19200,
};

function centsFor(amount) {
  return CENTS[String(amount)] ?? null;
}

function withPricingEngineResult(result, sellingPriceCents) {
  return {
    ...result,
    pricing_engine_result: {
      status: "success",
      selling_price_cents: sellingPriceCents,
      selected_method_amount_cents: sellingPriceCents,
      true_cost_cents: result.true_cost != null ? centsFor(result.true_cost) : null,
      profit_amount_cents: result.profit_amount != null ? centsFor(result.profit_amount) : null,
      method_rows: (result.pricing_method_results || []).map((row) => ({
        method_id: row.method_id,
        selected: !!row.selected,
        available: row.available !== false,
        amount_cents: row.amount_cents ?? null,
      })),
      breakdown_amounts: (result.breakdown || []).map((row) => ({
        label: row.label,
        amount_cents: row.amount_cents ?? centsFor(row.amount),
      })),
      component_amounts: [
        ...["pre_minimum_selling_price", "item_minimum_total", "order_minimum_total", "minimum_adjustment"].map((field) => ({
          field,
          amount_cents: centsFor(result[field]),
        })).filter((row) => row.amount_cents != null),
      ],
      errors: result.errors || [],
      warnings: result.warnings || result.calculation_warnings || [],
    },
  };
}

function pricingResult(category = "banners") {
  if (category === "banners") {
    return withPricingEngineResult({
      category,
      selling_price: 999,
      canonical_method_id: "square_foot_plus_addons",
      selected_method_id: "square_foot_plus_addons",
      pricing_method_used: "square_foot_plus_addons",
      pricing_method_results: [
        successfulMethod("square_foot_plus_addons", 192, true),
        successfulMethod("cost_plus", 170, false),
        { method_id: "target_margin", display_name: "target margin", status: "unavailable", available: false, reason: "missing true cost", amount: null },
      ],
      method_availability: [
        { method_id: "square_foot_plus_addons", available: true },
        { method_id: "cost_plus", available: true },
        { method_id: "target_margin", available: false, reason: "missing true cost" },
      ],
      breakdown: [{ label: "Base square-foot amount", amount: 144 }],
      detail_sections: [{ section: "authoritative_result", lines: [{ label: "Area", value: "24 sq ft" }] }],
      warnings: ["Owner-approved fixture warning"],
      errors: [],
    }, 19200);
  }

  if (category === "digital_print") {
    return withPricingEngineResult({
      category,
      selling_price: 20,
      canonical_method_id: "per_sqft",
      selected_method_id: "per_sqft",
      pricing_method_used: "per_sqft",
      minimum_policy: "digital_print_item_minimum_document_order_minimum",
      minimum_scope: "digital_print_line_item",
      pre_minimum_selling_price: 16.45,
      item_minimum: 20,
      order_minimum: 40,
      item_minimum_total: 20,
      order_minimum_total: 40,
      minimum_charge_applied: true,
      minimum_adjustment: 3.55,
      minimum_applied_reason: "item_minimum",
      pricing_method_results: [
        successfulMethod("per_sqft", 20, true),
        { method_id: "manual_override", display_name: "manual override", status: "unavailable", available: false, reason: "no manual amount", amount: null },
      ],
      method_availability: [
        { method_id: "per_sqft", available: true },
        { method_id: "manual_override", available: false, reason: "no manual amount" },
      ],
      detail_sections: [{
        section: "category_specific_details",
        lines: [
          { key: "pre_minimum_selling_price", label: "Pre Minimum Selling Price", amount: 16.45 },
          { key: "item_minimum_total", label: "Item Minimum Total", amount: 20 },
          { key: "order_minimum_total", label: "Document Order Minimum", amount: 40 },
          { key: "minimum_adjustment", label: "Item Minimum Adjustment", amount: 3.55 },
        ],
      }],
      breakdown: [{ label: "Digital Print item minimum adjustment", amount: 3.55 }],
      warnings: ["Digital Print order minimum is evaluated once at Quote or Order document level."],
      errors: [],
    }, 2000);
  }

  return withPricingEngineResult({
    category,
    selling_price: 48,
    canonical_method_id: "unit_price_x_quantity",
    selected_method_id: "unit_price_x_quantity",
    pricing_method_used: "unit_price_x_quantity",
    pricing_method_results: [
      successfulMethod("unit_price_x_quantity", 48, true),
      { method_id: "manual_override", display_name: "manual override", status: "unavailable", available: false, reason: "no manual amount", amount: null },
    ],
    method_availability: [
      { method_id: "unit_price_x_quantity", available: true },
      { method_id: "manual_override", available: false, reason: "no manual amount" },
    ],
    detail_sections: [{ section: `${category}_details`, lines: [{ label: "Category detail", value: "preserved" }] }],
    breakdown: [],
    warnings: [],
    errors: [],
  }, 4800);
}

function comparisonResult(selectedMethodId = "square_foot_plus_addons") {
  return {
    category_id: "banners",
    pricing_result: pricingResult("banners"),
    canonical_method_id: "square_foot_plus_addons",
    selected_method_id: selectedMethodId,
    primary_method_id: selectedMethodId,
    comparison_results: [
      { method_id: "square_foot_plus_addons", status: "success", available: true, amount: 999, amount_cents: 19200, selected: selectedMethodId === "square_foot_plus_addons" },
      { method_id: "cost_plus", status: "success", available: true, amount: 170, amount_cents: 17000, selected: selectedMethodId === "cost_plus" },
      { method_id: "target_margin", status: "unavailable", available: false, reason: "missing true cost", amount: null },
    ],
    availability: [
      { method_id: "square_foot_plus_addons", available: true },
      { method_id: "cost_plus", available: true },
      { method_id: "target_margin", available: false, reason: "missing true cost" },
    ],
  };
}

function mockApi() {
  const response = (data) => Promise.resolve({ data });

  api.get.mockImplementation((url) => {
    if (url === "/pricing/settings") {
      return response({
        category_meta: categoryMeta,
        material_profiles: [],
        pricing_components: [],
        pricing_presets: [],
      });
    }
    if (url.includes("/method-configuration")) {
      return response({
        configuration_mode: "starter_default",
        configuration_version: 1,
        primary_method_id: "square_foot_plus_addons",
        enabled_method_ids: ["square_foot_plus_addons", "cost_plus"],
      });
    }
    if (url.includes("/tier-price")) {
      return response({ tier_price: 150 });
    }
    if (url === "/pricing/saved-calculations") {
      return response({
        items: [
          {
            id: "saved-calc-1",
            name: "Saved banner",
            category: "banners",
            selling_price: 999,
            selling_price_cents: 18000,
            pricing_engine_result: {
              status: "success",
              selling_price_cents: 18000,
              method_rows: [{ method_id: "square_foot_plus_addons", amount_cents: 18000, selected: true, available: true }],
            },
            canonical_method_id: "square_foot_plus_addons",
            selected_method_id: "square_foot_plus_addons",
            pricing_method_results: [successfulMethod("square_foot_plus_addons", 180, true)],
            calculation_inputs: {
              category: "banners",
              width_inches: 96,
              height_inches: 36,
              quantity: 1,
              category_inputs: { dimension_unit: "in", selected_pricing_method: "square_foot_plus_addons" },
              pricing_component_ids: [],
            },
          },
        ],
      });
    }
    return response({});
  });

  api.post.mockImplementation((url, payload) => {
    if (url === "/pricing/calculate") {
      return response(pricingResult(payload.category));
    }
    if (url === "/pricing/method-comparison") {
      return response(comparisonResult(payload.primary_method_id || "square_foot_plus_addons"));
    }
    if (url === "/pricing/saved-calculations") {
      return response({ id: "saved-new", name: payload.name, category: payload.calculation_inputs.category });
    }
    if (url === "/pricing/saved-calculations/saved-calc-1/recalculate") {
      return response({
        saved_calculation: {
          id: "saved-calc-1",
          name: "Saved banner",
          selling_price: 999,
          selling_price_cents: 18000,
          pricing_engine_result: {
            status: "success",
            selling_price_cents: 18000,
            method_rows: [{ method_id: "square_foot_plus_addons", amount_cents: 18000, selected: true, available: true }],
          },
          calculation_inputs: {
            category: "banners",
            width_inches: 96,
            height_inches: 36,
            quantity: 1,
            category_inputs: { dimension_unit: "in", selected_pricing_method: "square_foot_plus_addons" },
            pricing_component_ids: [],
          },
        },
        current_result: pricingResult("banners"),
        comparison_result: comparisonResult("square_foot_plus_addons"),
        saved_price: 999,
        current_price: 999,
        saved_selling_price_cents: 18000,
        current_selling_price_cents: 19200,
        price_changed: true,
        transferable: true,
      });
    }
    if (url.includes("/method-availability")) {
      return response({
        recommended_primary_method_id: "square_foot_plus_addons",
        methods: [
          { method_id: "square_foot_plus_addons", available: true, method: { display_name: "Square foot plus add-ons" } },
          { method_id: "cost_plus", available: true, method: { display_name: "Cost plus" } },
          { method_id: "target_margin", available: false, reason: "missing true cost", method: { display_name: "Target margin" } },
        ],
      });
    }
    if (url.includes("/simple-setup/preview")) {
      return response({ enabled_method_ids: ["square_foot_plus_addons", "cost_plus"] });
    }
    if (url.includes("/simple-setup/apply")) {
      return response({ configuration_version: 2 });
    }
    return response({});
  });

  api.put.mockResolvedValue({ data: { configuration_version: 3 } });
  api.patch.mockResolvedValue({ data: {} });
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.useRealTimers();
  useAuth.mockReturnValue({
    hasPerm: (permission) => ["pricing:calculate", "pricing:read", "pricing:write"].includes(permission),
  });
  mockApi();
});

test("Shop Operations navigation omits Pricing as a permanent module", () => {
  const shopOperations = NAV_AREAS.find((area) => area.key === "shop-operations");
  expect(shopOperations.moduleNav.filter((item) => !item.hidden).map((item) => item.key)).toEqual([
    "overview",
    "customers",
    "sales",
    "approval-center",
    "production",
    "schedule",
    "webstores",
  ]);
  expect(shopOperations.moduleNav.some((item) => item.key === "pricing")).toBe(false);
  expect(shopOperations.moduleNav.find((item) => item.key === "wrap-lab")).toMatchObject({ hidden: true, contextual: true });
  expect(shopOperations.flyout).toBeUndefined();
});

test("renders the dedicated workspace and displays Banner authoritative and comparison results", async () => {
  renderWithProviders(<PricingCalculatorPage />);

  expect(await screen.findByTestId("pricing-calculator-workspace")).toBeInTheDocument();
  for (const label of ["Banners", "Rigid Signs", "Cut Vinyl", "Digital Print", "Vehicle Graphics", "Apparel", "Promotional", "Services", "Custom"]) {
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
  }
  fireEvent.click(screen.getByTestId("calc-run-button"));

  expect(await screen.findByTestId("calc-result")).toBeInTheDocument();
  expect(screen.getByTestId("calc-authoritative-selling-price")).toHaveTextContent("$192.00");
  expect(screen.getByTestId("calc-canonical-method")).toHaveTextContent("square foot plus addons");
  expect(screen.getByTestId("calc-selected-comparison-method")).toHaveTextContent("square foot plus addons");
  expect(screen.getByTestId("calc-method-square_foot_plus_addons")).toHaveTextContent("$192.00");
  expect(screen.getByTestId("calc-method-cost_plus")).toHaveTextContent("$170.00");
  expect(screen.getByTestId("calc-unavailable-methods")).toHaveTextContent("target margin");
  expect(screen.getByTestId("calc-warnings-banner")).toHaveTextContent("Owner-approved fixture warning");
  expect(screen.getByTestId("calc-detail-sections")).toHaveTextContent("24 sq ft");

  expect(api.post).toHaveBeenCalledWith("/pricing/calculate", expect.objectContaining({ category: "banners" }));
  expect(api.post).toHaveBeenCalledWith("/pricing/method-comparison", expect.objectContaining({ category: "banners" }));
});

test("switches to a normalized non-Banner category without calling Banner comparison", async () => {
  renderWithProviders(<PricingCalculatorPage />);
  fireEvent.change(await screen.findByTestId("calc-category-select"), { target: { value: "apparel" } });
  fireEvent.click(screen.getByTestId("calc-run-button"));

  expect(await screen.findByTestId("calc-category-fields-apparel")).toBeInTheDocument();
  expect(await screen.findByTestId("calc-authoritative-selling-price")).toHaveTextContent("$48.00");
  expect(screen.getByTestId("calc-method-unit_price_x_quantity")).toHaveTextContent("$48.00");
  expect(screen.getByTestId("calc-unavailable-methods")).toHaveTextContent("manual override");
  expect(screen.getByTestId("calc-detail-sections")).toHaveTextContent("Category detail");

  expect(api.post).toHaveBeenCalledWith("/pricing/calculate", expect.objectContaining({ category: "apparel" }));
  const comparisonCalls = api.post.mock.calls.filter(([url]) => url === "/pricing/method-comparison");
  expect(comparisonCalls).toHaveLength(0);
});

test("displays Digital Print minimum evidence returned by the backend", async () => {
  renderWithProviders(<PricingCalculatorPage />);
  fireEvent.change(await screen.findByTestId("calc-category-select"), { target: { value: "digital_print" } });
  fireEvent.click(screen.getByTestId("calc-run-button"));

  expect(await screen.findByTestId("calc-authoritative-selling-price")).toHaveTextContent("$20.00");
  expect(screen.getByTestId("calc-detail-sections")).toHaveTextContent("Item Minimum Adjustment");
  expect(screen.getByTestId("calc-detail-sections")).toHaveTextContent("$3.55");
  expect(screen.getByTestId("calc-detail-sections")).toHaveTextContent("Document Order Minimum");
  expect(screen.getByTestId("calc-detail-sections")).toHaveTextContent("$40.00");
  expect(screen.getByTestId("calc-warnings-banner")).toHaveTextContent("document level");
  expect(api.post).toHaveBeenCalledWith("/pricing/calculate", expect.objectContaining({ category: "digital_print" }));
});

test("selects a Banner comparison method deliberately without replacing the authoritative price", async () => {
  renderWithProviders(<PricingCalculatorPage />);
  fireEvent.click(await screen.findByTestId("calc-run-button"));
  await screen.findByTestId("calc-result");

  fireEvent.click(screen.getByTestId("calc-method-cost_plus"));

  await waitFor(() => {
    expect(screen.getByTestId("calc-selected-comparison-method")).toHaveTextContent("cost plus");
  });
  expect(screen.getByTestId("calc-authoritative-selling-price")).toHaveTextContent("$192.00");
  expect(api.post).toHaveBeenCalledWith("/pricing/method-comparison", expect.objectContaining({ primary_method_id: "cost_plus" }));
});

test("shows loading and error states honestly", async () => {
  let rejectCalculation;
  api.post.mockImplementation((url) => {
    if (url === "/pricing/calculate") {
      return new Promise((resolve, reject) => {
        rejectCalculation = reject;
      });
    }
    if (url.includes("/method-availability")) {
      return Promise.resolve({ data: { methods: [] } });
    }
    return Promise.resolve({ data: {} });
  });

  renderWithProviders(<PricingCalculatorPage />);
  fireEvent.click(await screen.findByTestId("calc-run-button"));
  expect(await screen.findByTestId("calc-loading-state")).toBeInTheDocument();

  rejectCalculation(new Error("pricing failed"));
  expect(await screen.findByTestId("calc-error-state")).toHaveTextContent("pricing failed");
});

test("fails closed when a fresh current response has invalid normalized cents despite legacy dollars", async () => {
  api.post.mockImplementation((url) => {
    if (url === "/pricing/calculate") {
      return Promise.resolve({
        data: {
          ...pricingResult("banners"),
          selling_price: 192,
          pricing_engine_result: { status: "success", selling_price_cents: true },
        },
      });
    }
    if (url.includes("/method-availability")) return Promise.resolve({ data: { methods: [] } });
    return Promise.resolve({ data: {} });
  });

  renderWithProviders(<PricingCalculatorPage />);
  fireEvent.click(await screen.findByTestId("calc-run-button"));

  expect(await screen.findByTestId("calc-error-state")).toHaveTextContent("selling_price_cents");
  expect(screen.queryByTestId("calc-result")).not.toBeInTheDocument();
});

test("exposes simple and advanced method configuration controls without persisting calculations", async () => {
  renderWithProviders(<PricingCalculatorPage />);
  fireEvent.click(await screen.findByTestId("calc-view-methods"));

  expect(await screen.findByTestId("pricing-method-setup-panel")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("calc-simple-preview-inline-button"));
  await waitFor(() => {
    expect(screen.getByTestId("calc-simple-preview")).toHaveTextContent("square foot plus addons");
  });

  fireEvent.click(screen.getByTestId("calc-advanced-save-button"));
  await waitFor(() => {
    expect(api.put).toHaveBeenCalledWith(expect.stringContaining("/advanced-setup"), expect.objectContaining({ primary_method_id: expect.any(String) }));
  });
  expect(api.post.mock.calls.some(([url]) => String(url).includes("calculations"))).toBe(false);
});

test("explicitly saves the current backend calculation from the dedicated workspace", async () => {
  renderWithProviders(<PricingCalculatorPage />);
  fireEvent.click(await screen.findByTestId("calc-run-button"));
  await screen.findByTestId("calc-result");

  fireEvent.change(screen.getByTestId("calc-save-name"), { target: { value: "8x3 saved banner" } });
  fireEvent.click(screen.getByTestId("calc-save-inline-button"));

  await waitFor(() => {
    expect(api.post).toHaveBeenCalledWith("/pricing/saved-calculations", expect.objectContaining({
      name: "8x3 saved banner",
      source_context: "pricing_calculator",
      calculation_inputs: expect.objectContaining({ category: "banners", width_inches: 96, height_inches: 36 }),
    }));
  });
});

test("uses a saved calculation as a fresh working copy and shows saved versus current price", async () => {
  renderWithProviders(<PricingCalculatorPage />);

  fireEvent.click(await screen.findByTestId("calc-view-library"));
  expect(await screen.findByTestId("saved-calculation-library")).toBeInTheDocument();
  fireEvent.click(await screen.findByTestId("saved-calc-row-saved-calc-1"));
  fireEvent.click(screen.getByTestId("saved-calc-use"));

  expect(await screen.findByTestId("calc-saved-current-price-panel")).toHaveTextContent("Saved Price");
  expect(screen.getByTestId("calc-saved-current-price-panel")).toHaveTextContent("$180.00");
  expect(screen.getByTestId("calc-saved-current-price-panel")).toHaveTextContent("$192.00");
  expect(screen.getByTestId("calc-saved-current-price-diff")).toBeInTheDocument();
  expect(screen.getByTestId("calc-authoritative-selling-price")).toHaveTextContent("$192.00");
});

test("denies the workspace when the user lacks pricing calculation permission", () => {
  useAuth.mockReturnValue({ hasPerm: () => false });
  renderWithProviders(<PricingCalculatorPage />);

  expect(screen.getByTestId("pricing-calculator-permission-denied")).toBeInTheDocument();
  expect(api.get).not.toHaveBeenCalled();
  expect(api.post).not.toHaveBeenCalled();
});
