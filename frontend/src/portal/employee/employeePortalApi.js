import axios from "axios";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND}/api`;

// EC8 phase 8c — separate token storage key from the Customer Portal
// (`sg_portal_token`) so a browser can hold an active Customer Portal
// session and an active Employee Portal session at the same time without
// either one clobbering the other.
const TOKEN_KEY = "sg_employee_portal_token";

const employeePortalApi = axios.create({ baseURL: API });

employeePortalApi.interceptors.request.use((cfg) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

employeePortalApi.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e?.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      if (!window.location.pathname.startsWith("/portal/employee/login") &&
          !window.location.pathname.startsWith("/portal/employee/verify")) {
        window.location.assign("/portal/employee/login");
      }
    }
    return Promise.reject(e);
  }
);

export function employeePortalExtractError(err, fallback = "Something went wrong") {
  return err?.response?.data?.detail || err?.message || fallback;
}

export { TOKEN_KEY };
export default employeePortalApi;
