export function centsToDollarsString(cents) {
  const n = Number(cents || 0) / 100;
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function isValidIntegerCents(value, { allowNegative = false } = {}) {
  if (typeof value !== "number" || !Number.isInteger(value) || !Number.isFinite(value)) return false;
  return allowNegative || value >= 0;
}

export function pricingEngineResult(source) {
  if (!source || typeof source !== "object") return null;
  const result = source.pricing_engine_result || source.current_pricing_engine_result || source.historical_pricing_engine_result;
  return result && typeof result === "object" ? result : null;
}

export function authoritativeSellingPriceCents(source, { allowLegacy = false } = {}) {
  const result = pricingEngineResult(source);
  if (result) {
    if (result.status && result.status !== "success") return null;
    if (!isValidIntegerCents(result.selling_price_cents)) {
      throw new Error("pricing_engine_result.selling_price_cents is not valid integer cents");
    }
    const topLevelCents = source?.selling_price_cents;
    if (topLevelCents != null && !isValidIntegerCents(topLevelCents)) {
      throw new Error("selling_price_cents is not valid integer cents");
    }
    if (topLevelCents != null && topLevelCents !== result.selling_price_cents) {
      throw new Error("pricing_engine_result.selling_price_cents disagrees with selling_price_cents");
    }
    return result.selling_price_cents;
  }
  if (!allowLegacy) return null;
  const candidates = [
    source?.selling_price_cents,
    source?.historical_selling_price_cents,
    source?.suggested_price_cents,
    source?.calculated_unit_price_cents,
  ];
  const cents = candidates.find((value) => value != null);
  return isValidIntegerCents(cents) ? cents : null;
}

export function transferUnitPriceCentsFromPricingResult(source, { category, quantity } = {}) {
  const sellingPriceCents = authoritativeSellingPriceCents(source);
  if (sellingPriceCents == null) return null;
  if (category !== "digital_print") return sellingPriceCents;
  const qty = Math.max(1, Number(quantity) || 1);
  return Math.round(sellingPriceCents / qty);
}

export function methodAmountCents(row, result = null) {
  if (!row || typeof row !== "object") return null;
  if (isValidIntegerCents(row.amount_cents)) return row.amount_cents;
  const methodId = row.method_id || row.method || row.id;
  const engine = pricingEngineResult(result) || result;
  const normalized = (engine?.method_rows || []).find((item) => (item.method_id || item.method) === methodId);
  if (isValidIntegerCents(normalized?.amount_cents)) return normalized.amount_cents;
  return null;
}

export function breakdownAmountCents(row, result = null, index = -1) {
  if (!row || typeof row !== "object") return null;
  if (isValidIntegerCents(row.amount_cents, { allowNegative: true })) return row.amount_cents;
  const engine = pricingEngineResult(result) || result;
  const normalized = Array.isArray(engine?.breakdown_amounts) ? engine.breakdown_amounts[index] : null;
  if (isValidIntegerCents(normalized?.amount_cents, { allowNegative: true })) return normalized.amount_cents;
  return null;
}

export function componentAmountCents(field, result = null) {
  const engine = pricingEngineResult(result) || result;
  const normalized = (engine?.component_amounts || []).find((item) => item.field === field);
  return isValidIntegerCents(normalized?.amount_cents, { allowNegative: true }) ? normalized.amount_cents : null;
}

export function formatPricingCents(value) {
  return isValidIntegerCents(value, { allowNegative: true }) ? centsToDollarsString(value) : "Unavailable";
}

export function parseDollarsToCents(input) {
  if (input === "" || input === null || input === undefined) return 0;
  const cleaned = String(input).replace(/[^0-9.-]/g, "");
  if (cleaned === "" || cleaned === "-" || cleaned === ".") return 0;
  const n = Number(cleaned);
  if (Number.isNaN(n)) return 0;
  return Math.round(n * 100);
}

export function formatDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "2-digit" });
  } catch {
    return iso;
  }
}

export function formatDateTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-US", {
      year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function relativeTime(iso) {
  if (!iso) return "";
  try {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const diff = Math.round((now - then) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export function formatMinutes(mins) {
  const total = Math.max(0, Math.round(Number(mins) || 0));
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${h}h ${m}m`;
}

export function formatClockTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}
