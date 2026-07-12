import { basisLabel, money, PO_STATUS_TONE, EXPENSE_STATE_TONE, debounce } from "@/lib/ec7";

describe("lib/ec7 helpers", () => {
  test("basisLabel maps known keys", () => {
    expect(basisLabel("issued_invoices")).toMatch(/Invoice basis/i);
    expect(basisLabel("expenses")).toMatch(/Expense basis/i);
  });

  test("basisLabel falls back to key or dash", () => {
    expect(basisLabel("nope")).toBe("nope");
    expect(basisLabel(undefined)).toBe("—");
  });

  test("money formats cents to USD", () => {
    expect(money(0)).toBe("$0.00");
    expect(money(12345)).toBe("$123.45");
    expect(money(-500)).toBe("-$5.00");
  });

  test("PO_STATUS_TONE covers the six statuses", () => {
    for (const k of ["draft", "submitted", "acknowledged", "partially_received", "received", "cancelled"]) {
      expect(typeof PO_STATUS_TONE[k]).toBe("string");
    }
  });

  test("EXPENSE_STATE_TONE covers three states", () => {
    for (const k of ["active", "archived", "voided"]) {
      expect(typeof EXPENSE_STATE_TONE[k]).toBe("string");
    }
  });

  test("debounce batches rapid calls", (done) => {
    let count = 0;
    const fn = debounce(() => { count += 1; }, 20);
    fn(); fn(); fn();
    setTimeout(() => {
      expect(count).toBe(1);
      done();
    }, 60);
  });
});
