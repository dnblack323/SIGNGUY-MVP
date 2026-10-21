import api from "@/lib/api";

const unauthorized = { response: { status: 401, data: { detail: "Not authenticated" } } };

afterEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  window.history.replaceState({}, "", "/");
});

test("an unrelated suspended-staff response cannot redirect the owner portal", async () => {
  window.history.replaceState({}, "", "/portal/webstores/store-1");
  localStorage.setItem("sg_portal_token", "owner-token");
  localStorage.setItem("signguy.token", "separate-staff-token");
  const suspended = { response: { status: 403, data: { detail: { code: "tenant_suspended" } } } };
  await expect(api.get("/webstores/store-1/setup-files", {
    adapter: () => Promise.reject(suspended),
  })).rejects.toBe(suspended);
  expect(localStorage.getItem("sg_portal_token")).toBe("owner-token");
  expect(localStorage.getItem("signguy.token")).toBe("separate-staff-token");
  expect(sessionStorage.getItem("signguy.suspended")).toBeNull();
  expect(window.location.pathname).toBe("/portal/webstores/store-1");
});

test("a suspended-staff response still routes staff to the suspended-account page", async () => {
  const originalLocation = window.location;
  delete window.location;
  window.location = { pathname: "/webstores/store-1", href: "/webstores/store-1" };
  localStorage.setItem("signguy.token", "suspended-staff-token");
  const detail = { code: "tenant_suspended", message: "Account suspended" };
  const suspended = { response: { status: 403, data: { detail } } };
  try {
    await expect(api.get("/webstores/store-1/setup-files", {
      adapter: () => Promise.reject(suspended),
    })).rejects.toBe(suspended);
    expect(localStorage.getItem("signguy.token")).toBeNull();
    expect(JSON.parse(sessionStorage.getItem("signguy.suspended"))).toEqual(detail);
    expect(window.location.href).toBe("/account-suspended");
  } finally {
    window.location = originalLocation;
  }
});

test.each(["/portal", "/portal/webstores/store-1", "/portal/login"])(
  "a staff 401 on %s preserves the separate portal session and location",
  async (path) => {
    window.history.replaceState({}, "", path);
    localStorage.setItem("sg_portal_token", "owner-only-token");
    const adapter = jest.fn(() => Promise.reject(unauthorized));

    await expect(api.get("/webstores/store-1/setup-files", { adapter })).rejects.toBe(unauthorized);

    expect(adapter.mock.calls[0][0].headers.Authorization).toBeUndefined();
    expect(localStorage.getItem("sg_portal_token")).toBe("owner-only-token");
    expect(localStorage.getItem("signguy.token")).toBeNull();
    expect(window.location.pathname).toBe(path);
  },
);

test("a staff 401 in the portal does not clear a separate staff token", async () => {
  window.history.replaceState({}, "", "/portal/webstores/store-1");
  localStorage.setItem("signguy.token", "separate-staff-token");
  await expect(api.get("/webstores/store-1/setup-files", {
    adapter: () => Promise.reject(unauthorized),
  })).rejects.toBe(unauthorized);
  expect(localStorage.getItem("signguy.token")).toBe("separate-staff-token");
  expect(window.location.pathname).toBe("/portal/webstores/store-1");
});

test("a staff 401 still clears staff authentication and redirects outside the portal", async () => {
  const originalLocation = window.location;
  delete window.location;
  window.location = { pathname: "/webstores/store-1", href: "/webstores/store-1" };
  localStorage.setItem("signguy.token", "expired-staff-token");
  localStorage.setItem("sg_portal_token", "separate-owner-token");
  try {
    await expect(api.get("/webstores/store-1/setup-files", {
      adapter: () => Promise.reject(unauthorized),
    })).rejects.toBe(unauthorized);
    expect(localStorage.getItem("signguy.token")).toBeNull();
    expect(localStorage.getItem("sg_portal_token")).toBe("separate-owner-token");
    expect(window.location.href).toBe("/login");
  } finally {
    window.location = originalLocation;
  }
});
