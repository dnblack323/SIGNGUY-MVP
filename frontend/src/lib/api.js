import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || (process.env.NODE_ENV === "development" ? "http://localhost:8001" : "");
if (!BACKEND_URL) {
  // Surface build/deploy misconfiguration without logging any credential value.
  console.error("REACT_APP_BACKEND_URL is not configured.");
}
export const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API, timeout: 30000 });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("signguy.token");
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      const path = window.location.pathname;
      if (!path.startsWith("/login") && !path.startsWith("/register") && !path.startsWith("/forgot-password") && !path.startsWith("/reset-password")) {
        localStorage.removeItem("signguy.token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  },
);

export default api;

export function extractError(err, fallback = "Something went wrong") {
  const d = err?.response?.data;
  if (!d) return fallback;
  if (typeof d?.detail === "string") return d.detail;
  if (Array.isArray(d?.detail)) {
    return d.detail.map((e) => e.msg || JSON.stringify(e)).join("; ");
  }
  return fallback;
}
