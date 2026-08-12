const legacyBackend = process.env.REACT_APP_BACKEND_URL?.replace(/\/+$/, "");
const legacyApiBase = legacyBackend ? `${legacyBackend}/api` : "";

export const API_BASE =
  process.env.REACT_APP_API_BASE_URL ||
  (process.env.NODE_ENV === "development" ? "/api" : legacyApiBase || "/api");
