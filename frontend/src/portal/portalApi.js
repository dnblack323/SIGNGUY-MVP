import axios from "axios";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND}/api`;

const portalApi = axios.create({ baseURL: API });

portalApi.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("sg_portal_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

portalApi.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e?.response?.status === 401) {
      localStorage.removeItem("sg_portal_token");
      if (!window.location.pathname.startsWith("/portal/login") && !window.location.pathname.startsWith("/portal/verify")) {
        window.location.assign("/portal/login");
      }
    }
    return Promise.reject(e);
  }
);

export function portalExtractError(err, fallback = "Something went wrong") {
  return err?.response?.data?.detail || err?.message || fallback;
}

export default portalApi;
