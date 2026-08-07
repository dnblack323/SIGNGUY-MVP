const legacyBackend = process.env.REACT_APP_BACKEND_URL?.replace(/\/+$/, "");
const legacyDevApiBase = process.env.NODE_ENV === "development" && legacyBackend ? `${legacyBackend}/api` : "";

export const API_BASE = process.env.REACT_APP_API_BASE_URL || legacyDevApiBase || "/api";
