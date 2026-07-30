import axios from "axios";
import { API_BASE } from "@/lib/apiBase";

export const API = API_BASE;

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
